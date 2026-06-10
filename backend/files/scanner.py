# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: scanner.py
# purpose: File system scan
# ---------------------------------------------------------------------------

from backend.repository.tables import Model, Component, ComponentSet, Workflow, ComponentType, DeploymentStatus

import logging
from threading import Thread, Lock, Barrier
from pathlib import Path
import hashlib
import json
from itertools import chain
from dataclasses import dataclass, field
import datetime

from backend.config import get_config, Configuration
import backend.repository.repository as repo


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
        Scan a directory with subdirectories and records for all models found.
        The active and archive directories are scanned in parallel.
            - Model files in archive and active folders match by hash, but they must also match by filename.
            - Extra files are matched by file stem.
            - Examples are located in a folder named by model hash in the examples branch.
        """
        self.logger.debug(f'starting scan for {type_name} in {working_root} and {archive_root}')
        working_examples = working_root.parent / 'examples'
        archive_examples = archive_root.parent / 'examples'


        def get_metadata(model_filename: str, meta_name: str | None, model_dir: Path) -> tuple[str, dict]:
            """
            Get a model's metadata, whether or not it exists
            """
            model_file = model_dir / model_filename
            if meta_name is None:
                md_file = model_file.with_suffix('.metadata.json')
                data = {'sha256': compute_sha256(model_file),
                        'model_name': model_file.stem,
                        'file_name': model_file.stem,
                        'tags': []}
            else:
                md_file = model_dir / meta_name
                data = json.loads(md_file.read_text(encoding='utf-8'))
                if 'sha256' not in data:
                    data['sha256'] = compute_sha256(model_file),
                data.setdefault('model_name', model_file.stem)
                data.setdefault('file_name', model_file.stem)
            self.logger.debug(f'updating metadata for {model_file}')
            md_file.write_text(json.dumps(data), encoding='utf-8')
            return md_file.name, data

        def assemble_set(data: dict, primary_dir: Path, ex_root: Path, where: str) \
                -> tuple[dict | None, ComponentSet]:
            """
            Turn a list of files into a component set.
            """
            if where in data:
                flist = data[where]
            else:
                return None, ComponentSet(where=where,
                                          primary_dir=primary_dir.as_posix(),
                                          components=[])
            components = []
            model_name = meta_name = None
            for component_type, file_name in flist:
                components.append(Component(file_name=file_name,
                                            component_type=component_type,
                                            touched=self.timestamp))
                if component_type == ComponentType.MODEL:
                    model_name = file_name
                if component_type == ComponentType.METADATA:
                    meta_name = file_name
            if model_name is None:
                return None, ComponentSet(where=where,
                                          primary_dir=primary_dir.as_posix(),
                                          components=components)

            metadata_filename, metadata = get_metadata(model_name, meta_name, primary_dir)

            if meta_name is None:
                components.append(Component(file_name=metadata_filename,
                                            component_type=ComponentType.METADATA,
                                            touched=self.timestamp))
            sha = metadata['sha256']
            ex_dir = ex_root / sha
            if ex_dir.is_dir():
                for ex in ex_dir.iterdir():
                    components.append(Component(file_name=ex.name,
                                                component_type=ComponentType.EXAMPLE,
                                                touched=self.timestamp))
            return metadata, ComponentSet(where=where,
                                        primary_dir=primary_dir.as_posix(),
                                        examples_dir=ex_dir.as_posix(),
                                        components=components)

        def reconcile_metadata(meta_1: dict, meta_2: dict) -> tuple[dict | None, str | None]:
            """
            Check it two versions of metadata are consistent.
            """
            if meta_2 is None:
                return meta_1, None
            if meta_1 is None:
                return meta_2, None
            if meta_1['sha256'] != meta_2['sha256']:
                return None, 'mismatched sha256'
            if meta_1['model_name'] != meta_2['model_name']:
                return None, 'mismatched model name'
            if meta_1['tags'] != meta_2['tags']:
                return None, 'mismatched tags'
            return meta_2, None

        for working_dir, subdirs, filenames in working_root.walk():
            relative_path = str(match_folders(working_root, archive_root, working_dir, subdirs))
            archive_dir = archive_root / relative_path

            found = {}

            # first collect all model and sidecar files
            self.logger.debug(f'current dir {working_dir}')
            for file_path, where in chain(((working_dir / fn, 'w') for fn in filenames),
                                          ((f.resolve(), 'a') for f in archive_dir.iterdir() if f.is_file())):
                stem = file_path.stem.replace('.metadata','')
                c_type = (ComponentType.MODEL if file_path.suffix in self.config.model_extensions else
                          ComponentType.METADATA if file_path.name.endswith('.metadata.json') else
                          ComponentType.EXTRA)
                found.setdefault(stem, {}).setdefault(where, []).append((c_type, file_path.name))

            # then assemble the models and save them
            for stem, data in found.items():
                working_md, working_set = assemble_set(data, working_dir, working_examples, 'w')
                archive_md, archive_set = assemble_set(data, archive_dir, archive_examples, 'a')
                metadata, err = reconcile_metadata(archive_md, working_md)
                if not metadata:
                    m = f'metadata for model {stem} has {err}, skipping'
                    self.logger.error(m)
                    self.report(error=m)
                    continue

                model = Model(id=metadata['sha256'],
                              file_name=metadata['file_name'],
                              internal_name=metadata['model_name'],
                              type=type_name,
                              relative_path=relative_path,
                              deployment=str(check_deployment(working_set, archive_set)),
                              touched=self.timestamp,
                              component_sets = [working_set, archive_set])

                with repo.lock:
                    repo.save_scanned_model(model, metadata['tags'])
                self.report(models=1)
        self.logger.debug(f'scan for {type_name} complete in {working_root} and {archive_root}')
        self.barrier.wait()

    def find_workflows(self, working_root: Path, archive_root: Path):
        """
        Scan archive and working directories and create records for all workflows found.
        """

        def normalize_workflow(wf_file: Path) -> dict | None:
            if wf_file is None:
                return None
            json_data = json.loads(wf_file.read_text(encoding='utf-8'))
            if 'id' not in json_data or 'revision' not in json_data or 'version' not in json_data:
                m = f'{wf_file} does not contain a valid workflow'
                self.logger.warning(m)
                self.report(error=m)
                return None
            else:
                conf = json_data.setdefault('config', {})
                conf.setdefault('name', wf_file.stem)
                conf.setdefault('purpose', '')
                conf.setdefault('tags', [])
            return json_data

        def reconcile_workflows(working_file: Path, archive_file: Path) -> dict | None:
            working = normalize_workflow(working_file)
            archive = normalize_workflow(archive_file)
            if working is None:
                if archive is None:
                    return None
                use = archive
            else:
                use = working
                if archive is not None:
                    if archive['id'] != working['id']:
                        m = f'archive and working workflows for {working_file.name} have different ids'
                        self.logger.warning(m)
                        self.report(error=m)
                        return None
                    archive['config']['name'] = working['config']['name']
                    if len(working['config']['purpose']) > 0:
                        archive['config']['purpose'] = working['config']['purpose']
                    if len(working['config']['tags']) > 0:
                        archive['config']['tags'] = [t for t in working['config']['tags']]
            if working is not None:
                working_file.write_text(json.dumps(working), encoding='utf-8')
            if archive is not None:
                archive_file.write_text(json.dumps(archive), encoding='utf-8')
            return use

        self.logger.debug(f'starting workflow scan in {working_root} and {archive_root}')
        for working_dir, subdirs, filenames in working_root.walk():
            relative_path = str(match_folders(working_root, archive_root, working_dir, subdirs))
            archive_dir = archive_root / relative_path
            workflows = {}
            for file_path, where in chain(((working_dir / fn, 'w') for fn in filenames),
                                            ((f.resolve(), 'a') for f in archive_dir.iterdir() if f.is_file())):
                if file_path.suffix != '.json':
                    self.logger.debug(f'ignoring {str(file_path)}')
                    continue
                stem = file_path.stem
                workflows.setdefault(stem, {})[where] = file_path.name
            for stem, wf_dict in workflows.items():
                self.logger.debug(f'finalizing workflow {stem}')

                file_name = wf_dict['w'] if 'w' in wf_dict else wf_dict['a']
                data = reconcile_workflows(working_dir / file_name if 'w' in wf_dict else None,
                                           archive_dir / file_name if 'a' in wf_dict else None)
                if data is None:
                    continue
                working_set = ComponentSet(where='w',
                                           primary_dir=working_dir.as_posix(),
                                           components=[Component(file_name=wf_dict['w'],
                                                                 component_type=ComponentType.WORKFLOW,
                                                                 touched = self.timestamp)] if 'w' in wf_dict else[])
                archive_set = ComponentSet(where='a',
                                           primary_dir=archive_dir.as_posix(),
                                           components=[Component(file_name=wf_dict['a'],
                                                                 component_type=ComponentType.WORKFLOW,
                                                                 touched = self.timestamp)] if 'a' in wf_dict else[])

                workflow = Workflow(id=data['id'],
                                    internal_name=data['config']['name'],
                                    file_name= stem,
                                    purpose=data['config']['purpose'],
                                    relative_path=relative_path,
                                    deployment=check_deployment(working_set, archive_set),
                                    touched=self.timestamp,
                                    component_sets=[working_set, archive_set])
                with repo.lock:
                    repo.save_scanned_workflow(workflow, data['config']['tags'])
                self.report(workflows=1)

        self.logger.debug(f'workflow scan complete in {working_root} and {archive_root}')
        self.barrier.wait()

def check_deployment(working_set: ComponentSet, archive_set: ComponentSet) -> DeploymentStatus:
    """
    check if the deployment sets are matched
    """
    if len(working_set.components) == 0:
        return DeploymentStatus.ARCHIVE
    elif len(archive_set.components) == 0:
        return DeploymentStatus.WORKING
    if len(working_set.components) != len(archive_set.components):
        return DeploymentStatus.MISMATCH
    working = {(c.file_name, c.component_type) for c in working_set.components}
    archive = {(c.file_name, c.component_type) for c in archive_set.components}
    if len(working ^ archive) != 0:
        return DeploymentStatus.MISMATCH
    return DeploymentStatus.SYNCED

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
