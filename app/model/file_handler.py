# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: file_handler.py
# purpose: File system scan
# ---------------------------------------------------------------------------

import logging
from typing import Iterable, Tuple
from pathlib import Path
from app.config.config import Configuration

logger = logging.getLogger('model_archivist')


class FileHandler:
    """
    Locates and moves files
    """
    def __init__(self, config: Configuration) -> None:
        self.configuration = config
        self.extensions = config.model_extensions

    def scan(self, root: Path) -> Iterable[Tuple[Path, Path, Path | None]]:
        """
        Scan a dir with subdirs and return all model files found.
        For models with an associated metadata file, return that too.
        """
        for dirpath, dirnames, filenames in root.walk():
            for name in filenames:
                file_path = dirpath / name
                if file_path.suffix in self.extensions:
                    metadata_path = file_path.with_suffix('.metadata.json')
                    if not metadata_path.is_file():
                        metadata_path = None
                    yield file_path, dirpath.relative_to(root), metadata_path
