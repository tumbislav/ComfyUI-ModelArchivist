# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: configuration.py
# purpose: Read-only REST access to application configuration
# ---------------------------------------------------------------------------

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.config import get_config
import backend.repository.repository as repo

router = APIRouter()


class OptionsInput(BaseModel):
    update_json_metadata: bool = True
    ignore_unknown_types: bool = False
    always_recalc_hashes: bool = False


class LocationInput(BaseModel):
    working_dir: str
    archive_dir: str | None = None


class ModelTypeInput(BaseModel):
    name: str
    display_name: str
    extensions: list[str] = Field(default_factory=list)
    locations: list[LocationInput] = Field(default_factory=list)


class RepositoryConfigurationInput(BaseModel):
    options: OptionsInput = Field(default_factory=OptionsInput)
    model_types: list[ModelTypeInput] = Field(default_factory=list)
    workflow_locations: list[LocationInput] = Field(default_factory=list)


class ModelConfigurationInput(BaseModel):
    model_types: list[ModelTypeInput] = Field(default_factory=list)


class WorkflowConfigurationInput(BaseModel):
    workflow_locations: list[LocationInput] = Field(default_factory=list)


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


@router.get('/config/repository')
async def get_repository_configuration() -> dict:
    return repo.get_repository_configuration()


@router.put('/config/repository')
async def update_repository_configuration(data: RepositoryConfigurationInput) -> dict:
    try:
        return repo.update_repository_configuration(data.model_dump())
    except ValueError as error:
        raise HTTPException(400, str(error)) from error


@router.put('/config/models')
async def update_model_configuration(data: ModelConfigurationInput) -> dict:
    try:
        return repo.update_model_configuration(data.model_dump())
    except ValueError as error:
        raise HTTPException(400, str(error)) from error


@router.put('/config/workflows')
async def update_workflow_configuration(data: WorkflowConfigurationInput) -> dict:
    try:
        return repo.update_workflow_configuration(data.model_dump())
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
