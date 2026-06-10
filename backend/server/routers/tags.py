# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: tags.py
# purpose: REST interface for tags
# ---------------------------------------------------------------------------

import backend.repository.repository as repo
from backend.repository.tables import PrimaryObjectType

from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get('/tags')
async def get_tags(targets: str, offset: int = 0, limit: int = 0) -> list[str]:
    target_types = set()
    for tg in [_.strip() for _ in targets.split(',')]:
        if tg == 'all':
            target_types |= {PrimaryObjectType.MODEL, PrimaryObjectType.WORKFLOW, PrimaryObjectType.COLLECTION}
        elif tg == str(PrimaryObjectType.MODEL):
            target_types.add(PrimaryObjectType.MODEL)
        elif tg == str(PrimaryObjectType.WORKFLOW):
            target_types.add(PrimaryObjectType.WORKFLOW)
        elif tg == str(PrimaryObjectType.COLLECTION):
            target_types.add(PrimaryObjectType.COLLECTION)
        else:
            raise HTTPException(status_code=400, detail=f'{tg} is not a recognized object type')
    return repo.list_tags(target_types, offset, limit)
