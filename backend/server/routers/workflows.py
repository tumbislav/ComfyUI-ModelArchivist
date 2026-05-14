# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: workflows.py
# purpose: REST interface for workflows
# ---------------------------------------------------------------------------

from backend.model.archivist import get_archivist
from fastapi import APIRouter

router = APIRouter()

@router.get('/workflows')
async def get_workflows() -> list[dict]:
    workflows = get_archivist().get_workflow_list()
    return workflows

@router.get('/workflows/{id}')
async def get_workflow(id: str) -> dict:
    workflow = get_archivist().get_workflow(id)
    return workflow

@router.post('/workflows/search')
async def search_workflows(criteria: dict) -> list[dict]:
    workflows = get_archivist().get_workflow_list(criteria)
    return workflows

@router.put('/workflows/{id}')
async def search_workflows(id: str, criteria: dict) -> list[dict]:
    pass
