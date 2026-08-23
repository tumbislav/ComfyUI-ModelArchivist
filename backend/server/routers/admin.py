# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: admin.py
# purpose: Admin endpoint
# ---------------------------------------------------------------------------

from fastapi import APIRouter, HTTPException
from backend.config import get_config
from backend.dispatcher import OperationBusyError, submit_scan
from backend.files.scanner import get_scanner
from backend.repository.repository import repo_status

router = APIRouter()

@router.get('/server-status')
def server_status() -> dict:
    return repo_status()


@router.post('/scan', status_code=202)
def start_scan(rehash: bool = False) -> dict:
    if get_config().read_only:
        raise HTTPException(403, 'Application is read-only')
    try:
        return submit_scan(rehash)
    except OperationBusyError as error:
        raise HTTPException(409, str(error))


@router.get('/scan/{timestamp}')
def scan_status(timestamp: str) -> dict:
    sc = get_scanner(timestamp)
    if sc is None:
        raise HTTPException(404, 'No such scan job')
    return sc.progress()
