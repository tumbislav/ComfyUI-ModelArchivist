# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: admin.py
# purpose: Admin endpoint
# ---------------------------------------------------------------------------

from fastapi import APIRouter, HTTPException
from backend.model.archivist import archivist

router = APIRouter()


@router.get('/admin')
def admin() -> dict[str, str]:
    return {}


@router.post('/admin/scan')
def admin() -> str:
    scan_id = archivist.start_scan()
    if scan_id is None:
        raise HTTPException(400, 'Scan already running')
    return scan_id


@router.get('/admin/scan/{scanId}')
def admin(scanId: int) -> int:
    progress = archivist.status(scanId)
    if progress is None:
        raise HTTPException(400, 'No scan running')
    return progress
