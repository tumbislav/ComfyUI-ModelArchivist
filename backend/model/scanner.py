# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: scanner.py
# purpose: File system scan
# ---------------------------------------------------------------------------

from backend.db.tables import Model, Component

import uuid
import logging
from enum import StrEnum
from threading import Thread, Lock, Barrier
from pathlib import Path
import hashlib
import json
from itertools import chain
from typing import Iterable
from dataclasses import dataclass, field

from .object_types import ComponentFileType, ArchivistException, ArchivistError
from backend.config import get_config
from backend.db.repository import lock as repo_lock, save_model, cleanup

logger = logging.getLogger('model_archivist')


class ScanStatus(StrEnum):
    INACTIVE = 'inactive'
    RUNNING = 'scanning'
    CLEANUP = 'completed'
    ERROR = 'error'

@dataclass
class ScanStatus:
    id: str | None = None

    status: ScanStatus = ScanStatus.INACTIVE
    models_scanned: int = 0
    workflows_scanned: int = 0
    hashes_calculated: int = 0
    errors: list[str] = field(default_factory=list)


class Scanner:
    def __init__(self):
        self.id: str | None = None
        self.status: ScanStatus | None = None
        self.status_lock = Lock()

    def start(self, rehash: bool = False) -> str | None:
        config = get_config()
        with self.status_lock:
            status = self.status

        if status != ScanStatus.INACTIVE:
            return None

        with self.status_lock:
            self.status = ScanStatus.RUNNING
            self.id = str(uuid.uuid1())

        model_args = [(name, active, archive, rehash)
                      for name, locations in config.model_folders.items()
                      for active, archive in locations]
        workflow_args = [(active, archive) for active, archive in config.workflow_folders]
        total_threads = len(model_args) + len(workflow_args) + 1
        barrier = Barrier(total_threads)

        for ma in model_args:
            Thread(target=self.scan_models, args=(barrier, *ma)).start()
        for wa in workflow_args:
            Thread(target=self.scan_workflows, args=(barrier, *wa)).start()
        Thread(target=self.cleanup, args=(barrier,)).start()
        for name, active, archive, rehash in model_args:
            self.scan_models(barrier, name, active, archive, rehash)
        self.cleanup(barrier)

        return self.id

    def scan_status(self):
        pass

    def scan_models(self, barrier: Barrier, type_name: str, active: Path, archive: Path, rehash: bool):
        logger.info(f'Scanner.scan_models: {self.id} starting scan for {type_name} in {active} and {archive}')
        extensions = get_config().models.extensions
        for model_dict in find_models(active, archive, extensions, rehash):
            archive_count = sum(1 if is_archive else 0 for fn, ft, is_archive in model_dict['files'])
            logger.info(f'Scanner: located model {model_dict["name"]}')
            model = Model(hash=model_dict['hash'],
                          name=model_dict['name'],
                          relative_path=model_dict['relative_path'],
                          type=type_name,
                          active_type_dir=str(active),
                          archive_type_dir=str(archive),
                          is_archived=archive_count > 0,
                          is_active=archive_count < len(model_dict['files']),
                          last_scan_id=self.id,
                          components=[Component(file_name=str(file_path.name),
                                                file_dir=str(file_path.parent),
                                                component_type=file_type,
                                                is_archive=is_archive,
                                                last_scan_id=self.id)
                                      for file_path, file_type, is_archive in model_dict['files']],
                          scan_errors='')
            with repo_lock:
                save_model(model, model_dict['tags'])
        logger.info(f'Scanner.scan_models: {self.id} ending scan for {type_name} in {active} and {archive}')
        barrier.wait()

    def scan_workflows(self, barrier: Barrier, active: Path, archive: Path):
        logger.info(f'{self.id} starting workflow scan')
        for workflow_dict in find_workflows(active, archive):
            pass

        logger.info(f'{self.id} ending workflow scan')
        barrier.wait()

    def cleanup(self, barrier: Barrier):
        barrier.wait()
        with self.status_lock:
            self.status = ScanStatus.CLEANUP
        logger.info(f'{self.id} starting cleanup')
        with repo_lock:
            cleanup(self.id)
        with self.status_lock:
            self.status = ScanStatus.INACTIVE
        logger.info(f'{self.id} done')


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


def find_models(active_root: Path, archive_root: Path, extensions: list[str], rehash: bool) -> Iterable:
    """
    Scan a directory with subdirectories and return all model and sidecar files found.
    The active and archive directories are scanned in parallel.
    """
    active_examples = active_root.parent / 'examples'
    archive_examples = archive_root.parent / 'examples'

    logger.info(f'FileHandler.scan_models: scanning from {active_root}')
    for active_dir, subdirs, filenames in active_root.walk():
        relative_path = match_folders(active_root, archive_root, active_dir, subdirs)
        archive_dir = archive_root / relative_path

        # Make a list of all files. Model files in archive and active folders match by hash, but they
        # must also match by filename. Extra files are matched by file stem, examples also by hash, but they
        # are in a different branch of the directory tree.
        models = {}
        others = {}

        logger.info(f'FileHandler.scan_models: current dir {active_dir}')
        for file_path, is_archive in chain(((active_dir / fn, False) for fn in filenames),
                                           ((f.resolve(), True) for f in archive_dir.iterdir() if f.is_file())):
            stem = file_path.stem
            if file_path.suffix in extensions:
                metadata_file = file_path.with_suffix('.metadata.json')
                metadata = ensure_metadata(file_path, metadata_file, rehash)
                model_hash = metadata['sha256']
                if model_hash not in models:
                    models[model_hash] = {'stem': stem,
                                          'hash': model_hash,
                                          'name': metadata.get('model_name', stem),
                                          'tags': metadata.get('tags', []),
                                          'relative_path': str(relative_path),
                                          'files': []}
                elif models[model_hash]['stem'] != stem:
                    raise ArchivistException(ArchivistError.INCONSISTENT_FILENAME, str(file_path))
                models[model_hash]['files'].append((file_path, ComponentFileType.MODEL, is_archive))
                models[model_hash]['files'].append((metadata_file, ComponentFileType.METADATA, is_archive))
            elif not file_path.name.endswith('.metadata.json'):
                if stem not in others:
                    others[stem] = [(file_path, ComponentFileType.EXTRA, is_archive)]
                else:
                    others[stem].append((file_path, ComponentFileType.EXTRA, is_archive))

        # Complete and return all models collected
        for model_hash, model_dict in models.items():
            stem = model_dict['stem']
            logger.info(f'FileHandler.scan_models: finalizing model {stem}')
            if stem in others:
                for file_path, component_type, is_archive in others[stem]:
                    model_dict['files'].append((file_path, component_type, is_archive))
            examples_dir = active_examples / model_hash
            if examples_dir.is_dir():
                for example in examples_dir.iterdir():
                    model_dict['files'].append((example.resolve(), ComponentFileType.EXAMPLE, False))
            examples_dir = archive_examples / model_hash
            if examples_dir.is_dir():
                for example in examples_dir.iterdir():
                    model_dict['files'].append((example.resolve(), ComponentFileType.EXAMPLE, True))

            yield model_dict


def find_workflows(active_root: Path, archive_root: Path) -> Iterable:
    logger.info(f'FileHandler.scan_workflows: scanning from {active_root}')
    for active_dir, subdirs, filenames in active_root.walk():
        relative_path = match_folders(active_root, archive_root, active_dir, subdirs)
        archive_dir = archive_root / relative_path
        workflows = {}
        for file_path, is_archive in chain(((active_dir / fn, False) for fn in filenames),
                                           ((f.resolve(), True) for f in archive_dir.iterdir() if f.is_file())):
            stem = file_path.stem
            if file_path.suffix in ('json',):
                data = json.loads(file_path.read_text(encoding='utf-8'))
                # sanity check that this is a workflow file
                if 'id' not in data or 'revision' not in data or 'version' not in data:
                    continue
                model_id = data['id']
                conf = data['config'] if 'config' in data else {}
                name = conf['name'] if 'name' in conf else stem
                tags = conf['tags'] if 'tags' in conf else []
                if model_id not in workflows:
                    workflows[model_id] = {'stem': stem,
                                           'id': model_id,
                                           'name': name,
                                           'tags': tags,
                                           'relative_path': str(relative_path),
                                           'files': []}


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
        logger.info(f'Updating metadata for {model_file}')
        metadata_file.write_text(json.dumps(data), encoding='utf-8')
    return data

_scanner: Scanner | None = None

def get_scanner():
    global _scanner
    if _scanner is None:
        _scanner = Scanner()
    return _scanner
