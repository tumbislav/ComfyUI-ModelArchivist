# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: scanner.py
# purpose: File system scan
# ---------------------------------------------------------------------------

from backend.db.tables import Model, Component, Workflow

import uuid
import logging
from threading import Thread, Lock, Barrier
from pathlib import Path
import hashlib
import json
from itertools import chain
from dataclasses import dataclass, field

from .object_types import ComponentFileType
from backend.config import get_config, Configuration
from backend.db.repository import lock as db_lock, save_model, save_workflow, cleanup as db_cleanup


@dataclass
class Scanner:
    uid: str | None = None #todo: change to timestamp!
    started: bool = False
    finished: bool = False
    models_scanned: int = 0
    workflows_scanned: int = 0
    hashes_calculated: int = 0
    errors: list[str] = field(default_factory=list)
    lock: Lock = Lock()
    barrier: Barrier | None = None
    config: Configuration | None = None

    def start(self, rehash: bool = False) -> str | None:
        if self.started:
            _logger.error(f'attempting to start an already started scanner')
            return None
        self.config = get_config()
        _logger.debug(f'starting scan with rehash={rehash}')

        self.started = True
        self.uid = str(uuid.uuid1())

        threads = []
        for name, locations in self.config.model_folders.items():
            for active, archive in locations:
                threads.append(Thread(target=self.find_models, args=(name, active, archive, rehash)))

        for active, archive in self.config.workflow_folders:
            threads.append(Thread(target=self.find_workflows, args=(active, archive)))

        threads.append(Thread(target=self.cleanup, args=tuple()))
        self.barrier = Barrier(len(threads))

        _logger.debug(f'creating {len(threads)} worker threads')
        for thread in threads:
            thread.start()
        return self.uid

    def report(self, models: int=0, workflows: int=0, hashes: int=0, error: str=''):
        with self.lock:
            self.models_scanned += models
            self.workflows_scanned += workflows
            self.hashes_calculated += hashes
            if error != '':
                self.errors.append(error)

    def cleanup(self):
        self.barrier.wait()
        _logger.debug(f'starting cleanup')
        with db_lock:
            db_cleanup(self.uid)
        with self.lock:
            self.finished = True
        _logger.debug(f'completed filesystem scan')

    def find_models(self, type_name: str, active_root: Path, archive_root: Path, rehash: bool):
        """
        Scan a directory with subdirectories and return all model and sidecar files found.
        The active and archive directories are scanned in parallel.
        """
        _logger.debug(f'starting scan for {type_name} in {active_root} and {archive_root}')
        active_examples = active_root.parent / 'examples'
        archive_examples = archive_root.parent / 'examples'

        for active_dir, subdirs, filenames in active_root.walk():
            relative_path = match_folders(active_root, archive_root, active_dir, subdirs)
            archive_dir = archive_root / relative_path

            # Make a list of all files.
            # - Model files in archive and active folders match by hash, but they must also match by filename.
            # - Extra files are matched by file stem.
            # - Examples are located in a folder named hash in the examples branch.
            models = {}
            sidecars = {}

            # first collect all model and sidecar files
            _logger.debug(f'current dir {active_dir}')
            for file_path, is_archive in chain(((active_dir / fn, False) for fn in filenames),
                                               ((f.resolve(), True) for f in archive_dir.iterdir() if f.is_file())):
                stem = file_path.stem
                if file_path.suffix in self.config.model_extensions:
                    metadata_file = file_path.with_suffix('.metadata.json')
                    metadata = ensure_metadata(file_path, metadata_file, rehash)
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
                    models[sha256]['files'].append((file_path, ComponentFileType.MODEL, is_archive))
                    models[sha256]['files'].append((metadata_file, ComponentFileType.METADATA, is_archive))
                elif not file_path.name.endswith('.metadata.json'):
                    if stem not in sidecars:
                        sidecars[stem] = [(file_path, ComponentFileType.EXTRA, is_archive)]
                    else:
                        sidecars[stem].append((file_path, ComponentFileType.EXTRA, is_archive))

            # Assemble and save all models found
            for sha256, model_dict in models.items():
                stem = model_dict['stem']
                _logger.debug(f'finalizing model {stem}')
                files = model_dict['files']

                if stem in sidecars:
                    for file_path, component_type, is_archive in sidecars[stem]:
                        files.append((file_path, component_type, is_archive))
                examples_dir = active_examples / sha256
                if examples_dir.is_dir():
                    for example in examples_dir.iterdir():
                        files.append((example.resolve(), ComponentFileType.EXAMPLE, False))
                examples_dir = archive_examples / sha256
                if examples_dir.is_dir():
                    for example in examples_dir.iterdir():
                        files.append((example.resolve(), ComponentFileType.EXAMPLE, True))

                archive_count = sum(1 for fn, ft, is_archive in files if is_archive)
                _logger.debug(f'found model {model_dict["name"]} in {model_dict["relative_path"]}')
                model = Model(id=model_dict['id'],
                              name=model_dict['name'],
                              relative_path=model_dict['relative_path'],
                              type=type_name,
                              active_type_dir=str(active_root),
                              archive_type_dir=str(archive_root),
                              is_archived=archive_count > 0,
                              is_active=archive_count < len(files),
                              last_scan_id=self.uid,
                              components=[Component(file_name=str(file_path.name),
                                                    file_dir=str(file_path.parent),
                                                    component_type=file_type,
                                                    is_archive=is_archive,
                                                    last_scan_id=self.uid)
                                          for file_path, file_type, is_archive in files],
                              scan_errors='')
                with db_lock:
                    save_model(model, model_dict['tags'])
                self.report(models=1)
        _logger.debug(f'scan for {type_name} complete in {active_root} and {archive_root}')
        self.barrier.wait()

    def find_workflows(self, active_root: Path, archive_root: Path):
        _logger.debug(f'starting workflow scan in {active_root} and {archive_root}')
        for active_dir, subdirs, filenames in active_root.walk():
            relative_path = match_folders(active_root, archive_root, active_dir, subdirs)
            archive_dir = archive_root / relative_path
            workflows = {}
            for file_path, is_archive in chain(((active_dir / fn, False) for fn in filenames),
                                               ((f.resolve(), True) for f in archive_dir.iterdir() if f.is_file())):
                if file_path.suffix != '.json':
                    _logger.debug(f'ignoring {str(file_path)}')
                    continue
                stem = file_path.stem
                data = json.loads(file_path.read_text(encoding='utf-8'))
                # sanity check that this is a workflow file
                if 'id' not in data or 'revision' not in data or 'version' not in data:
                    _logger.warning(f'{file_path} does not contain a valid workflow')
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
                workflows[workflow_id]['files'].append((file_path, ComponentFileType.WORKFLOW, is_archive))
            for workflow_id, workflow_dict in workflows.items():
                _logger.debug(f'finalizing workflow {workflow_dict["name"]}')
                workflow = Workflow(id=workflow_id,
                                    name=workflow_dict['name'],
                                    purpose=workflow_dict['purpose'],
                                    file_stem=workflow_dict['stem'],
                                    relative_path=workflow_dict['relative_path'],
                                    is_archived=any(is_archive for is_archive in workflow_dict['files']),
                                    is_active=any(not is_archive for is_archive in workflow_dict['files']),
                                    last_scan_id=self.uid,
                                    components=[Component(file_name=str(file_path.name),
                                                          file_dir=str(file_path.parent),
                                                          component_type=file_type,
                                                          is_archive=is_archive,
                                                          last_scan_id=self.uid)
                                                for file_path, file_type, is_archive in workflow_dict['files']],
                                    scan_errors='')
                with db_lock:
                    save_workflow(workflow, workflow_dict['tags'])
                self.report(workflows=1)

        _logger.debug(f'workflow scan complete in {active_root} and {archive_root}')
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

def ensure_metadata(model_file: Path, metadata_file: Path, rehash: bool) -> dict:
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
        _logger.debug(f'updating metadata for {model_file}')
        metadata_file.write_text(json.dumps(data), encoding='utf-8')
    return data

_scanner: Scanner | None = None
_logger: logging.Logger | None = None

def create_scanner() -> Scanner | None:
    global _scanner
    global _logger
    _logger = logging.getLogger('archivist.files')
    if _scanner is None or _scanner.finished:
        _scanner = Scanner()
        return _scanner
    _logger.info(f'scanner {_scanner.uid} still active, new instance not created')
    return None
