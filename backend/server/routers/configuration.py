# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: configuration.py
# purpose: Read-only REST access to application configuration
# ---------------------------------------------------------------------------

from fastapi import APIRouter

from backend.config import get_config

router = APIRouter()


@router.get('/config/file_formats')
async def get_file_formats() -> list[str]:
    formats = (extension.lower().removeprefix('.')
               for extension in get_config().model_extensions)
    return list(dict.fromkeys(formats))


@router.get('/config/model_types')
async def get_model_types() -> list[dict[str, str]]:
    return [
        {'value': value, 'label': label}
        for value, label in get_config().model_types.items()
    ]
