# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: configuration.py
# purpose: REST access to repository settings and first-run acknowledgment
# ---------------------------------------------------------------------------

from fastapi import APIRouter, HTTPException, Request, Query
from pydantic import BaseModel, Field
from pathlib import Path

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


@router.post('/config/acknowledge-first-run')
async def acknowledge_first_run() -> dict:
    try:
        with dispatcher.configuration_change():
            return repo.acknowledge_first_run()
    except OperationBusyError as error:
        raise HTTPException(409, detail={
            'code': 'operation_busy', 'message': str(error), 'params': {}}) from error


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
async def get_repository_configuration(request: Request) -> dict:
    return repo.get_repository_configuration(request.headers.get('X-Archivist-Profile'))


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
            if original_name is None and current.get('mode') == 'standalone':
                if len(data.locations) != 1 or not data.locations[0].working_dir.strip():
                    raise HTTPException(400, detail={
                        'code': 'model_working_folder_required',
                        'message': 'Select one working folder before adding a model type.', 'params': {}})
                data.name = Path(data.locations[0].working_dir).name
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
        raise HTTPException(400, detail={
            'code': 'invalid_model_type', 'message': str(error), 'params': {}}) from error


@router.delete('/config/model-type')
async def delete_model_type(name: str, expected_model_count: int = Query(ge=0)) -> dict:
    try:
        with dispatcher.configuration_change():
            return repo.delete_model_type(name, expected_model_count)
    except OperationBusyError as error:
        raise HTTPException(409, detail={
            'code': 'operation_busy', 'message': str(error), 'params': {}}) from error
    except ValueError as error:
        code = str(error)
        message = ('The model count changed. Review the current count and confirm again.'
                   if code == 'model_type_count_changed' else 'The model type no longer exists.')
        raise HTTPException(409 if code == 'model_type_count_changed' else 404, detail={
            'code': code, 'message': message, 'params': {'name': name}}) from error
