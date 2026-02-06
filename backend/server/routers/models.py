# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: models.py
# purpose: REST interface for models
# ---------------------------------------------------------------------------

from backend.model.archivist import archivist

from fastapi import APIRouter

router = APIRouter()

@router.get('/models')
def get_models() -> list[dict]:
    models = archivist.get_models()
    return models
