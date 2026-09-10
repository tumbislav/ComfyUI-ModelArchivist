# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: models.py
# purpose: REST interface for models
# ---------------------------------------------------------------------------

import backend.repository.repository as repo
from fastapi import APIRouter, HTTPException, Response

from backend.dispatcher import OperationBusyError, dispatcher
from backend.exception import ArcException
from backend.repository.tables import DeploymentStatus
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter()


class ModelSearchCriteria(BaseModel):
    model_config = ConfigDict(extra='forbid')

    types: list[str] = Field(default_factory=list)
    file_formats: list[str] = Field(default_factory=list)
    required_tags: list[str] = Field(default_factory=list)
    forbidden_tags: list[str] = Field(default_factory=list)
    name_prefix: str = ''


class ModelIds(BaseModel):
    ids: list[str]


class ModelTagUpdate(ModelIds):
    add: list[str] = Field(default_factory=list)
    remove: list[str] = Field(default_factory=list)


class ModelBaseModelUpdate(ModelIds):
    base_model: str = ''


class ModelRelocation(ModelIds):
    destination: str


@router.get('/models')
async def get_models() -> list[dict]:
    return repo.list_models(True)


@router.get('/models/base-models')
async def get_base_models() -> list[str]:
    return repo.list_base_models()


@router.get('/models/relative-paths')
async def get_model_relative_paths(type_id: str | None = None) -> list[str]:
    return repo.relative_path_choices('models', type_id)


@router.post('/models/relocate')
async def relocate_models(data: ModelRelocation, simulate: bool = True) -> dict:
    try:
        with dispatcher.configuration_change():
            return repo.relocate_objects('models', data.ids, data.destination, simulate)
    except OperationBusyError as error:
        raise HTTPException(409, detail={
            'code': 'operation_busy', 'message': str(error), 'params': {}}) from error
    except ValueError as error:
        raise HTTPException(400, detail={
            'code': 'invalid_relative_path', 'message': str(error), 'params': {}}) from error


@router.get('/models/{id}')
async def get_model(id: str) -> dict | None:
    try:
        return repo.get_model(id)
    except ArcException as e:
        if e.code == ArcException.Code.UNKNOWN_MODEL:
            raise HTTPException(404, e.message)

@router.post('/models/search')
async def search_models(criteria: ModelSearchCriteria) -> list[dict]:
    models = repo.list_models(True, criteria.model_dump())
    return models


@router.post('/models/bulk/tags')
async def update_model_tags(data: ModelTagUpdate) -> dict:
    try:
        return repo.update_model_tags(data.ids, data.add, data.remove)
    except ArcException as error:
        raise HTTPException(400, {'code': error.code.name.lower(), 'message': error.message, 'params': {}})


@router.post('/models/bulk/base-model')
async def update_model_base_models(data: ModelBaseModelUpdate) -> dict:
    return repo.update_model_base_models(data.ids, data.base_model)


@router.post('/models/bulk/synchronize')
async def synchronize_models(data: ModelIds, response: Response,
                             simulate: bool = True) -> dict:
    if simulate:
        return repo.model_batch_operation(data.ids, 'synchronize', True)
    try:
        operation = dispatcher.submit(
            'model_batch_sync',
            lambda report: repo.model_batch_operation(
                data.ids, 'synchronize', False, progress=report))
    except OperationBusyError as error:
        raise HTTPException(409, str(error))
    response.status_code = 202
    return operation


@router.post('/models/bulk/move')
async def move_models(data: ModelIds, destination: DeploymentStatus,
                      response: Response, simulate: bool = True) -> dict:
    if simulate:
        return repo.model_batch_operation(data.ids, 'move', True, destination)
    try:
        operation = dispatcher.submit(
            'model_batch_move',
            lambda report: repo.model_batch_operation(
                data.ids, 'move', False, destination, report))
    except OperationBusyError as error:
        raise HTTPException(409, str(error))
    response.status_code = 202
    return operation

@router.put('/models/{id}')
async def update_mode(changed_model: dict) -> dict:
    try:
        return repo.update_model(changed_model)
    except ArcException as error:
        raise HTTPException(400, {'code': error.code.name.lower(), 'message': error.message, 'params': {}})


@router.post('/models/{id}/synchronize')
async def synchronize_model(id: str, response: Response,
                            simulate: bool = True) -> dict:
    if simulate:
        return repo.synchronize_model(id, True)
    try:
        operation = dispatcher.submit(
            'model_sync', lambda report: repo.synchronize_model(id, False, report))
    except OperationBusyError as error:
        raise HTTPException(409, str(error))
    response.status_code = 202
    return operation


@router.post('/models/{id}/move')
async def move_model(id: str, destination: DeploymentStatus,
                     response: Response, simulate: bool = True) -> dict:
    if simulate:
        return repo.move_model(id, destination, True)
    try:
        operation = dispatcher.submit(
            'model_move',
            lambda report: repo.move_model(id, destination, False, report))
    except OperationBusyError as error:
        raise HTTPException(409, str(error))
    response.status_code = 202
    return operation

