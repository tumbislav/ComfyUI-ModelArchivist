# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: file_handler.py
# purpose: Scanning folders and moving file_handler around
# ---------------------------------------------------------------------------

import logging
from typing import Iterable
from pathlib import Path
from app.config.config import Configuration
from app.model.file_utils import ensure_metadata
from app.model.object_types import Location, ComponentType
from app.db.tables import Component

logger = logging.getLogger('model_archivist')


class FileHandler:
    """
    Locates and moves file_handler
    """
    def __init__(self, config: Configuration) -> None:
        self.configuration = config
        self.extensions = config.model_extensions

    def scan_model_location(self, root: Path, location: Location) -> Iterable:
        """
        Scan a dir with subdirs and return all model file_handler found.
        For models with an associated metadata file, return that too.
        """
        examples_root = root.parent / 'examples'
        for dirpath, dirnames, filenames in root.walk():
            for name in filenames:
                model_path = dirpath / name
                if model_path.suffix in self.extensions:
                    file_list = []
                    relative_path = dirpath.relative_to(root)
                    metadata_path, metadata = ensure_metadata(model_path)
                    file_list.append(Component(location=None,
                                               relative_path=relative_path,
                                               filename=metadata_path.name,
                                               component_type=ComponentType.METADATA,
                                               is_present=metadata_path is not None))
                    file_list.append(Component(location=None,
                                               relative_path=relative_path,
                                               filename=name,
                                               component_type=ComponentType.MODEL,
                                               is_present=True))
                    for filename in filenames:
                        if model_path.stem == Path(filename).stem:
                            file_list.append(Component(location=None,
                                                       relative_path=relative_path,
                                                       filename=filename,
                                                       component_type=ComponentType.EXTRA,
                                                       is_present=True))
                    if examples_root.is_dir():
                        examples_dir = examples_root / metadata['sha256']
                        examples_relative_path = examples_dir.relative_to(root)
                        if examples_dir.is_dir():
                            for example in examples_dir.iterdir():
                                file_list.append(Component(location=None,
                                                           relative_path=examples_relative_path,
                                                           filename=example,
                                                           component_type=ComponentType.EXAMPLE,
                                                           is_present=True))

                    yield model_path.name, metadata, file_list
