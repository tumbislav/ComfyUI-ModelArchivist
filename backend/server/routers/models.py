# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: models.py
# purpose: REST interface for models
# ---------------------------------------------------------------------------

import backend.repository.repository as repo
from fastapi import APIRouter, HTTPException

from backend.exception import ArcException

router = APIRouter()


@router.get('/models')
async def get_models() -> list[dict]:
    return repo.list_models(True)

@router.get('/models/{id}')
async def get_model(id: str) -> dict | None:
    try:
        return repo.get_model(id)
    except ArcException as e:
        if e.code == ArcException.Code.UNKNOWN_MODEL:
            raise HTTPException(404, e.message)

@router.post('/models/search')
async def search_models(criteria: dict) -> list[dict]:
    models = repo.list_models(True, criteria)
    return models

@router.put('/models/{id}')
async def update_mode(changed_model: dict) -> dict:
    return repo.update_model(changed_model)

