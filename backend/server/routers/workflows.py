# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: workflows.py
# purpose: REST interface for workflows
# ---------------------------------------------------------------------------

import backend.repository.repository as repo
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.exception import ArcException
from backend.repository.tables import DeploymentStatus

router = APIRouter()


class WorkflowSearchCriteria(BaseModel):
    required_tags: list[str] = []
    forbidden_tags: list[str] = []
    name_prefix: str = ''


class WorkflowIds(BaseModel):
    ids: list[str]


class WorkflowTagUpdate(WorkflowIds):
    add: list[str]
    remove: list[str]


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
        raise HTTPException(400, e.message)

@router.post('/workflows/search')
async def search_workflows(criteria: WorkflowSearchCriteria) -> list[dict]:
    return repo.list_workflows(True, criteria.model_dump())


@router.post('/workflows/bulk/tags')
async def update_workflow_tags(data: WorkflowTagUpdate) -> dict:
    return repo.update_workflow_tags(data.ids, data.add, data.remove)


@router.post('/workflows/bulk/synchronize')
async def synchronize_workflows(data: WorkflowIds, simulate: bool = True) -> dict:
    return repo.workflow_batch_operation(data.ids, 'synchronize', simulate)


@router.post('/workflows/bulk/move')
async def move_workflows(data: WorkflowIds, destination: DeploymentStatus,
                         simulate: bool = True) -> dict:
    return repo.workflow_batch_operation(data.ids, 'move', simulate, destination)


@router.put('/workflows/{id}')
async def update_workflow(id: str, changed_workflow: dict) -> dict:
    changed_workflow['id'] = id
    try:
        return repo.update_workflow(changed_workflow)
    except ArcException as error:
        if error.code == ArcException.Code.UNKNOWN_WORKFLOW:
            raise HTTPException(404, error.message)
        if error.code == ArcException.Code.READ_ONLY:
            raise HTTPException(403, error.message)
        raise HTTPException(400, error.message)


@router.post('/workflows/{id}/synchronize')
async def synchronize_workflow(id: str, simulate: bool = True) -> dict:
    return repo.synchronize_workflow(id, simulate)


@router.post('/workflows/{id}/move')
async def move_workflow(id: str, destination: DeploymentStatus,
                        simulate: bool = True) -> dict:
    return repo.move_workflow(id, destination, simulate)
