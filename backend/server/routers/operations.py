# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: operations.py
# purpose: REST polling interface for long-running operations
# ---------------------------------------------------------------------------

from fastapi import APIRouter, HTTPException

from backend.dispatcher import UnknownOperationError, dispatcher
from backend.repository.repository import repository_counts

router = APIRouter()


@router.get('/repository-status')
async def repository_status() -> dict:
    return {'counts': repository_counts(), 'operation': dispatcher.current()}


@router.get('/operations/{id}')
async def get_operation(id: str) -> dict:
    try:
        return dispatcher.get(id)
    except UnknownOperationError:
        raise HTTPException(404, f'operation {id} does not exist')
