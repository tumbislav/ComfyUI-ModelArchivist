# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: tags.py
# purpose: REST interface for tags
# ---------------------------------------------------------------------------

import backend.repository.repository as repo
from backend.repository.tables import PrimaryObjectType
from backend.tags import browser_tag_rules
from backend.repository.tag_operations import tag_usage, remap_tags
from backend.dispatcher import dispatcher, OperationBusyError
from pydantic import BaseModel

from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get('/tags')
async def get_tags(targets: str = 'all', offset: int = 0, limit: int = 0) -> list[str]:
    if targets == 'all':
        return repo.list_tags(None, offset, limit)
    target_types = set()
    for tg in [_.strip() for _ in targets.split(',')]:
        if tg == 'all':
            target_types |= {PrimaryObjectType.MODEL, PrimaryObjectType.WORKFLOW, PrimaryObjectType.COLLECTION}
        elif tg == str(PrimaryObjectType.MODEL):
            target_types.add(PrimaryObjectType.MODEL)
        elif tg == str(PrimaryObjectType.WORKFLOW):
            target_types.add(PrimaryObjectType.WORKFLOW)
        elif tg == str(PrimaryObjectType.COLLECTION):
            target_types.add(PrimaryObjectType.COLLECTION)
        else:
            raise HTTPException(status_code=400, detail=f'{tg} is not a recognized object type')
    return repo.list_tags(target_types, offset, limit)


@router.get('/tags/rules')
async def tag_rules() -> dict:
    return browser_tag_rules()


@router.get('/tags/usage')
async def usage() -> list[dict]:
    return tag_usage(repo._engine)


class TagRemapRequest(BaseModel):
    mappings: dict[str, str]


@router.post('/tags/remap', status_code=202)
async def remap(request: TagRemapRequest) -> dict:
    try:
        return dispatcher.submit('tag_remap', lambda report: remap_tags(
            repo._engine, request.mappings,
            repo._config is None or repo._config.read_only, report=report))
    except OperationBusyError as error:
        raise HTTPException(409, {'code': 'operation_busy', 'message': str(error), 'params': {}})
