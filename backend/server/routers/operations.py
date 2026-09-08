# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: operations.py
# purpose: REST polling interface for long-running operations
# ---------------------------------------------------------------------------

from fastapi import APIRouter, HTTPException

from backend.dispatcher import UnknownOperationError, dispatcher
from backend.repository.repository import repository_counts, repository_summary, repo_status

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
    return {'sections': repository_summary(), 'operation': dispatcher.current(),
            'can_scan': status['started'] and not status['read_only']
                        and not status.get('setup_required', True)}
