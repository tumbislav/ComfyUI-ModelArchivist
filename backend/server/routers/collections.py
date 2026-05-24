# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: collections.py
# purpose: REST interface for collections
# ---------------------------------------------------------------------------

import backend.repository.repository as repo
from fastapi import APIRouter

router = APIRouter()

@router.get('/collections')
async def get_collections() -> list[dict]:
    return repo.list_collections(True)
