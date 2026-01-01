# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: archivist.py
# purpose: Main service
# ---------------------------------------------------------------------------

import yaml
from pathlib import Path
import logging
import uuid

from app.config.config import Configuration
from app.db.repository import Repository
from app.model.file_handler import FileHandler
from object_types import Location

logger = logging.getLogger('model_archivist')


class ArchivistService:
    """
    High-level operations on models.
    """

    def __init__(self) -> None:
        self.config = None
        self.repo = None
        self.active_root = None
        self.archive_root = None
        self.inactive_root = None
        self.is_first_run = None
        self.model_types = None
        self.file_handler = None

    def attach(self, config: Configuration, repo: Repository) -> None:
        self.config = config
        self.repo = repo
        self.is_first_run = repo.is_first_run
        self.file_handler = FileHandler(config)
        self.locate_model_paths()
        self.scan_models()

    def locate_model_paths(self) -> None:
        """
        Find all model folders.
        - Active locations are those in comfy_root/models and
        those in extra_model_paths.yaml.
        - inactive locations are those in inactive_root
        - archive locations are those in archive_root
        """
        model_root = Path(self.config.comfy_root) / 'models'
        self.active_root = model_root
        self.inactive_root = self.config.inactive_root
        self.archive_root = self.config.archive_root
        for model_sub in model_root.iterdir():
            if not model_sub.is_dir() or model_sub == 'examples':
                continue
            model_type = str(model_sub)
            if self.model_types is None:
                self.model_types = {}
            if model_type not in self.model_types:
                self.model_types[model_type] = {}
            self.model_types[model_type]['base'] = model_sub.resolve()
        for extra_path in self.config.extra_models:
            self.locate_extra_paths(extra_path['yaml'], extra_path.get('inactive'), extra_path.get('active'))

    def locate_extra_paths(self, yaml_file: Path, inactive: Path | None, archive: Path | None) -> None:
        extra_config = yaml.safe_load(yaml_file.read_text(encoding='utf-8'))
        yaml_root = yaml_file.parent
        for config_name, config_set in extra_config.items():
            if config_set is None or config_name != 'comfyui':
                continue
            base_path = None
            if 'base_path' in config_set:
                base_path = Path(config_set.pop('base_path')).resolve()
                if not base_path.is_absolute():
                    base_path = yaml_root / base_path
            for model_type, extras in config_set.items():
                type_record = self.model_types[model_type]
                for extra_path in extras.split('\n'):
                    if len(extra_path) == 0:
                        continue
                    extra_dir = Path(extra_path)
                    if base_path:
                        full_dir = base_path / extra_dir
                    elif extra_dir.is_absolute():
                        full_dir = extra_dir
                    else:
                        full_dir = yaml_root / extra_dir
                    extra_record = {Location.ACTIVE: full_dir}
                    if Location.INACTIVE is not None:
                        extra_record[Location.INACTIVE] = inactive / extra_path
                    if Location.ARCHIVE is not None:
                        extra_record[Location.ARCHIVE] = archive / extra_path
                    if 'extras' not in type_record:
                        type_record['extras'] = []
                    type_record['extras'].append(extra_record)

    def scan_models(self):
        scan_id = str(uuid.uuid4())
        for loc in Location:
            for type_name, type_rec in self.model_types.values():
                for contents in self.file_handler.scan_model_location(type_rec[loc], loc):
                    contents.location = Location
                    contents.sha256 = contents.metadata['sha256']
                    contents.filename = contents.metadata['filename']
                    contents.type = type_name
                    self.repo.ensure_model_in_location(contents, scan_id)

    def get_models(self):
        pass


archivist = ArchivistService()
