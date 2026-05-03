# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: archivist.py
# purpose: Main service
# ---------------------------------------------------------------------------

import logging

from backend.db.repository import start_repo, get_models, get_tags
from .scanner import get_scanner
from backend.config import get_config

logger = logging.getLogger('model_archivist')


class ArchivistService:
    """
    High-level operations on archive objects.
    """
    def __init__(self) -> None:
        self.model_types = None
        self.workflow_locations = None
        self.file_handler = None
        self.scan_id = None
        self.config = get_config()
        self.is_first_run = start_repo()
        if self.is_first_run:
            self.scan()

    def scan(self, rehash: bool = False):
        sc = get_scanner()
        self.scan_id = sc.start(self.model_types, self.workflow_locations, rehash)

    def get_models(self, ordered=True, tags=False, components=False) -> list:
        result = []
        for model in get_models(ordered):
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
        return [tag.tag for tag in get_tags(target, offset, limit)]


_archivist: ArchivistService | None = None

def start_archivist() -> ArchivistService:
    global _archivist
    if _archivist is not None:
        raise RuntimeError('Cannot start Archivist Service twice')
    _archivist = ArchivistService()
    return _archivist

def get_archivist() -> ArchivistService | None:
    global _archivist
    if _archivist is None:
        raise RuntimeError('Archivist Service not started')
    return _archivist

