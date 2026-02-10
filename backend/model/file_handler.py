# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: file_handler.py
# purpose: Scanning folders and moving file_handler around
# ---------------------------------------------------------------------------

import logging
from typing import Iterable
from pathlib import Path
from itertools import chain
from backend.config import Configuration
from .file_utils import ensure_metadata
from .object_types import ComponentType, ArchivistException, ArchivistError


logger = logging.getLogger('model_archivist')


class FileHandler:
    """
    Locates and moves files
    """
    def __init__(self, config: Configuration) -> None:
        self.config = config

    def scan_models(self, active_root: Path, archive_root: Path) -> Iterable:
        """
        Scan a directory with subdirectories and return all model and sidecar files found.
        The active and archive directories are scanned in parallel.
        """
        active_examples = active_root.parent / 'examples'
        archive_examples = archive_root.parent / 'examples'

        logger.info(f'FileHandler.scan_models: scanning level 1 {active_root}')
        for active_dir, subdirs, filenames in active_root.walk():
            # make sure the archive and active trees are equal
            relative_path = str(active_dir.relative_to(active_root))
            archive_dir = archive_root / relative_path
            for d in subdirs:
                (archive_dir / d).mkdir(exist_ok=True)
            for subdir in (d.name for d in archive_dir.iterdir() if d.is_dir()):
                if subdir not in subdirs:
                    (active_dir / subdir).mkdir()
                    subdirs.append(subdir)

            # Make a list of all files. Model files in archive and active folders match by hash, but they
            # must also match by filename. Extra files are matched by file stem, examples also by hash, but they
            # are in a different branch of the directory tree.
            models = {}
            others = {}

            logger.info(f'FileHandler.scan_models: scanning level 2 {active_dir}')
            for file_path, is_archive in chain(((active_dir / name, False) for name in filenames),
                                                ((f.resolve(), True) for f in archive_dir.iterdir() if f.is_file())):
                stem = file_path.stem
                if file_path.suffix in self.config.model_extensions:
                    metadata_file = file_path.with_suffix('.metadata.json')
                    metadata = ensure_metadata(file_path, metadata_file)
                    model_hash = metadata['sha256']
                    if model_hash not in models:
                        models[model_hash] = {'stem': stem,
                                              'hash': model_hash,
                                              'name': metadata.get('model_name', stem),
                                              'tags': metadata.get('tags', []),
                                              'relative_path': relative_path,
                                              'files': []}
                    elif models[model_hash]['stem'] != stem:
                        raise ArchivistException(ArchivistError.INCONSISTENT_FILENAME, str(file_path))
                    models[model_hash]['files'].append((file_path, ComponentType.MODEL, is_archive))
                    models[model_hash]['files'].append((metadata_file, ComponentType.METADATA, is_archive))
                elif not file_path.name.endswith('.metadata.json'):
                    if stem not in others:
                        others[stem] = [(file_path, ComponentType.EXTRA, is_archive)]
                    else:
                        others[stem].append((file_path, ComponentType.EXTRA, is_archive))

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
                        model_dict['files'].append((example.resolve(), ComponentType.EXAMPLE, False))
                examples_dir = archive_examples / model_hash
                if examples_dir.is_dir():
                    for example in examples_dir.iterdir():
                        model_dict['files'].append((example.resolve(), ComponentType.EXAMPLE, True))

                yield model_dict
