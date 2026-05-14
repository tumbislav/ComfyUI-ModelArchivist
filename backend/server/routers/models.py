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
    models = get_archivist().get_model_list()
    return models

@router.get('/models/{id}')
async def get_model(id: str) -> dict:
    model = get_archivist().get_model(id)
    return model

@router.post('/models/search')
async def search_models(criteria: dict) -> list[dict]:
    models = get_archivist().get_model_list(criteria)
    return models

@router.put('/models/{id}')
async def search_models(id: str, criteria: dict) -> list[dict]:
    pass

