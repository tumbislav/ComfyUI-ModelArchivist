# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: operations.py
# purpose: REST polling interface for long-running operations
# ---------------------------------------------------------------------------

from fastapi import APIRouter, HTTPException

from backend.dispatcher import UnknownOperationError, dispatcher
from backend.repository.repository import repository_counts, repository_summary, repo_status
from backend.config import get_config
from backend.repository.repository import user_types_for_scan

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


@router.get('/repository-summary')
def get_repository_summary() -> dict:
    status = repo_status()
    config = get_config()
    return {'sections': repository_summary(), 'operation': dispatcher.current(),
            'configured_scopes': {
                'models': any(config.model_folders.values()),
                'workflows': bool(config.workflow_folders),
                'user_objects': bool(user_types_for_scan()),
            },
            'can_scan': status['started'] and not status['read_only']
                        and not status.get('setup_required', True)}
