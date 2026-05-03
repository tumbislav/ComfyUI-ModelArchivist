# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: models.py
# purpose: REST interface for models
# ---------------------------------------------------------------------------

from backend.model.archivist import get_archivist
from fastapi import APIRouter

router = APIRouter()

@router.get('/models')
async def get_models() -> list[dict]:
    models = get_archivist().get_models()
    return models
