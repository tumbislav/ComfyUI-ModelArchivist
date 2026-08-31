# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: collections.py
# purpose: REST interface for collections
# ---------------------------------------------------------------------------

import backend.repository.repository as repo
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from backend.exception import ArcException
from backend.dispatcher import OperationBusyError, dispatcher
from backend.repository.tables import DeploymentStatus

router = APIRouter()


class CollectionModelUpdate(BaseModel):
    model_ids: list[str]
    add: bool


class CollectionWorkflowUpdate(BaseModel):
    workflow_ids: list[str]
    add: bool


class CollectionUserObjectUpdate(BaseModel):
    user_object_ids: list[str]
    add: bool

@router.get('/collections')
async def get_collections() -> list[dict]:
    return repo.list_collections(True)


@router.get('/collections/{id}')
async def get_collection(id: str) -> dict:
    try:
        return repo.get_collection(id)
    except ArcException as error:
        if error.code == ArcException.Code.UNKNOWN_COLLECTION:
            raise HTTPException(404, error.message)
        raise HTTPException(400, error.message)


@router.post('/collections')
async def create_collection(data: dict) -> dict:
    try:
        return repo.create_collection(data)
    except ArcException as error:
        if error.code in (ArcException.Code.UNKNOWN_MODEL,
                          ArcException.Code.UNKNOWN_WORKFLOW,
                          ArcException.Code.UNKNOWN_USER_OBJECT,
                          ArcException.Code.UNKNOWN_COLLECTION):
            raise HTTPException(404, error.message)
        if error.code in (ArcException.Code.DUPLICATE_COLLECTION_MEMBER,
                          ArcException.Code.COLLECTION_CYCLE):
            raise HTTPException(409, error.message)
        raise HTTPException(400, error.message)


@router.put('/collections/{id}')
async def update_collection(id: str, data: dict) -> dict:
    try:
        return repo.update_collection(id, data)
    except ArcException as error:
        if error.code in (ArcException.Code.UNKNOWN_MODEL,
                          ArcException.Code.UNKNOWN_WORKFLOW,
                          ArcException.Code.UNKNOWN_USER_OBJECT,
                          ArcException.Code.UNKNOWN_COLLECTION):
            raise HTTPException(404, error.message)
        if error.code in (ArcException.Code.DUPLICATE_COLLECTION_MEMBER,
                          ArcException.Code.COLLECTION_CYCLE):
            raise HTTPException(409, error.message)
        raise HTTPException(400, error.message)


@router.post('/collections/{id}/models')
async def update_collection_models(id: str, data: CollectionModelUpdate) -> dict:
    try:
        return repo.update_collection_models(id, data.model_ids, data.add)
    except ArcException as error:
        if error.code in (ArcException.Code.UNKNOWN_MODEL,
                          ArcException.Code.UNKNOWN_COLLECTION):
            raise HTTPException(404, error.message)
        if error.code in (ArcException.Code.EMPTY_COLLECTION,
                          ArcException.Code.DUPLICATE_COLLECTION_MEMBER):
            raise HTTPException(409, error.message)
        raise HTTPException(400, error.message)


@router.post('/collections/{id}/workflows')
async def update_collection_workflows(id: str, data: CollectionWorkflowUpdate) -> dict:
    try:
        return repo.update_collection_workflows(id, data.workflow_ids, data.add)
    except ArcException as error:
        if error.code in (ArcException.Code.UNKNOWN_WORKFLOW,
                          ArcException.Code.UNKNOWN_COLLECTION):
            raise HTTPException(404, error.message)
        if error.code in (ArcException.Code.EMPTY_COLLECTION,
                          ArcException.Code.DUPLICATE_COLLECTION_MEMBER):
            raise HTTPException(409, error.message)
        raise HTTPException(400, error.message)


@router.post('/collections/{id}/user-objects')
async def update_collection_user_objects(id: str, data: CollectionUserObjectUpdate) -> dict:
    try:
        return repo.update_collection_user_objects(id, data.user_object_ids, data.add)
    except ArcException as error:
        if error.code in (ArcException.Code.UNKNOWN_USER_OBJECT,
                          ArcException.Code.UNKNOWN_COLLECTION):
            raise HTTPException(404, error.message)
        if error.code in (ArcException.Code.EMPTY_COLLECTION,
                          ArcException.Code.DUPLICATE_COLLECTION_MEMBER):
            raise HTTPException(409, error.message)
        raise HTTPException(400, error.message)


@router.delete('/collections/{id}')
async def delete_collection(id: str) -> dict:
    try:
        return repo.delete_collection(id)
    except ArcException as error:
        if error.code == ArcException.Code.UNKNOWN_COLLECTION:
            raise HTTPException(404, error.message)
        if error.code == ArcException.Code.EMPTY_COLLECTION:
            raise HTTPException(409, error.message)
        raise HTTPException(400, error.message)


@router.post('/collections/{id}/synchronize')
async def synchronize_collection(id: str, response: Response,
                                 simulate: bool = True) -> dict:
    plan = repo.synchronize_collection(id, True)
    if simulate or not plan['allowed']:
        return plan
    if not repo.collection_operation_requires_lro(plan):
        return repo.synchronize_collection(id, False)
    try:
        operation = dispatcher.submit(
            'collection_sync',
            lambda _report: repo.synchronize_collection(id, False))
    except OperationBusyError as error:
        raise HTTPException(409, str(error))
    response.status_code = 202
    return operation


@router.post('/collections/{id}/move')
async def move_collection(id: str, destination: DeploymentStatus,
                          response: Response, simulate: bool = True) -> dict:
    plan = repo.move_collection(id, destination, True)
    if simulate or not plan['allowed']:
        return plan
    if not repo.collection_operation_requires_lro(plan):
        return repo.move_collection(id, destination, False)
    try:
        operation = dispatcher.submit(
            'collection_move',
            lambda _report: repo.move_collection(id, destination, False))
    except OperationBusyError as error:
        raise HTTPException(409, str(error))
    response.status_code = 202
    return operation
