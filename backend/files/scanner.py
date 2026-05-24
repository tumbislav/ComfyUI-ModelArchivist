# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: scanner.py
# purpose: File system scan
# ---------------------------------------------------------------------------

from backend.repository.tables import Model, Component, Workflow

import logging
from threading import Thread, Lock, Barrier
from pathlib import Path
import hashlib
import json
from itertools import chain
from dataclasses import dataclass, field
import datetime
from collections import Counter

from backend.config import get_config, Configuration
import backend.repository.repository as repo
from enum import StrEnum


class ComponentType(StrEnum):
    MODEL = 'model'
    METADATA = 'metadata'
    EXTRA = 'extra'
    EXAMPLE = 'example'
    WORKFLOW = 'workflow'

@dataclass
class Scanner:
    start_time: datetime.datetime | None = None
    end_time: datetime.datetime | None = None
    started: bool = False
    finished: bool = False
    models_scanned: int = 0
    workflows_scanned: int = 0
    hashes_calculated: int = 0
    errors: list[str] = field(default_factory=list)
    lock: Lock = Lock()
    barrier: Barrier | None = None
    config: Configuration | None = None
    logger: logging.Logger = field(default_factory=lambda:logging.getLogger('archivist.files'))

    def start(self, rehash: bool = False) -> str | None:
        if self.started:
            self.logger.error(f'attempting to start an already started scanner')
            return None
        self.config = get_config()
        self.logger.debug(f'starting scan with rehash={rehash}')

        self.started = True
        self.start_time = datetime.datetime.now(tz=datetime.timezone.utc)

        threads = []
        for name, locations in self.config.model_folders.items():
            for active, archive in locations:
                threads.append(Thread(target=self.find_models, args=(name, active, archive, rehash)))

        for active, archive in self.config.workflow_folders:
            threads.append(Thread(target=self.find_workflows, args=(active, archive)))

        threads.append(Thread(target=self.cleanup, args=tuple()))
        self.barrier = Barrier(len(threads))

        self.logger.debug(f'creating {len(threads)} worker threads')
        for thread in threads:
            thread.start()
        return self.timestamp

    def report(self, models: int=0, workflows: int=0, hashes: int=0, error: str=''):
        with self.lock:
            self.models_scanned += models
            self.workflows_scanned += workflows
            self.hashes_calculated += hashes
            if error != '':
                self.errors.append(error)

    def progress(self) -> dict:
        if not self.started:
            return {'started': False}
        progress_dict = {'started': self.started,
                         'finished': self.finished,
                         'models_scanned': self.models_scanned,
                         'workflows_scanned': self.workflows_scanned,
                         'hashes_calculated': self.hashes_calculated}

        if self.start_time is not None:
            progress_dict['start_time'] = self.start_time.isoformat()  # noqa
            if self.end_time is None:
                interval = datetime.datetime.now(tz=datetime.timezone.utc) - self.start_time
            else:
                progress_dict['end_time'] = self.end_time.isoformat()  # noqa
                interval = self.end_time - self.start_time
            progress_dict['duration'] = interval.total_seconds()  # noqa

        return progress_dict

    @property
    def timestamp(self):
        return self.start_time.isoformat()

    def cleanup(self):
        self.barrier.wait()
        self.logger.debug(f'starting cleanup')
        with repo.lock:
            repo.scan_cleanup(self.timestamp)
        with self.lock:
            self.finished = True
        self.logger.debug(f'completed filesystem scan')
        self.end_time = datetime.datetime.now(tz=datetime.timezone.utc)

    def find_models(self, type_name: str, working_root: Path, archive_root: Path, rehash: bool):
        """
        Scan a directory with subdirectories and return all model and sidecar files found.
        The active and archive directories are scanned in parallel.
        """
        self.logger.debug(f'starting scan for {type_name} in {working_root} and {archive_root}')
        working_examples = working_root.parent / 'examples'
        archive_examples = archive_root.parent / 'examples'

        for working_dir, subdirs, filenames in working_root.walk():
            relative_path = match_folders(working_root, archive_root, working_dir, subdirs)
            archive_dir = archive_root / relative_path

            # Make a list of all files.
            # - Model files in archive and active folders match by hash, but they must also match by filename.
            # - Extra files are matched by file stem.
            # - Examples are located in a folder named hash in the examples branch.
            models = {}
            sidecars = {}

            # first collect all model and sidecar files
            self.logger.debug(f'current dir {working_dir}')
            for file_path, where in chain(((working_dir / fn, 'w') for fn in filenames),
                                          ((f.resolve(), 'a') for f in archive_dir.iterdir() if f.is_file())):
                stem = file_path.stem
                if file_path.suffix in self.config.model_extensions:
                    metadata_file = file_path.with_suffix('.metadata.json')
                    metadata = ensure_metadata(file_path, metadata_file, rehash, self.logger)
                    sha256 = metadata['sha256']
                    if sha256 not in models:
                        models[sha256] = {'stem': stem,
                                              'id': sha256,
                                              'name': metadata.get('model_name', stem),
                                              'tags': metadata.get('tags', []),
                                              'relative_path': str(relative_path),
                                              'files': []}
                    elif models[sha256]['stem'] != stem:
                        self.report(error=f'model {file_path.stem} has the same hash as {models[sha256]["stem"]}')
                        continue
                    models[sha256]['files'].append((file_path, ComponentType.MODEL, where))
                    models[sha256]['files'].append((metadata_file, ComponentType.METADATA, where))
                elif not file_path.name.endswith('.metadata.json'):
                    if stem not in sidecars:
                        sidecars[stem] = [(file_path, ComponentType.EXTRA, where)]
                    else:
                        sidecars[stem].append((file_path, ComponentType.EXTRA, where))

            # Assemble and save all models found
            for sha256, model_dict in models.items():
                stem = model_dict['stem']
                self.logger.debug(f'finalizing model {stem}')
                files = model_dict['files']

                if stem in sidecars:
                    for file_path, component_type, where in sidecars[stem]:
                        files.append((file_path, component_type, where))
                examples_dir = working_examples / sha256
                if examples_dir.is_dir():
                    for example in examples_dir.iterdir():
                        files.append((example.resolve(), ComponentType.EXAMPLE, 'w'))
                examples_dir = archive_examples / sha256
                if examples_dir.is_dir():
                    for example in examples_dir.iterdir():
                        files.append((example.resolve(), ComponentType.EXAMPLE, 'a'))

                counts = Counter([_[-1] for _ in files])
                self.logger.debug(f'found model {model_dict["name"]} in {model_dict["relative_path"]}')
                model = Model(id=model_dict['id'],
                              name=model_dict['name'],
                              type=type_name,
                              relative_path=model_dict['relative_path'],
                              working_dir=str(working_root),
                              archive_dir=str(archive_root),
                              archived=counts['a'],
                              working=counts['w'],
                              scan_timestamp=self.timestamp,
                              components=[Component(file_name=str(file_path.name),
                                                    file_dir=str(file_path.parent),
                                                    where=where,
                                                    component_type=file_type,
                                                    scan_timestamp=self.timestamp)
                                          for file_path, file_type, where in files])
                with repo.lock:
                    repo.save_scanned_model(model, model_dict['tags'])
                self.report(models=1)
        self.logger.debug(f'scan for {type_name} complete in {working_root} and {archive_root}')
        self.barrier.wait()

    def find_workflows(self, working_root: Path, archive_root: Path):
        self.logger.debug(f'starting workflow scan in {working_root} and {archive_root}')
        for active_dir, subdirs, filenames in working_root.walk():
            relative_path = match_folders(working_root, archive_root, active_dir, subdirs)
            archive_dir = archive_root / relative_path
            workflows = {}
            for file_path, where in chain(((active_dir / fn, 'w') for fn in filenames),
                                            ((f.resolve(), 'a') for f in archive_dir.iterdir() if f.is_file())):
                if file_path.suffix != '.json':
                    self.logger.debug(f'ignoring {str(file_path)}')
                    continue
                stem = file_path.stem
                data = json.loads(file_path.read_text(encoding='utf-8'))
                # sanity check that this is a workflow file
                if 'id' not in data or 'revision' not in data or 'version' not in data:
                    self.logger.warning(f'{file_path} does not contain a valid workflow')
                    self.report(error=f'{file_path} does not contain a valid workflow')
                    continue
                workflow_id = data['id']
                conf = data.get('config', {})
                if workflow_id not in workflows:
                    workflows[workflow_id] = {'stem': stem,
                                              'id': workflow_id,
                                              'name': conf.get('name', stem),
                                              'purpose': conf.get('purpose', ''),
                                              'tags': conf.get('tags', []),
                                              'relative_path': str(relative_path),
                                              'files': []}
                elif workflows[workflow_id]['stem'] != stem:
                    self.report(error=f'model {file_path.stem} has the same id as {workflows[workflow_id]["stem"]}')
                    continue
                workflows[workflow_id]['files'].append((file_path, ComponentType.WORKFLOW, where))

            for workflow_id, workflow_dict in workflows.items():
                counts = Counter([_[-1] for _ in workflow_dict['files']])
                self.logger.debug(f'finalizing workflow {workflow_dict["name"]}')
                workflow = Workflow(id=workflow_id,
                                    name=workflow_dict['name'],
                                    purpose=workflow_dict['purpose'],
                                    file_stem=workflow_dict['stem'],
                                    working_dir=str(working_root),
                                    archive_dir=str(archive_root),
                                    relative_path=workflow_dict['relative_path'],
                                    working=counts['w'],
                                    archived=counts['a'],
                                    scan_timestamp=self.timestamp,
                                    components=[Component(file_name=str(file_path.name),
                                                          file_dir=str(file_path.parent),
                                                          component_type=file_type,
                                                          where=where,
                                                          scan_timestamp=self.timestamp)
                                                for file_path, file_type, where in workflow_dict['files']],
                                    scan_errors='')
                with repo.lock:
                    repo.save_scanned_workflow(workflow, workflow_dict['tags'])
                self.report(workflows=1)

        self.logger.debug(f'workflow scan complete in {working_root} and {archive_root}')
        self.barrier.wait()

def match_folders(root_1: Path, root_2: Path, dir_1: Path, sub_dirs: list[str]) -> Path:
    """
    Make sure folders in two branches match
    """
    relative_path = dir_1.relative_to(root_1)
    dir_2 = root_2 / relative_path
    for d in sub_dirs:
        (dir_2 / d).mkdir(exist_ok=True)
    for subdir in (d.name for d in dir_2.iterdir() if d.is_dir()):
        if subdir not in sub_dirs:
            (dir_1 / subdir).mkdir()
            sub_dirs.append(subdir)
    return relative_path

def compute_sha256(path: Path, chunk_size: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()

def ensure_metadata(model_file: Path, metadata_file: Path, rehash: bool, logger: logging.Logger) -> dict:
    if metadata_file.is_file():
        data = json.loads(metadata_file.read_text(encoding='utf-8'))
    else:
        data = {}
    is_changed = False
    if 'sha256' not in data or rehash:
        data['sha256'] = compute_sha256(model_file)
        is_changed = True
    if 'model_name' not in data:
        data['model_name'] = model_file.stem
        is_changed = True
    if 'tags' not in data:
        data['tags'] = []
        is_changed = True
    if is_changed:
        logger.debug(f'updating metadata for {model_file}')
        metadata_file.write_text(json.dumps(data), encoding='utf-8')
    return data

_scanner: Scanner | None = None

def get_scanner(scan_timestamp: str | None = None) -> Scanner | None:
    """
    Return the selected scanner, or return the only scanner.
    """
    global _scanner
    if scan_timestamp is None:
        return _scanner
    if _scanner is None or _scanner.timestamp != scan_timestamp:
        return None
    return _scanner

def create_scanner() -> Scanner | None:
    """
    Create and return a scanner, unless there is one already and it's active.
    """
    global _scanner
    if _scanner is None or _scanner.finished:
        _scanner = Scanner()
        return _scanner
    return None
