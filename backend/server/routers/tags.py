# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: tags.py
# purpose: REST interface for tags
# ---------------------------------------------------------------------------

from backend.db.repository import repo
from backend.model.object_types import Taggable

from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get('/tags')
async def get_tags(target: str = 'all', offset: int = 0, limit: int = 0) -> list[str]:
    target_types = set()
    match target:
        case 'models':
            target_types = {Taggable.MODEL}
        case 'workflows':
            target_types = {Taggable.WORKFLOW}
        case 'collections':
            target_types = {Taggable.COLLECTION}
        case 'all':
            target_types = {Taggable.MODEL, Taggable.WORKFLOW, Taggable.COLLECTION}
        case _:
            raise HTTPException(status_code=400, detail=f'{target} is not a taggable object')
    tags = repo.get_tags(target_types, offset, limit)
    return tags
