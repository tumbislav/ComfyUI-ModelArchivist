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

router = APIRouter()


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
async def search_models(criteria: dict) -> list[dict]:
    models = repo.list_models(True, criteria)
    return models

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

