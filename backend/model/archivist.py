# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: archivist.py
# purpose: Main service
# ---------------------------------------------------------------------------
from selectors import SelectSelector

import yaml
from pathlib import Path
import logging
import uuid

from ..db.repository import Repository
from ..db.tables import Model, Tag
from .file_handler import FileHandler
from .object_types import Location

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

    def attach(self, config, repo: Repository) -> None:
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
        if self.model_types is None:
            self.model_types = {}
        for model_sub in model_root.iterdir():
            relative_path = model_sub.relative_to(model_root)
            model_type = model_sub.stem
            if not model_sub.is_dir() or model_type == 'examples':
                continue
            if model_type not in self.model_types:
                self.model_types[model_type] = {}
            self.model_types[model_type] = [{Location.ACTIVE: model_sub,
                                             Location.INACTIVE: self.inactive_root / relative_path,
                                             Location.ARCHIVE: self.archive_root / relative_path}]
        for extra_path in self.config.extra_models:
            self.locate_extra_paths(extra_path['yaml'],
                                    extra_path.get('inactive', self.inactive_root),
                                    extra_path.get('active', self.archive_root))

    def locate_extra_paths(self, yaml_file: Path, inactive_path: Path, archive_path: Path) -> None:
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
                type_locations = self.model_types.get(model_type, [])
                for extra_dir in (Path(_) for _ in extras.split('\n') if len(_) > 0):
                    if base_path:
                        full_dir = base_path / extra_dir
                    elif extra_dir.is_absolute():
                        full_dir = extra_dir
                    else:
                        full_dir = yaml_root / extra_dir
                    type_locations.append({Location.ACTIVE: full_dir,
                                           Location.INACTIVE: inactive_path / model_type,
                                           Location.ARCHIVE: archive_path / model_type})

    def scan_models(self):
        scan_id = str(uuid.uuid4())
        for type_name, type_locations in self.model_types.items():
            for location_item in type_locations:
                for location, loc_path in location_item.items():
                    for metadata, files in self.file_handler.scan_model_location(loc_path, location):
                        tags = metadata.get('tags', [])
                        model = Model(sha256=metadata['sha256'],
                                      name=metadata['model_name'],
                                      type=type_name,
                                      active_root=str(location_item[Location.ACTIVE]),
                                      inactive_root=str(location_item[Location.INACTIVE]),
                                      archive_root=str(location_item[Location.ARCHIVE]),
                                      last_scan_id=scan_id,
                                      tags=[Tag(tag=_) for _ in tags],
                                      components=files,
                                      scan_errors='')

                        self.repo.ensure_model_in_location(model, location)

    def get_models(self, tags=False, components=False):
        result = []
        for model in self.repo.get_models():
            json_model = {'id': str(model.id),
            'sha256':model.sha256,
            'name': model.name,
            'type': self.config.model_types.get(model.type, model.type),
            'status': 'ACTIVE' if model.is_active and not model.is_inactive else \
                'INACTIVE' if model.is_inactive and not model.is_active else \
                'UNDETERMINED',
            'archived': model.is_archived}
            if tags:
                json_model['tags'] = [_.tag for _ in model.tags]
            if components:
                json_model['components']=[{
                    'location': str(component.location),
                    'relative_path': component.relative_path,
                    'filename': component.filename,
                    'type': str(component.component_type),
                    'is_present': component.is_present} for component in model.components]
            result.append(json_model)
        return result


archivist = ArchivistService()
