# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: collections.py
# purpose: REST interface for collections
# ---------------------------------------------------------------------------

from backend.model.archivist import get_archivist
from fastapi import APIRouter

router = APIRouter()

@router.get('/collections')
async def get_collections() -> list[dict]:
    collections = get_archivist().get_collection_list()
    return collections
