# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: user_types.py
# purpose: REST interface for user-defined types and objects
# ---------------------------------------------------------------------------

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

import backend.repository.repository as repo
from backend.dispatcher import OperationBusyError, dispatcher
from backend.exception import ArcException
from backend.repository.tables import DeploymentStatus


router = APIRouter()


class UserTypeInput(BaseModel):
    name: str
    short_name: str = Field(min_length=1, max_length=8)
    object_class: str
    extensions: list[str] = Field(default_factory=list)
    working_dir: str
    archive_dir: str
    icon: str
    purpose: str = ''
    size_limit: int | None = None
    small: bool = False
    confirm_oversized: bool = False


class UserObjectUpdate(BaseModel):
    display_name: str
    purpose: str = ''
    tags: list[str] = Field(default_factory=list)


class UserObjectSearchCriteria(BaseModel):
    name_prefix: str = ''
    required_tags: list[str] = Field(default_factory=list)
    forbidden_tags: list[str] = Field(default_factory=list)


def handle(error: ArcException) -> HTTPException:
    if error.code in (ArcException.Code.UNKNOWN_USER_TYPE,
                      ArcException.Code.UNKNOWN_USER_OBJECT):
        return HTTPException(404, error.message)
    if error.code == ArcException.Code.READ_ONLY:
        return HTTPException(403, error.message)
    if error.code in (ArcException.Code.USER_TYPE_IN_USE,
                      ArcException.Code.CONFIRMATION_REQUIRED,
                      ArcException.Code.INVALID_CONFIRMATION):
        return HTTPException(409, error.message)
    return HTTPException(400, error.message)


def type_payload(data: UserTypeInput) -> dict:
    payload = data.model_dump(exclude_none=True)
    return payload


@router.get('/user-types')
async def list_user_types() -> list[dict]:
    return repo.list_user_types()


@router.post('/user-types', status_code=201)
async def create_user_type(data: UserTypeInput) -> dict:
    try:
        return repo.create_user_type(type_payload(data))
    except ArcException as error:
        raise handle(error)


@router.get('/user-types/{id}')
async def get_user_type(id: str) -> dict:
    try:
        return repo.get_user_type(id)
    except ArcException as error:
        raise handle(error)


@router.put('/user-types/{id}')
async def update_user_type(id: str, data: UserTypeInput) -> dict:
    try:
        return repo.update_user_type(id, type_payload(data))
    except ArcException as error:
        raise handle(error)


@router.post('/user-types/{id}/deletion-preview')
async def preview_user_type_deletion(id: str) -> dict:
    try:
        return repo.preview_user_type_deletion(id)
    except ArcException as error:
        raise handle(error)


@router.delete('/user-types/{id}')
async def delete_user_type(id: str, confirmation_id: str) -> dict:
    try:
        return repo.delete_user_type(id, confirmation_id)
    except ArcException as error:
        raise handle(error)


@router.get('/user-types/{id}/objects')
async def list_user_objects(id: str) -> list[dict]:
    try:
        return repo.list_user_objects(id)
    except ArcException as error:
        raise handle(error)


@router.post('/user-types/{id}/objects/search')
async def search_user_objects(id: str, criteria: UserObjectSearchCriteria) -> list[dict]:
    try:
        return repo.list_user_objects(id, criteria.model_dump())
    except ArcException as error:
        raise handle(error)


@router.get('/user-objects/{id}')
async def get_user_object(id: str) -> dict:
    try:
        return repo.get_user_object(id)
    except ArcException as error:
        raise handle(error)


@router.put('/user-objects/{id}')
async def update_user_object(id: str, data: UserObjectUpdate) -> dict:
    try:
        return repo.update_user_object(id, data.model_dump())
    except ArcException as error:
        raise handle(error)


@router.post('/user-objects/{id}/synchronize')
async def synchronize_user_object(id: str, response: Response,
                                  simulate: bool = True) -> dict:
    plan = repo.synchronize_user_object(id, True)
    if simulate or not plan['allowed']:
        return plan
    if not repo.user_object_operation_requires_lro([id], plan['transfer_bytes']):
        return repo.synchronize_user_object(id, False)
    try:
        operation = dispatcher.submit(
            'user_object_sync',
            lambda report: repo.synchronize_user_object(id, False, report))
    except OperationBusyError as error:
        raise HTTPException(409, str(error))
    response.status_code = 202
    return operation


@router.post('/user-objects/{id}/move')
async def move_user_object(id: str, destination: DeploymentStatus,
                           response: Response, simulate: bool = True) -> dict:
    plan = repo.move_user_object(id, destination, True)
    if simulate or not plan['allowed']:
        return plan
    if not repo.user_object_operation_requires_lro([id], plan['transfer_bytes']):
        return repo.move_user_object(id, destination, False)
    try:
        operation = dispatcher.submit(
            'user_object_move',
            lambda report: repo.move_user_object(id, destination, False, report))
    except OperationBusyError as error:
        raise HTTPException(409, str(error))
    response.status_code = 202
    return operation
