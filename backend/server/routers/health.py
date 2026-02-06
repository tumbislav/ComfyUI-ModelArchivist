# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: health.py
# purpose: Healthcheck endpoint
# ---------------------------------------------------------------------------

from fastapi import APIRouter

router = APIRouter()

@router.get('/health')
def health() -> dict[str, str]:
    return {'status': 'ok'}