# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: file_handler.py
# purpose: Scanning folders and moving file_handler around
# ---------------------------------------------------------------------------

import logging
from typing import Iterable
from pathlib import Path
import hashlib
import json
from itertools import chain
from .object_types import ComponentFileType, ArchivistException, ArchivistError

logger = logging.getLogger('model_archivist')


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


def scan_models(active_root: Path, archive_root: Path, extensions: list[str], rehash: bool) -> Iterable:
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


def scan_workflows(active_root: Path, archive_root: Path) -> Iterable:
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
