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


@router.get('/models')
async def get_models() -> list[dict]:
    return repo.list_models(True)

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
    return repo.update_model_tags(data.ids, data.add, data.remove)


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
    return repo.update_model(changed_model)


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

