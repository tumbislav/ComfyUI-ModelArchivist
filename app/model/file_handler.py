# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: file_handler.py
# purpose: Scanning folders and moving files around
# ---------------------------------------------------------------------------

import logging
from typing import Iterable, Dict
from pathlib import Path
from app.config.config import Configuration
from app.model.file_utils import ensure_metadata
from app.model.object_types import ModelInLocation

logger = logging.getLogger('model_archivist')


class FileHandler:
    """
    Locates and moves files
    """
    def __init__(self, config: Configuration) -> None:
        self.configuration = config
        self.extensions = config.model_extensions

    def scan(self, root: Path) -> Iterable[ModelInLocation]:
        """
        Scan a dir with subdirs and return all model files found.
        For models with an associated metadata file, return that too.
        """
        examples_root = root.parent / 'examples'
        for dirpath, dirnames, filenames in root.walk():
            for name in filenames:
                model_path = dirpath / name
                if model_path.suffix in self.extensions:
                    metadata_path, metadata = ensure_metadata(model_path)
                    contents = ModelInLocation()
                    contents.model_path = model_path
                    contents.metadata_path = metadata_path
                    contents.metadata = metadata
                    contents.relative_path = dirpath.relative_to(root)
                    for filename in filenames:
                        extra_file = dirpath / filename
                        if model_path.stem == extra_file.stem:
                            contents.extra_files.append(extra_file)
                    if examples_root.is_dir():
                        examples_dir = examples_root / metadata['sha256']
                        if examples_dir.is_dir():
                            contents.examples_dir = examples_dir
                            contents.examples = [ex for ex in examples_dir.iterdir()]
                    yield contents
