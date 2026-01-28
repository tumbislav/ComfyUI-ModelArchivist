# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: models.py
# purpose: REST interface for models
# ---------------------------------------------------------------------------

from backend.model.archivist import archivist

from fastapi import APIRouter

model_router = APIRouter()


@model_router.get('/models')
def get_models() -> list[dict]:
    models = archivist.get_models()
    return models


@model_router.get('/health')
def health() -> dict[str, str]:
    return {'status': 'ok'}

