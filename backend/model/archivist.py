# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: archivist.py
# purpose: Main service
# ---------------------------------------------------------------------------

import logging

from ..db.repository import Repository
from .scanner import scanner, ScanStatus

logger = logging.getLogger('model_archivist')


class ArchivistService:
    """
    High-level operations on archive objects.
    """
    def __init__(self) -> None:
        self.config = None
        self.repo = None
        self.is_first_run = None
        self.model_types = None
        self.workflow_locations = None
        self.file_handler = None
        self.scan_id = None

    def attach(self, config, repo: Repository) -> None:
        self.config = config
        self.repo = repo
        self.is_first_run = repo.is_first_run

    def scan(self, rehash: bool = False):
        self.scan_id = scanner.start(self.model_types, self.workflow_locations, rehash)

    def get_models(self, ordered=True, tags=False, components=False) -> list:
        result = []
        for model in self.repo.get_models(ordered):
            json_model = {'hash': model.hash,
                          'name': model.name,
                          'type': self.config.model_types.get(model.type, model.type),
                          'active': model.is_active,
                          'archived': model.is_archived}
            if tags:
                json_model['tags'] = [_.tag for _ in model.tags]
            if components:
                json_model['components'] = [{
                    'location': str(component.location),
                    'relative_path': component.relative_path,
                    'filename': component.filename,
                    'type': str(component.component_type),
                    'is_present': component.is_present} for component in model.components]
            result.append(json_model)
        return result

    def get_tags(self, target: str, offset: int, limit: int) -> list:
        return [tag.tag for tag in self.repo.get_tags(target, offset, limit)]


archivist = ArchivistService()
