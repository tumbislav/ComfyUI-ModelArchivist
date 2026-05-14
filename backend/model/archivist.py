# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: archivist.py
# purpose: Main service
# ---------------------------------------------------------------------------

import logging

import backend.db.repository as repo
from .object_types import Taggable
from .scanner import create_scanner
from backend.config import get_config, Configuration

class ArchivistService:
    """
    High-level operations on archive objects.
    """
    def __init__(self, config: Configuration) -> None:
        self.scan_id: str | None = None
        self.config: Configuration = config
        self.is_first_run = repo.start_repo()
        if self.is_first_run:
            self.scan()

    def scan(self, rehash: bool = False):
        _logger.info('Starting filesystem scan')
        sc = create_scanner()
        self.scan_id = sc.start(rehash)

    def get_model_list(self, ordered=True) -> list[dict]:
        result = []
        for model in repo.list_models(ordered):
            json_model = {'id': model.id,
                          'name': model.name,
                          'type': self.config.model_types.get(model.type, model.type),
                          'active': model.is_active,
                          'archived': model.is_archived}
            result.append(json_model)
        return result

    def get_model(self, id: str) -> dict:
        model = repo.get_model(id)
        json_model = {'id': model.id,
                      'name': model.name,
                      'type': self.config.model_types.get(model.type, model.type),
                      'active': model.is_active,
                      'archived': model.is_archived,
                      'tags': [_.tag for _ in model.tags],
                      'components': [{
                          'location': str(component.location),
                          'relative_path': component.relative_path,
                          'filename': component.filename,
                          'type': str(component.component_type),
                          'is_present': component.is_present} for component in model.components]
                      }
        return json_model

    @staticmethod
    def get_workflow_list(self, ordered=True) -> list[dict]:
        result = []
        for workflow in repo.list_workflows(ordered):
            json_workflow = {'id': workflow.id,
                          'name': workflow.name,
                          'purpose': workflow.purpose,
                          'active': workflow.is_active,
                          'archived': workflow.is_archived}
            result.append(json_workflow)
        return result

    def get_workflow(self, id) -> dict:
        pass
#        workflow = get_workflow(id)

    def get_collection_list(self, ordered=True, tags=False, components=False) -> list[dict]:
        result = [{'id': 1,
                   'name': 'dummy collection',
                   'type': 'no type',
                   'active': True,
                   'archived': True}]
        for collection in repo.list_workflows(ordered):
            json_collection = {'id': collection.id,
                               'name': collection.name,
                               'type': self.config.model_types.get(collection.type, collection.type),
                               'active': collection.is_active,
                               'archived': collection.is_archived}
            if tags:
                json_collection['tags'] = [_.tag for _ in collection.tags]
            if components:
                json_collection['components'] = [{
                    'location': str(component.location),
                    'relative_path': component.relative_path,
                    'filename': component.filename,
                    'type': str(component.component_type),
                    'is_present': component.is_present} for component in collection.components]
            result.append(json_collection)
        return result

    @staticmethod
    def get_tags(target: set[Taggable], offset: int, limit: int) -> list:
        return repo.get_tags(target, offset, limit)


_archivist: ArchivistService | None = None
_logger: logging.Logger

def start_archivist() -> ArchivistService:
    global _archivist, _logger
    config = get_config()
    _logger = logging.getLogger('archivist.core')
    if _archivist is not None:
        _logger.error('Attempting to start the Archivist service that is already started')
        raise RuntimeError('Cannot start Archivist service twice')
    _archivist = ArchivistService(config)
    _logger.info('Archivist service started')
    return _archivist

def get_archivist() -> ArchivistService | None:
    global _archivist
    if _archivist is None:
        raise RuntimeError('Archivist Service not started')
    return _archivist

