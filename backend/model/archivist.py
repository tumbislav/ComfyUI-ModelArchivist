# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: archivist.py
# purpose: Main service
# ---------------------------------------------------------------------------

import yaml
from pathlib import Path
import logging
import uuid

from ..db.repository import Repository
from ..db.tables import Model, Tag, Component
from .file_handler import FileHandler
from .object_types import ArchivistError, ArchivistException


logger = logging.getLogger('model_archivist')

class ArchivistService:
    """
    High-level operations on models.
    """

    def __init__(self) -> None:
        self.config = None
        self.repo = None
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

    def add_model_type_paths(self, model_type, model_dir, archive_dir):
        if model_type in self.config.ignore_types:
            return
        if model_type not in self.model_types:
            self.model_types[model_type] = set()
        model_dir.mkdir(exist_ok=True, parents=True)
        archive_dir.mkdir(exist_ok=True, parents=True)
        self.model_types[model_type].add((model_dir, archive_dir))

    def locate_model_paths(self) -> None:
        """
        Find all model folders. Make sure that all folders exist and are accessible.
        """
        model_root = Path(self.config.comfy_root) / 'models'
        archive_root = self.config.archive_root
        if self.model_types is None:
            self.model_types = {}
        # Start from the active models folder and update the archive models
        for model_type in (d.stem for d in model_root.iterdir() if d.is_dir()):
            self.add_model_type_paths(model_type, model_root / model_type, archive_root / model_type)
        # Now do the inverse
        for model_type in (d.stem for d in archive_root.iterdir() if d.is_dir()):
            self.add_model_type_paths(model_type, model_root / model_type, archive_root / model_type)
        archive_locations = {archive_root}
        for yaml_file, extra_archive_root in self.config.extra_models:
            if extra_archive_root in archive_locations:
                raise ArchivistException(ArchivistError.DUPLICATE_ARCHIVE, extra_archive_root)
            self.locate_extra_paths(yaml_file, extra_archive_root)


    def locate_extra_paths(self, yaml_file: Path, archive_path: Path) -> None:
        extra_config = yaml.safe_load(yaml_file.read_text(encoding='utf-8'))
        config_set = extra_config.get('comfyui', {})

        if 'base_path' in config_set:
            base_path = Path(config_set.pop('base_path'))
            if not base_path.is_absolute():
                base_path = yaml_file.parent / base_path
        else:
            base_path = yaml_file.parent

        for model_type, extras in config_set.items():
            if not isinstance(extras, str):
                continue
            paths = extras.split('\n')
            if len(paths) > 1:
                raise ArchivistException(ArchivistError.MULTIPLE_PATHS_PER_TYPE, model_type)
            extra_path = Path(paths[0])
            if not extra_path.is_absolute():
                extra_path = base_path / extra_path
            self.add_model_type_paths(model_type, extra_path, archive_path / model_type)

    def scan_models(self):
        scan_id = str(uuid.uuid1())  # timestamp based uuid
        for type_name, type_locations in self.model_types.items():
            for active_dir, archive_dir in type_locations:
                for model_dict in self.file_handler.scan_models(active_dir, archive_dir):
                    archive_count = sum(1 if is_archive else 0 for fn, ft, is_archive in model_dict['files'])
                    logger.info(f'archivist.scan_models: located model {model_dict["name"]}')
                    model = Model(sha256=model_dict['hash'],
                                  name=model_dict['name'],
                                  relative_path=model_dict['relative_path'],
                                  type=type_name,
                                  active_type_dir=str(active_dir),
                                  archive_type_dir=str(archive_dir),
                                  is_archived = archive_count > 0,
                                  is_active = archive_count < len(model_dict['files']),
                                  last_scan_id=scan_id,
                                  tags=[Tag(tag=tag) for tag in model_dict['tags']],
                                  components=[Component(file_name=str(file_path.name),
                                                        file_dir=str(file_path.parent),
                                                        component_type=file_type,
                                                        is_archive=is_archive,
                                                        last_scan_id=scan_id)
                                              for file_path, file_type, is_archive in model_dict['files']],
                                  scan_errors='')
                    self.repo.save_model(model)

    def get_models(self, tags=False, components=False):
        result = []
        for model in self.repo.get_models():
            json_model = {'id': str(model.id),
            'sha256':model.sha256,
            'name': model.name,
            'type': self.config.model_types.get(model.type, model.type),
            'status': 'ACTIVE' if model.is_active else 'NOT_ACTIVE',
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
