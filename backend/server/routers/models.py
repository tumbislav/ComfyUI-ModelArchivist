# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: models.py
# purpose: REST interface for models
# ---------------------------------------------------------------------------

from backend.model.archivist import archivist

from fastapi import APIRouter

router = APIRouter()

@router.get('/models')
async def get_models(rescan: bool=False) -> list[dict]:
    if rescan:
        archivist.scan_models()
    models = archivist.get_models()
    return models
