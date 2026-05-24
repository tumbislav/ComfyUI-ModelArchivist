# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: admin.py
# purpose: Admin endpoint
# ---------------------------------------------------------------------------

from fastapi import APIRouter, HTTPException
from backend.files.scanner import get_scanner, create_scanner
from backend.repository.repository import repo_status

router = APIRouter()

@router.get('/server-status')
def server_status() -> dict:
    return repo_status()


@router.post('/scan')
def start_scan() -> str:
    sc = create_scanner()
    if sc is None:
        raise HTTPException(400, 'Scan already running')
    return sc.start()


@router.get('/scan/{timestamps}')
def scan_status(timestamp: str) -> dict:
    sc = get_scanner(timestamp)
    if sc is None:
        raise HTTPException(404, 'No such scan job')
    return sc.progress()
