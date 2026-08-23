# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: workflows.py
# purpose: REST interface for workflows
# ---------------------------------------------------------------------------

import backend.repository.repository as repo
from fastapi import APIRouter, HTTPException

from backend.exception import ArcException

router = APIRouter()

@router.get('/workflows')
async def get_workflows() -> list[dict]:
    workflows = repo.list_workflows(True)
    return workflows

@router.get('/workflows/{id}')
async def get_workflow(id: str) -> dict | None:
    try:
        return repo.get_workflow(id)
    except ArcException as e:
        if e.code == ArcException.Code.UNKNOWN_WORKFLOW:
            raise HTTPException(404, e.message)

@router.post('/workflows/search')
async def search_workflows(criteria: dict) -> list[dict]:
    return repo.list_workflows(True, criteria)


@router.post('/workflows/{id}/synchronize')
async def synchronize_workflow(id: str, simulate: bool = True) -> dict:
    return repo.synchronize_workflow(id, simulate)
