# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: configuration.py
# purpose: REST access to repository settings and one-time filesystem setup
# ---------------------------------------------------------------------------

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.config import get_config
from backend import directory_browser
from backend.filesystem_policy import Role
from backend.dispatcher import dispatcher, OperationBusyError
import backend.repository.repository as repo

router = APIRouter()


@router.get('/config/directory-roots')
def directory_roots(role: Role) -> list[dict]:
    return directory_browser.roots(role)


@router.get('/config/directories')
def browse_directories(path: str, role: Role) -> dict:
    return directory_browser.directories(path, role)


class OptionsInput(BaseModel):
    update_json_metadata: bool = True
    ignore_unknown_types: bool = False
    always_recalc_hashes: bool = False


class FilesystemRootsInput(BaseModel):
    working_roots: list[str]
    archive_roots: list[str]
    accept_inaccessible: bool = False


@router.put('/config/initial-filesystem-roots')
async def initialize_filesystem_roots(data: FilesystemRootsInput) -> dict:
    try:
        with dispatcher.configuration_change():
            return repo.initialize_filesystem_roots(
                data.working_roots, data.archive_roots, data.accept_inaccessible)
    except repo.FilesystemSetupClosedError as error:
        raise HTTPException(403, detail={
            'code': 'filesystem_setup_closed', 'message': str(error), 'params': {}}) from error
    except repo.FilesystemRootsRequiredError as error:
        raise HTTPException(400, detail={
            'code': 'filesystem_roots_required', 'message': str(error), 'params': {}}) from error
    except OperationBusyError as error:
        raise HTTPException(409, detail={
            'code': 'operation_busy', 'message': str(error), 'params': {}}) from error
    except (ValueError, OSError) as error:
        raise HTTPException(400, detail={
            'code': 'filesystem_setup_failed', 'message': str(error), 'params': {}}) from error


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


class ModelExtensionsInput(BaseModel):
    extensions: list[str]


@router.put('/config/model-extensions')
async def update_model_extensions(data: ModelExtensionsInput) -> dict:
    try:
        with dispatcher.configuration_change():
            return repo.update_model_extensions(data.extensions)
    except OperationBusyError as error:
        raise HTTPException(409, detail={
            'code': 'operation_busy', 'message': str(error), 'params': {}}) from error
    except ValueError as error:
        raise HTTPException(400, detail={
            'code': 'invalid_model_extensions', 'message': str(error), 'params': {}}) from error


class ModelMappingInput(BaseModel):
    working_root: str
    archive_root: str
    extensions: list[str] = Field(default_factory=list)


@router.get('/config/model-mapping-roots')
def get_model_mapping_roots() -> list[str]:
    return repo.model_mapping_roots()


@router.post('/config/model-mapping-preview')
def preview_model_mappings(data: ModelMappingInput) -> list[dict]:
    try:
        return repo.propose_model_mappings(
            data.working_root, data.archive_root, data.extensions)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error


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
        with dispatcher.configuration_change():
            return repo.update_repository_configuration(data.model_dump())
    except OperationBusyError as error:
        raise HTTPException(409, detail={
            "code": "operation_busy", "message": str(error), "params": {}}) from error
    except ValueError as error:
        raise HTTPException(400, str(error)) from error


@router.put('/config/models')
async def update_model_configuration(data: ModelConfigurationInput) -> dict:
    try:
        with dispatcher.configuration_change():
            return repo.update_model_configuration(data.model_dump())
    except OperationBusyError as error:
        raise HTTPException(409, detail={
            "code": "operation_busy", "message": str(error), "params": {}}) from error
    except ValueError as error:
        raise HTTPException(400, str(error)) from error


@router.put('/config/workflows')
async def update_workflow_configuration(data: WorkflowConfigurationInput) -> dict:
    try:
        with dispatcher.configuration_change():
            return repo.update_workflow_configuration(data.model_dump())
    except OperationBusyError as error:
        raise HTTPException(409, detail={
            "code": "operation_busy", "message": str(error), "params": {}}) from error
    except ValueError as error:
        raise HTTPException(400, str(error)) from error


@router.put('/config/model-type')
async def update_single_model_type(data: ModelTypeInput, original_name: str | None = None) -> dict:
    try:
        with dispatcher.configuration_change():
            current = repo.get_repository_configuration()
            types = current['model_types']
            name = original_name if original_name is not None else data.name.strip()
            index = next((i for i, item in enumerate(types) if item['name'] == name), None)
            if original_name is None and index is not None:
                raise ValueError('a model type with this name already exists')
            if original_name is not None and index is None:
                raise ValueError('the original model type no longer exists')
            if any(item['name'] == data.name.strip() and i != index for i, item in enumerate(types)):
                raise ValueError('a model type with this name already exists')
            if index is None:
                types.append(data.model_dump())
            else:
                types[index] = data.model_dump()
            return repo.update_model_configuration({'model_types': types})
    except OperationBusyError as error:
        raise HTTPException(409, detail={
            'code': 'operation_busy', 'message': str(error), 'params': {}}) from error
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
