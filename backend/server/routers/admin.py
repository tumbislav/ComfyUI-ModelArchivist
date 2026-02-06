# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: admin.py
# purpose: Admin endpoint
# ---------------------------------------------------------------------------

from fastapi import APIRouter

router = APIRouter()

@router.get('/admin')
def admin() -> dict[str, str]:
    return {}