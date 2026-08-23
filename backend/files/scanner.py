# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: scanner.py
# purpose: File system scan
# ---------------------------------------------------------------------------

from backend.repository.tables import (Model, Component, ComponentSet, Workflow, ComponentType,
                                       DeploymentStatus, WorkflowError, ModelError)

import logging
from threading import Thread, Lock, Barrier
from pathlib import Path
from uuid import UUID
import hashlib
import json
from itertools import chain
from dataclasses import dataclass, field
import datetime

from backend.config import get_config, Configuration
from backend.files.metadata import (ARCHIVIST_METADATA_SUFFIX,
                                    LEGACY_METADATA_SUFFIX,
                                    scan_model_metadata,
                                    model_component_stem)
import backend.repository.repository as repo


def scanned_component(path: Path, component_type: ComponentType, touched: str,
                      relative_path: str = '') -> Component:
    try:
        stat = path.stat()
        size = stat.st_size
        modified_at_ns = stat.st_mtime_ns
    except OSError:
        size = 0
        modified_at_ns = 0
    return Component(file_name=path.name,
                     relative_path=relative_path,
                     size=size,
                     modified_at_ns=modified_at_ns,
                     component_type=component_type,
                     touched=touched)


@dataclass
class WorkflowCandidate:
    path: Path
    root: Path
    relative_file: Path
    where: str
    workflow_id: str
    name: str
    purpose: str
    tags: list[str]
    errors: set[WorkflowError] = field(default_factory=set)


def read_workflow_candidate(path: Path, root: Path, where: str) -> WorkflowCandidate | None:
    """Return UUID-bearing workflow metadata, or None when the file is not a workflow."""
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data, dict) or not isinstance(data.get('id'), str):
            return None
        workflow_id = str(UUID(data['id']))
    except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError):
        return None

    errors = set()
    config = data.get('config', {})
    if not isinstance(config, dict):
        config = {}
        errors.add(WorkflowError.INVALID_CONFIG)

    name = config.get('name', path.stem)
    purpose = config.get('purpose', '')
    tags = config.get('tags', [])
    if not isinstance(name, str):
        name = path.stem
        errors.add(WorkflowError.INVALID_CONFIG)
    if not isinstance(purpose, str):
        purpose = ''
        errors.add(WorkflowError.INVALID_CONFIG)
    if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
        tags = []
        errors.add(WorkflowError.INVALID_CONFIG)

    return WorkflowCandidate(path=path,
                             root=root,
                             relative_file=path.relative_to(root),
                             where=where,
                             workflow_id=workflow_id,
                             name=name,
                             purpose=purpose,
                             tags=tags,
                             errors=errors)


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

        if self.config.workflow_folders:
            threads.append(Thread(target=self.find_workflows, args=(self.config.workflow_folders,)))

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
            self.end_time = datetime.datetime.now(tz=datetime.timezone.utc)
            self.finished = True
        self.logger.debug(f'completed filesystem scan')

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


        def get_metadata(model_filename: str, model_dir: Path) -> tuple[str, dict, bool, bool]:
            """
            Read Archivist metadata, importing legacy metadata on first use.
            """
            model_file = model_dir / model_filename
            md_file = model_file.with_suffix(ARCHIVIST_METADATA_SUFFIX)
            self.logger.debug(f'updating metadata for {model_file}')
            scanned = scan_model_metadata(model_file, rehash)
            return md_file.name, scanned.data, scanned.unreadable, scanned.hash_calculated

        def assemble_set(data: dict, primary_dir: Path, ex_root: Path, where: str) \
                -> tuple[dict | None, set[ModelError], ComponentSet]:
            """
            Turn a list of files into a component set.
            """
            if where in data:
                flist = data[where]
            else:
                return None, set(), ComponentSet(where=where,
                                          primary_dir=primary_dir.as_posix(),
                                          components=[])
            components = []
            model_names = []
            errors = set()
            for component_type, file_name in flist:
                components.append(scanned_component(primary_dir / file_name,
                                                    component_type,
                                                    self.timestamp))
                try:
                    with (primary_dir / file_name).open('rb') as component_file:
                        component_file.read(1)
                except OSError:
                    errors.add(ModelError.UNREADABLE)
                if component_type == ComponentType.MODEL:
                    model_names.append(file_name)
            if not model_names:
                return None, set(), ComponentSet(where=where,
                                          primary_dir=primary_dir.as_posix(),
                                          components=components)

            if len(model_names) > 1:
                errors.add(ModelError.AMBIGUOUS_STEM)
            model_name = model_names[0]
            try:
                metadata_filename, metadata, unreadable, hash_calculated = get_metadata(model_name, primary_dir)
            except OSError as error:
                self.report(error=f'unreadable model file {primary_dir / model_name}: {error}')
                return None, {ModelError.UNREADABLE}, ComponentSet(
                    where=where, primary_dir=primary_dir.as_posix(), components=components)
            if unreadable:
                errors.add(ModelError.UNREADABLE)
            if hash_calculated:
                self.report(hashes=1)
            if where == 'w' and metadata.get('file_name') != Path(model_name).stem:
                errors.add(ModelError.METADATA_RENAME)

            if not any(c.file_name == metadata_filename for c in components):
                components.append(scanned_component(primary_dir / metadata_filename,
                                                    ComponentType.METADATA,
                                                    self.timestamp))
            sha = metadata['sha256']
            ex_dir = ex_root / sha
            if ex_dir.is_dir():
                try:
                    example_files = [path for path in ex_dir.iterdir() if path.is_file()]
                except OSError:
                    errors.add(ModelError.UNREADABLE)
                    example_files = []
                for ex in example_files:
                    components.append(scanned_component(ex, ComponentType.EXAMPLE,
                                                        self.timestamp))
                    try:
                        with ex.open('rb') as example_file:
                            example_file.read(1)
                    except OSError:
                        errors.add(ModelError.UNREADABLE)
            return metadata, errors, ComponentSet(where=where,
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
            return meta_2, None

        def file_format(*component_sets: ComponentSet) -> str:
            for component_set in component_sets:
                for component in component_set.components:
                    if component.component_type == ComponentType.MODEL:
                        return Path(component.file_name).suffix.lower().removeprefix('.')
            return ''

        for working_dir, subdirs, filenames in working_root.walk():
            relative_path = str(match_folders(working_root, archive_root, working_dir, subdirs))
            archive_dir = archive_root / relative_path

            found = {}

            # first collect all model and sidecar files
            self.logger.debug(f'current dir {working_dir}')
            for file_path, where in chain(((working_dir / fn, 'w') for fn in filenames),
                                          ((f.resolve(), 'a') for f in archive_dir.iterdir() if f.is_file())):
                stem = model_component_stem(file_path)
                c_type = (ComponentType.MODEL if file_path.suffix in self.config.model_extensions else
                          ComponentType.METADATA if file_path.name.endswith(ARCHIVIST_METADATA_SUFFIX) else
                          ComponentType.EXTRA)
                found.setdefault(stem, {}).setdefault(where, []).append((c_type, file_path.name))

            # then assemble the models and save them
            for stem, data in found.items():
                working_md, working_errors, working_set = assemble_set(data, working_dir, working_examples, 'w')
                archive_md, archive_errors, archive_set = assemble_set(data, archive_dir, archive_examples, 'a')
                metadata, err = reconcile_metadata(archive_md, working_md)
                if err == 'mismatched sha256':
                    for side_metadata, side_errors, present_set, absent_set in (
                        (working_md, working_errors, working_set, archive_set),
                        (archive_md, archive_errors, archive_set, working_set),
                    ):
                        if side_metadata is None:
                            continue
                        conflict_errors = side_errors | {ModelError.PATH_IDENTITY_CONFLICT}
                        conflict_model = Model(
                            id=side_metadata['sha256'],
                            file_name=side_metadata['file_name'],
                            internal_name=side_metadata['model_name'],
                            type=type_name,
                            file_format=file_format(present_set),
                            relative_path=relative_path,
                            deployment=str(DeploymentStatus.WORKING if present_set.where == 'w'
                                           else DeploymentStatus.ARCHIVE),
                            touched=self.timestamp,
                            errors=[error.value for error in ModelError if error in conflict_errors],
                            component_sets=[present_set, ComponentSet(
                                where=absent_set.where,
                                primary_dir=absent_set.primary_dir,
                                components=[])])
                        with repo.lock:
                            repo.save_scanned_model(conflict_model, side_metadata['tags'])
                        self.report(models=1)
                    continue
                if not metadata:
                    m = f'metadata for model {stem} has {err}, skipping'
                    self.logger.error(m)
                    self.report(error=m)
                    continue

                model = Model(id=metadata['sha256'],
                              file_name=metadata['file_name'],
                              internal_name=metadata['model_name'],
                              type=type_name,
                              file_format=file_format(working_set, archive_set),
                              relative_path=relative_path,
                              deployment=str(check_deployment(working_set, archive_set)),
                              touched=self.timestamp,
                              errors=[error.value for error in ModelError
                                      if error in working_errors | archive_errors],
                              component_sets = [working_set, archive_set])

                with repo.lock:
                    repo.save_scanned_model(model, metadata['tags'])
                self.report(models=1)
        self.logger.debug(f'scan for {type_name} complete in {working_root} and {archive_root}')
        self.barrier.wait()

    def find_workflows(self, folder_pairs: list[tuple[Path, Path]]):
        """Scan and reconcile workflows by UUID across every configured folder pair."""
        grouped: dict[str, list[WorkflowCandidate]] = {}
        for working_root, archive_root in folder_pairs:
            for root, where in ((working_root, 'w'), (archive_root, 'a')):
                self.logger.debug(f'scanning workflows in {root}')
                for path in sorted(root.rglob('*'), key=str):
                    if not path.is_file() or path.suffix.lower() != '.json':
                        continue
                    candidate = read_workflow_candidate(path, root, where)
                    if candidate is None:
                        self.logger.debug(f'ignoring non-workflow JSON file {path}')
                        continue
                    grouped.setdefault(candidate.workflow_id, []).append(candidate)

        error_order = list(WorkflowError)
        for workflow_id, candidates in grouped.items():
            working = [candidate for candidate in candidates if candidate.where == 'w']
            archive = [candidate for candidate in candidates if candidate.where == 'a']
            errors = set().union(*(candidate.errors for candidate in candidates))
            if len(working) > 1:
                errors.add(WorkflowError.DUPLICATE_WORKING)
            if len(archive) > 1:
                errors.add(WorkflowError.DUPLICATE_ARCHIVE)
            if working and archive:
                working_locations = {candidate.relative_file.as_posix() for candidate in working}
                archive_locations = {candidate.relative_file.as_posix() for candidate in archive}
                if working_locations != archive_locations:
                    errors.add(WorkflowError.LOCATION_MISMATCH)

            selected = working[0] if working else archive[0]
            grouped_components: dict[tuple[str, Path], list[Component]] = {}
            for candidate in candidates:
                relative_parent = candidate.relative_file.parent.as_posix()
                if relative_parent == '.':
                    relative_parent = ''
                component = scanned_component(candidate.path,
                                              ComponentType.WORKFLOW,
                                              self.timestamp,
                                              relative_parent)
                grouped_components.setdefault((candidate.where, candidate.root), []).append(component)
            component_sets = [
                ComponentSet(where=where,
                             primary_dir=root.as_posix(),
                             components=components)
                for (where, root), components in grouped_components.items()
            ]
            deployment = (DeploymentStatus.SYNCED if working and archive else
                          DeploymentStatus.WORKING if working else DeploymentStatus.ARCHIVE)
            relative_parent = selected.relative_file.parent.as_posix()
            if relative_parent == '.':
                relative_parent = ''
            workflow = Workflow(id=workflow_id,
                                internal_name=selected.name,
                                file_name=selected.path.stem,
                                purpose=selected.purpose,
                                relative_path=relative_parent,
                                deployment=str(deployment),
                                touched=self.timestamp,
                                errors=[error.value for error in error_order if error in errors],
                                component_sets=component_sets)
            with repo.lock:
                repo.save_scanned_workflow(workflow, selected.tags)
            self.report(workflows=1)

        self.logger.debug('workflow scan complete')
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
    config = get_config()
    if config.read_only:
        return None
    if _scanner is None or _scanner.finished:
        _scanner = Scanner()
        return _scanner
    return None
