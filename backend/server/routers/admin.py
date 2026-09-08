# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: admin.py
# purpose: Admin endpoint
# ---------------------------------------------------------------------------

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from threading import Lock
from typing import Literal
from pathlib import Path
import tomllib
from backend.config import get_config
from backend.dispatcher import OperationBusyError, dispatcher, submit_scan
from backend.files.scanner import get_scanner
from backend.repository.repository import repo_status, user_types_for_scan

router = APIRouter()
_startup_scan_lock = Lock()
_startup_scan_id: str | None = None

@router.get('/server-status')
def server_status() -> dict:
    return repo_status()


@router.get('/about')
def about() -> dict[str, str]:
    project_file = Path(__file__).resolve().parents[3] / 'pyproject.toml'
    with project_file.open('rb') as source:
        project = tomllib.load(source)
    return {'version': project['project']['version'], 'mode': get_config().mode}


class ScanTargets(BaseModel):
    type_ids: list[str] = Field(min_length=1)


@router.post('/scan', status_code=202)
def start_scan(rehash: bool = False, startup: bool = False,
               scope: Literal['all', 'models', 'workflows', 'user_objects'] = 'all',
               type_id: str | None = None, targets: ScanTargets | None = None) -> dict:
    global _startup_scan_id
    config = get_config()
    if config.read_only:
        raise HTTPException(403, 'Application is read-only')
    if config.setup_required:
        raise HTTPException(409, detail={
            'code': 'setup_required',
            'message': 'Complete repository setup before scanning',
            'params': {},
        })
    selected = targets.type_ids if targets is not None else ([type_id] if type_id is not None else None)
    invalid_scope = scope not in ('all', 'models', 'workflows', 'user_objects')
    invalid_scope |= targets is not None and type_id is not None
    invalid_scope |= startup and (scope != 'all' or selected is not None)
    if selected is not None:
        if scope == 'models':
            invalid_scope |= not set(selected).issubset(config.model_folders)
        elif scope == 'user_objects':
            invalid_scope |= not set(selected).issubset(item['id'] for item in user_types_for_scan())
        else:
            invalid_scope = True
    if invalid_scope:
        raise HTTPException(422, detail={
            'code': 'invalid_scan_scope', 'message': 'Invalid scan scope or type',
            'params': {'scope': scope, 'type_id': type_id},
        })
    try:
        if startup:
            with _startup_scan_lock:
                if _startup_scan_id is not None:
                    return dispatcher.get(_startup_scan_id)
                operation = submit_scan(config.options.always_recalc_hashes)
                _startup_scan_id = operation['id']
                return operation
        if scope == 'all' and type_id is None:
            return submit_scan(rehash)
        return submit_scan(rehash, scope, list(dict.fromkeys(selected)) if targets else type_id)
    except OperationBusyError as error:
        raise HTTPException(409, str(error))


@router.get('/scan/{timestamp}')
def scan_status(timestamp: str) -> dict:
    sc = get_scanner(timestamp)
    if sc is None:
        raise HTTPException(404, 'No such scan job')
    return sc.progress()
