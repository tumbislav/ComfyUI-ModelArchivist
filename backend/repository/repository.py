# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: repository.py
# purpose: Database operations
# ---------------------------------------------------------------------------

from typing import Callable, Set
from threading import Lock
import logging
import datetime
import os
from pathlib import Path
from time import monotonic
from uuid import uuid4

from sqlmodel import Session, create_engine, select, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.engine.base import Engine
from sqlalchemy import func
from sqlalchemy.orm import selectinload
from backend.repository.tables import (Model, Workflow, Collection, Component, ComponentSet,
                                       ComponentType, Tag, PrimaryObjectType, DeploymentStatus,
                                       ModelError, CollectionCollectionLink, ModelCollectionLink,
                                       WorkflowCollectionLink, UserDefinedType,
                                       UserDefinedObject, UserObjectCollectionLink,
                                       UserObjectClass, UserObjectError, UserObjectSet,
                                       UserObjectEntry, ApplicationSettings,
                                       ModelTypeSetting, ModelLocationSetting,
                                       WorkflowLocationSetting)
from backend.exception import ArcException
from backend.config import Configuration, OptionsConfig, get_config
from backend.environment import get_environment_provider
from backend.repository.migrations import update_database_schema
import backend.files.model_files as model_files
import backend.files.workflow_files as workflow_files
from backend.files.operations import (FileAction, FileSnapshot, OperationIssue, OperationPlan,
                                      action_transfer_size, atomic_copy, execute_file_action)

_logger: logging.Logger | None = None
_engine: Engine | None = None
_config: Configuration | None = None

lock = Lock()
_user_type_deletion_previews: dict[str, tuple[float, str, tuple]] = {}

_first_run: bool = False
_repo_started: bool = False


def create_scanner():
    """Lazily resolve the scanner to avoid a repository/scanner import cycle."""
    from backend.files.scanner import create_scanner as scanner_factory
    return scanner_factory()


def get_scanner():
    """Lazily resolve the current scanner."""
    from backend.files.scanner import get_scanner as scanner_getter
    return scanner_getter()

def prepare_database_file(db_file: Path) -> bool:
    """Validate the SQLite location and return whether a new database is needed."""
    parent = db_file.parent
    try:
        parent.mkdir(exist_ok=True, parents=True)
    except OSError as error:
        raise ArcException(ArcException.Code.INACCESSIBLE_FOLDER, f'{parent}: {error}') from error

    if not parent.is_dir() or not os.access(parent, os.R_OK | os.W_OK):
        raise ArcException(ArcException.Code.INACCESSIBLE_FOLDER, str(parent))

    try:
        if db_file.exists():
            if not db_file.is_file():
                raise ArcException(ArcException.Code.INVALID_DATABASE, f'{db_file} is not a file')
            if not os.access(db_file, os.R_OK | os.W_OK):
                raise ArcException(ArcException.Code.DATABASE_UNAVAILABLE, str(db_file))
            return db_file.stat().st_size == 0
    except ArcException:
        raise
    except OSError as error:
        raise ArcException(ArcException.Code.DATABASE_UNAVAILABLE, f'{db_file}: {error}') from error
    return True


def validate_database(engine: Engine, db_file: Path, first_run: bool) -> None:
    """Open SQLite and verify its structural integrity."""
    try:
        with engine.begin() as connection:
            result = connection.exec_driver_sql('PRAGMA quick_check').scalars().all()
            if result != ['ok']:
                raise ArcException(ArcException.Code.INVALID_DATABASE,
                                   f'{db_file}: {"; ".join(result)}')
    except ArcException:
        raise
    except (OSError, SQLAlchemyError) as error:
        code = (ArcException.Code.DATABASE_UNAVAILABLE if first_run
                else ArcException.Code.INVALID_DATABASE)
        raise ArcException(code, f'{db_file}: {error}') from error


def load_repository_configuration(config: Configuration) -> None:
    """Combine persistent settings with working locations supplied by the environment."""
    provider = get_environment_provider()
    config.mode = provider.mode
    config.reset_runtime_paths()
    with Session(_engine) as session:
        settings = session.get(ApplicationSettings, 1)
        if settings is None:
            settings = ApplicationSettings()
            session.add(settings)
            session.commit()
        config.options = OptionsConfig(
            update_json_metadata=settings.update_json_metadata,
            ignore_unknown_types=settings.ignore_unknown_types,
            always_recalc_hashes=settings.always_recalc_hashes)
        config.setup_required = not settings.setup_complete

        type_settings = {item.name: item for item in session.exec(
            select(ModelTypeSetting)).all()}
        config.model_type_labels = {
            name: item.display_name for name, item in type_settings.items()}
        config.model_extensions_by_type = {
            name: list(item.extensions) for name, item in type_settings.items()}

        model_locations = session.exec(select(ModelLocationSetting)).all()
        workflow_locations = session.exec(select(WorkflowLocationSetting)).all()
        if provider.mode == 'standalone':
            for location in model_locations:
                if not location.active or location.source != 'standalone' or not location.archive_dir:
                    continue
                config.add_model_locations(location.model_type, Path(location.working_dir),
                                           Path(location.archive_dir))
            for location in workflow_locations:
                if location.active and location.source == 'standalone' and location.archive_dir:
                    config.add_workflow_locations(Path(location.working_dir),
                                                  Path(location.archive_dir))
        else:
            discovered_models = provider.model_locations()
            discovered_paths = {str(item.working_dir) for item in discovered_models}
            stored_models = {location.working_dir: location for location in model_locations
                             if location.source == 'comfyui'}
            for location in stored_models.values():
                location.active = location.working_dir in discovered_paths
                session.add(location)
            for discovered in discovered_models:
                location = stored_models.get(str(discovered.working_dir))
                if location is None:
                    location = ModelLocationSetting(
                        model_type=discovered.model_type, source='comfyui',
                        working_dir=str(discovered.working_dir), active=True)
                    session.add(location)
                else:
                    location.model_type = discovered.model_type
                    location.active = True
                type_setting = type_settings.get(discovered.model_type)
                if type_setting is None:
                    type_setting = ModelTypeSetting(
                        name=discovered.model_type, display_name=discovered.model_type,
                        extensions=list(discovered.extensions))
                    session.add(type_setting)
                    type_settings[discovered.model_type] = type_setting
                config.model_type_labels[discovered.model_type] = type_setting.display_name
                config.model_extensions_by_type[discovered.model_type] = list(
                    discovered.extensions)
                if location.archive_dir:
                    config.add_model_locations(discovered.model_type,
                                               discovered.working_dir,
                                               Path(location.archive_dir))
                else:
                    config.unmapped_model_folders.setdefault(
                        discovered.model_type, []).append(discovered.working_dir)

            discovered_workflows = provider.workflow_locations()
            discovered_workflow_paths = {str(path) for path in discovered_workflows}
            stored_workflows = {location.working_dir: location for location in workflow_locations
                                if location.source == 'comfyui'}
            for location in stored_workflows.values():
                location.active = location.working_dir in discovered_workflow_paths
                session.add(location)
            for path in discovered_workflows:
                location = stored_workflows.get(str(path))
                if location is None:
                    location = WorkflowLocationSetting(
                        source='comfyui', working_dir=str(path), active=True)
                    session.add(location)
                if location.archive_dir:
                    config.add_workflow_locations(path, Path(location.archive_dir))
                else:
                    config.unmapped_workflow_folders.append(path)
            session.commit()


def start_repo():
    global _engine, _logger, _config, _first_run, _repo_started
    if _repo_started:
        return
    config = get_config()
    _logger = logging.getLogger('archivist.database')
    first_run = prepare_database_file(config.db_file)
    db_name = f'{config.dbms_prefix}{config.db_file}'
    engine = create_engine(db_name, echo=False)
    try:
        validate_database(engine, config.db_file, first_run)
        update_database_schema(engine)
    except Exception:
        engine.dispose()
        raise

    _engine = engine
    _config = config
    _first_run = first_run
    try:
        load_repository_configuration(config)
    except Exception:
        engine.dispose()
        _engine = None
        _config = None
        raise
    sql_logger = logging.getLogger('sqlalchemy.engine')
    sql_logger.addHandler(logging.FileHandler(_config.log_file))
    sql_logger.setLevel(_config.sql_log_level)
    _repo_started = True
    if _config.configured and not _config.read_only:
        sc = create_scanner()
        if sc is None:
            msg = 'Cannot create a scanner, aborting'
            _logger.critical(msg)
            raise RuntimeError(msg)
        sc.start(_config.options.always_recalc_hashes)


def repo_status():
    if not _repo_started:
        return {'started': False,
                'ready': False,
                'read_only': True if _config is None else _config.read_only}
    status_dict = {'started': True,
                   'first_run': _first_run,
                   'read_only': _config.read_only,
                   'setup_required': _config.setup_required,
                   'mode': _config.mode}
    sc = get_scanner()
    if sc is None:
        status_dict['ready'] = True
    else:
        scan_progress = sc.progress()
        status_dict['scanning'] = scan_progress['started'] and not scan_progress['finished']
        status_dict['ready'] = not status_dict['scanning']
    return status_dict


def get_repository_configuration() -> dict:
    """Return the persistent settings together with environment-derived locations."""
    with Session(_engine) as session:
        settings = session.get(ApplicationSettings, 1) or ApplicationSettings()
        model_types = session.exec(select(ModelTypeSetting)).all()
        locations = session.exec(select(ModelLocationSetting)).all()
        workflows = session.exec(select(WorkflowLocationSetting)).all()
        by_type: dict[str, list[dict]] = {}
        for location in locations:
            by_type.setdefault(location.model_type, []).append({
                'id': location.id,
                'working_dir': location.working_dir,
                'archive_dir': location.archive_dir,
                'source': location.source,
                'active': location.active,
            })
        return {
            'mode': _config.mode,
            'setup_complete': settings.setup_complete,
            'options': {
                'update_json_metadata': settings.update_json_metadata,
                'ignore_unknown_types': settings.ignore_unknown_types,
                'always_recalc_hashes': settings.always_recalc_hashes,
            },
            'model_types': [{
                'name': item.name,
                'display_name': item.display_name,
                'extensions': list(item.extensions),
                'locations': by_type.get(item.name, []),
            } for item in model_types],
            'workflow_locations': [{
                'id': item.id,
                'working_dir': item.working_dir,
                'archive_dir': item.archive_dir,
                'source': item.source,
                'active': item.active,
            } for item in workflows],
        }


def _normalized_location(value: str) -> str:
    if not value.strip():
        raise ValueError('folder paths cannot be empty')
    return str(Path(value).expanduser().absolute())


def update_repository_configuration(data: dict) -> dict:
    """Validate and persist repository locations and behavioral options."""
    model_types = data.get('model_types', [])
    workflow_locations = data.get('workflow_locations', [])
    if _config.mode == 'standalone' and any(
            len(item.get('locations', [])) > 1 for item in model_types):
        raise ValueError('standalone mode permits one working/archive pair per model type')
    if _config.mode == 'standalone' and len(workflow_locations) > 1:
        raise ValueError('standalone mode permits one workflow working/archive pair')

    seen: set[str] = set()
    for item in model_types:
        if not item.get('name', '').strip() or not item.get('display_name', '').strip():
            raise ValueError('model type names cannot be empty')
        extensions = item.get('extensions', [])
        if not extensions:
            raise ValueError(f'model type {item["name"]} requires at least one extension')
        for location in item.get('locations', []):
            for key in ('working_dir', 'archive_dir'):
                value = location.get(key)
                if key == 'archive_dir' and not value and _config.mode == 'comfyui':
                    continue
                normalized = _normalized_location(value or '')
                if normalized in seen:
                    raise ValueError(f'folder is reused by more than one location: {normalized}')
                seen.add(normalized)
    for location in workflow_locations:
        for key in ('working_dir', 'archive_dir'):
            value = location.get(key)
            if key == 'archive_dir' and not value and _config.mode == 'comfyui':
                continue
            normalized = _normalized_location(value or '')
            if normalized in seen:
                raise ValueError(f'folder is reused by more than one location: {normalized}')
            seen.add(normalized)

    with Session(_engine) as session:
        settings = session.get(ApplicationSettings, 1) or ApplicationSettings()
        options = data.get('options', {})
        for name in ('update_json_metadata', 'ignore_unknown_types', 'always_recalc_hashes'):
            if name in options:
                setattr(settings, name, bool(options[name]))
        session.add(settings)

        if _config.mode == 'standalone':
            for row in session.exec(select(ModelLocationSetting)).all():
                session.delete(row)
            for row in session.exec(select(WorkflowLocationSetting)).all():
                session.delete(row)
            for row in session.exec(select(ModelTypeSetting)).all():
                session.delete(row)
            session.flush()
            for item in model_types:
                session.add(ModelTypeSetting(
                    name=item['name'].strip(), display_name=item['display_name'].strip(),
                    extensions=sorted({f'.{value.lower().lstrip(".")}'
                                       for value in item['extensions']})))
                for location in item.get('locations', []):
                    session.add(ModelLocationSetting(
                        model_type=item['name'].strip(), source='standalone',
                        working_dir=_normalized_location(location['working_dir']),
                        archive_dir=_normalized_location(location['archive_dir'])))
            for location in workflow_locations:
                session.add(WorkflowLocationSetting(
                    source='standalone',
                    working_dir=_normalized_location(location['working_dir']),
                    archive_dir=_normalized_location(location['archive_dir'])))
        else:
            stored_types = {row.name: row for row in session.exec(
                select(ModelTypeSetting)).all()}
            stored_models = {row.working_dir: row for row in session.exec(
                select(ModelLocationSetting).where(ModelLocationSetting.source == 'comfyui')).all()}
            for item in model_types:
                type_row = stored_types.get(item['name'])
                if type_row is not None:
                    type_row.display_name = item['display_name'].strip()
                    session.add(type_row)
                for location in item.get('locations', []):
                    working = _normalized_location(location['working_dir'])
                    row = stored_models.get(working)
                    if row is None or not row.active:
                        raise ValueError(f'working folder is not supplied by ComfyUI: {working}')
                    row.archive_dir = (_normalized_location(location['archive_dir'])
                                       if location.get('archive_dir') else None)
                    session.add(row)
            stored_workflows = {row.working_dir: row for row in session.exec(
                select(WorkflowLocationSetting).where(
                    WorkflowLocationSetting.source == 'comfyui')).all()}
            for location in workflow_locations:
                working = _normalized_location(location['working_dir'])
                row = stored_workflows.get(working)
                if row is None or not row.active:
                    raise ValueError(f'workflow folder is not supplied by ComfyUI: {working}')
                row.archive_dir = (_normalized_location(location['archive_dir'])
                                   if location.get('archive_dir') else None)
                session.add(row)

        mapped_models = all(location.get('archive_dir') for item in model_types
                            for location in item.get('locations', []))
        has_models = any(item.get('locations') for item in model_types)
        mapped_workflows = bool(workflow_locations) and all(
            location.get('archive_dir') for location in workflow_locations)
        settings.setup_complete = bool(has_models and mapped_models and mapped_workflows)
        session.add(settings)
        session.commit()

    load_repository_configuration(_config)
    return get_repository_configuration()


def update_model_configuration(data: dict) -> dict:
    """Update only model settings while preserving workflow settings and options."""
    current = get_repository_configuration()
    current['model_types'] = data.get('model_types', [])
    return update_repository_configuration(current)


def update_workflow_configuration(data: dict) -> dict:
    """Update only workflow settings while preserving model settings and options."""
    current = get_repository_configuration()
    current['workflow_locations'] = data.get('workflow_locations', [])
    return update_repository_configuration(current)


def repository_counts() -> dict[str, int]:
    """Return counts of the logical objects displayed by the application."""
    if not _repo_started:
        return {'models': 0, 'workflows': 0, 'user_objects': 0, 'collections': 0}
    with Session(_engine) as session:
        return {
            'models': session.exec(select(func.count()).select_from(Model)).one(),
            'workflows': session.exec(select(func.count()).select_from(Workflow)).one(),
            'user_objects': session.exec(
                select(func.count()).select_from(UserDefinedObject)).one(),
            'collections': session.exec(select(func.count()).select_from(Collection)).one(),
        }

#-----------------------------------------------------------------------------------
#
# Scan
#
#-----------------------------------------------------------------------------------

def save_scanned_model(model: Model, tag_names: list[str]) -> None:
    """
    Save a full model from a scan. We have the following possibilities:
    - the model is not known: add the model,
    - the model is known, but has not been seen in this scan: update it,
    - the model is known and has already been seen in this scan: raise an exception.
    """
    with Session(_engine) as session:
        path_conflicts = session.exec(select(Model).where(
            Model.touched == model.touched,
            Model.type == model.type,
            Model.relative_path == model.relative_path,
            Model.file_name == model.file_name,
            Model.id != model.id,
        )).all()
        if path_conflicts:
            if ModelError.PATH_IDENTITY_CONFLICT.value not in model.errors:
                model.errors.append(ModelError.PATH_IDENTITY_CONFLICT.value)
            for conflict in path_conflicts:
                if ModelError.PATH_IDENTITY_CONFLICT.value not in conflict.errors:
                    conflict.errors = [*conflict.errors, ModelError.PATH_IDENTITY_CONFLICT.value]
                    session.add(conflict)
        known_models = session.exec(select(Model).where(Model.id == model.id)).all()
        if len(known_models) == 0:
            _logger.debug(f'adding model {model.internal_name}')
            model.tags = resolve_tags(session, tag_names)
            session.add(model)
            session.commit()
        else:
            _logger.debug(f'updating model {model.internal_name}')
            if len(known_models) > 1:
                all_names = ', '.join(m.internal_name for m in known_models)
                raise ArcException(ArcException.Code.DUPLICATE_MODEL,
                                         f'{model.id}, {all_names}')
            old_model = known_models[0]
            if old_model.touched == model.touched:
                old_sides = {item.where for item in old_model.component_sets if item.components}
                new_sides = {item.where for item in model.component_sets if item.components}
                merged_errors = set(old_model.errors) | set(model.errors)
                if 'w' in old_sides & new_sides:
                    merged_errors.add(ModelError.DUPLICATE_WORKING.value)
                if 'a' in old_sides & new_sides:
                    merged_errors.add(ModelError.DUPLICATE_ARCHIVE.value)
                if (old_model.file_name, old_model.relative_path, old_model.type) != (
                        model.file_name, model.relative_path, model.type):
                    merged_errors.add(ModelError.LOCATION_MISMATCH.value)
                old_model.errors = [error.value for error in ModelError if error.value in merged_errors]
                existing_by_side = {item.where: item for item in old_model.component_sets}
                for scanned_set in model.component_sets:
                    existing_set = existing_by_side.get(scanned_set.where)
                    if existing_set is None:
                        old_model.component_sets.append(scanned_set)
                        existing_by_side[scanned_set.where] = scanned_set
                    elif Path(existing_set.primary_dir).resolve() == Path(
                            scanned_set.primary_dir).resolve():
                        existing_set.components.extend(scanned_set.components)
                session.add(old_model)
                session.commit()
                return
            for component_set in list(old_model.component_sets):
                session.delete(component_set)
            session.flush()
            old_model.update_from(model)
            old_model.tags = resolve_tags(session, tag_names)
            old_model.component_sets = model.component_sets
            session.add(old_model)
            session.commit()

def save_scanned_workflow(workflow: Workflow, tag_names: list[str]) -> None:
    """
    Save a full workflow record.
    """
    with Session(_engine) as session:
        known_workflows = session.exec(select(Workflow).where(Workflow.id == workflow.id)).all()
        if len(known_workflows) == 0:
            _logger.debug(f'adding workflow {workflow.internal_name}')
            workflow.tags = resolve_tags(session, tag_names)
            session.add(workflow)
            session.commit()
        else:
            _logger.debug(f'updating workflow {workflow.internal_name}')
            if len(known_workflows) > 1:
                all_names = ', '.join(w.internal_name for w in known_workflows)
                raise ArcException(ArcException.Code.DUPLICATE_MODEL,
                                         f'{workflow.id}, {all_names}')
            old_workflow = known_workflows[0]
            if old_workflow.touched == workflow.touched:
                raise ArcException(ArcException.Code.DUPLICATE_MODEL,
                                   f'{workflow.internal_name} {workflow.id}, {old_workflow.touched}')
            for component_set in list(old_workflow.component_sets):
                session.delete(component_set)
            session.flush()
            old_workflow.update_from(workflow)
            old_workflow.tags = resolve_tags(session, tag_names)
            old_workflow.component_sets = workflow.component_sets
            session.add(old_workflow)
            session.commit()

def scan_cleanup(scan_timestamp: str):
    with Session(_engine) as session:
        models = session.exec(select(Model).where(Model.touched != scan_timestamp))
        for model in models:
            _logger.debug(f'deleting model {model.internal_name}')
            session.delete(model)
        workflows = session.exec(select(Workflow).where(Workflow.touched != scan_timestamp))
        for workflow in workflows:
            _logger.debug(f'deleting workflow {workflow.internal_name}')
            session.delete(workflow)
        user_objects = session.exec(select(UserDefinedObject).where(
            UserDefinedObject.touched != scan_timestamp))
        for user_object in user_objects:
            _logger.debug(f'deleting user-defined object {user_object.display_name}')
            session.delete(user_object)
        session.commit()


def user_types_for_scan() -> list[dict]:
    """Return detached type definitions needed by the filesystem scanner."""
    with Session(_engine) as session:
        return [item.representation() for item in session.exec(select(UserDefinedType)).all()]


def retain_oversized_user_object(type_id: str, relative_path: str,
                                 touched: str, observed_size: int) -> bool:
    """Keep a known oversized object stale and read-only; ignore an unknown one."""
    with Session(_engine) as session:
        item = session.exec(select(UserDefinedObject).where(
            UserDefinedObject.type_id == type_id,
            UserDefinedObject.relative_path == relative_path)).one_or_none()
        if item is None:
            return False
        item.touched = touched
        item.size = max(item.size, observed_size)
        if UserObjectError.OVER_SIZE_LIMIT.value not in item.errors:
            item.errors = [*item.errors, UserObjectError.OVER_SIZE_LIMIT.value]
        session.add(item)
        session.commit()
        return True


def retain_unreadable_user_type_objects(type_id: str, touched: str) -> None:
    """Prevent cleanup after a type root failed and mark its known objects read-only."""
    with Session(_engine) as session:
        items = session.exec(select(UserDefinedObject).where(
            UserDefinedObject.type_id == type_id)).all()
        for item in items:
            item.touched = touched
            if UserObjectError.UNREADABLE.value not in item.errors:
                item.errors = [*item.errors, UserObjectError.UNREADABLE.value]
            session.add(item)
        session.commit()


def save_scanned_user_object(scanned: UserDefinedObject) -> None:
    """Insert a discovered UDP object or refresh its filesystem state and metadata."""
    with Session(_engine) as session:
        item = session.exec(select(UserDefinedObject).where(
            UserDefinedObject.type_id == scanned.type_id,
            UserDefinedObject.relative_path == scanned.relative_path).options(
                selectinload(UserDefinedObject.sets))).one_or_none()
        if item is None:
            session.add(scanned)
        else:
            for object_set in list(item.sets):
                session.delete(object_set)
            session.flush()
            item.deployment = scanned.deployment
            item.size = scanned.size
            item.modified_at_ns = scanned.modified_at_ns
            item.touched = scanned.touched
            item.errors = scanned.errors
            item.sets = scanned.sets
            session.add(item)
        session.commit()

#-----------------------------------------------------------------------------------
#
# Models
#
#-----------------------------------------------------------------------------------

def update_model(updates: dict) -> dict:
    """
    Update an existing model. The items that may change are the name, internal name and tags.
    """
    if _config.read_only:
        raise ArcException(ArcException.Code.READ_ONLY, 'Model updates are disabled')
    with Session(_engine) as session:
        model: Model | None = session.get(Model, updates['id'])
        if model is None:
            msg = f'unknown model {updates["id"]} ({updates["internal_name"]})'
            _logger.error(msg)
            raise ArcException(ArcException.Code.UNKNOWN_MODEL, msg)
        _logger.debug(f'updating model {updates["id"]}')

        model_files.update_model(model, updates['file_name'], updates['internal_name'], updates['tags'])

        model.file_name = updates['file_name']
        model.internal_name = updates['internal_name']
        model.tags = resolve_tags(session, updates['tags'])
        model.touched = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()

        session.add(model)
        session.commit()
        working_path, archive_path = _model_paths(model)
        return model.representation(_config.model_types, working_path, archive_path)


def update_model_tags(ids: list[str], add: list[str], remove: list[str]) -> dict:
    """Apply tag additions and removals to several models."""
    if _config.read_only:
        raise ArcException(ArcException.Code.READ_ONLY, 'Model updates are disabled')
    results = []
    removed = set(remove)
    for model_id in dict.fromkeys(ids):
        current = get_model(model_id)
        tags = [tag for tag in current['tags'] if tag not in removed]
        tags.extend(tag for tag in add if tag not in tags)
        changed = dict(current)
        changed['tags'] = tags
        results.append(update_model(changed))
    return {'models': results}


def model_batch_operation(ids: list[str], operation: str, simulate: bool = True,
                          destination: DeploymentStatus | None = None,
                          progress: Callable[[dict], None] | None = None) -> dict:
    """Validate and execute one filesystem operation for several models."""
    model_ids = list(dict.fromkeys(ids))

    def run(model_id: str, member_simulate: bool,
            member_progress: Callable[[dict], None] | None = None) -> dict:
        if operation == 'synchronize':
            return synchronize_model(model_id, member_simulate, member_progress)
        return move_model(model_id, destination, member_simulate, member_progress)

    validations = [run(model_id, True) for model_id in model_ids]
    rejected = [result for result in validations if not result['allowed']]
    output = {
        'operation': operation,
        'object_type': 'model_batch',
        'object_id': 'batch',
        'simulate': simulate,
        'allowed': not rejected,
        'performed': False,
        'errors': [],
        'warnings': [],
        'actions': [action for result in validations for action in result['actions']],
        'members': validations,
    }
    if rejected:
        output['errors'] = [
            {'code': 'member_validation_failed',
             'message': f'{result["object_id"]}: {result["errors"]}'}
            for result in rejected
        ]
        return output
    if simulate:
        return output

    results = []
    total = len(model_ids)
    member_bytes = [sum(action_transfer_size(FileAction(
        action=action['action'], source=action['source'], destination=action['destination'],
        source_before=(FileSnapshot(**action['source_before'])
                       if action['source_before'] is not None else None),
        destination_before=FileSnapshot(**action['destination_before'])))
        for action in validation['actions']) for validation in validations]
    member_files = [len(validation['actions']) for validation in validations]
    bytes_total = sum(member_bytes)
    files_total = sum(member_files)
    bytes_before = 0
    files_before = 0
    if progress is not None:
        progress({'phase': 'executing', 'models_total': total, 'models_completed': 0,
                  'files_total': files_total, 'files_completed': 0,
                  'bytes_total': bytes_total, 'bytes_completed': 0})
    for index, model_id in enumerate(model_ids):
        def report_member(value: dict, completed=index) -> None:
            if progress is not None:
                progress({'phase': value.get('phase', 'executing'),
                          'models_total': total,
                          'models_completed': completed,
                          'current_model': model_id,
                          'files_total': files_total,
                          'files_completed': files_before + value.get('files_completed', 0),
                          'bytes_total': bytes_total,
                          'bytes_completed': bytes_before + value.get('bytes_completed', 0),
                          'current': value})
        result = run(model_id, False, report_member)
        results.append(result)
        if not result['allowed'] or not result['performed']:
            break
        if progress is not None:
            progress({'phase': 'executing', 'models_total': total,
                      'models_completed': index + 1, 'current_model': model_id,
                      'files_total': files_total,
                      'files_completed': files_before + member_files[index],
                      'bytes_total': bytes_total,
                      'bytes_completed': bytes_before + member_bytes[index]})
        bytes_before += member_bytes[index]
        files_before += member_files[index]
    output['members'] = results
    output['performed'] = len(results) == total and all(
        result['allowed'] and result['performed'] for result in results)
    if not output['performed']:
        output['allowed'] = False
        output['errors'].append({
            'code': 'member_execution_failed',
            'message': f'{len(results)} of {total} models were attempted',
        })
    return output

def deploy_model(id: str, deployment: DeploymentStatus) -> Model:
    """
    Move the model to either working set or archive, or synchronize them both.
    """
    if _config.read_only:
        raise ArcException(ArcException.Code.READ_ONLY, 'Model deployment is disabled')
    with Session(_engine) as session:
        model: Model | None = session.get(Model, id)
        if model is None:
            msg = f'unknown model {id}'
            _logger.error(msg)
            raise ArcException(ArcException.Code.UNKNOWN_MODEL, msg)
        _logger.debug(f'deploying model {model.internal_name} ({id}) to {deployment}')
    pass

def list_models(ordered, search_criteria: dict | None = None) -> list[dict]:
    with Session(_engine) as session:
        if ordered:
            statement = select(Model).order_by(Model.type, Model.internal_name)
        else:
            statement = select(Model).order_by(Model.type)
        criteria = search_criteria or {}
        types = criteria.get('types', [])
        if types:
            statement = statement.where(Model.type.in_(types))
        file_formats = [value.lower().removeprefix('.')
                        for value in criteria.get('file_formats', [])]
        if file_formats:
            statement = statement.where(Model.file_format.in_(file_formats))
        for tag in criteria.get('required_tags', []):
            statement = statement.where(Model.tags.any(Tag.tag == tag))
        for tag in criteria.get('forbidden_tags', []):
            statement = statement.where(~Model.tags.any(Tag.tag == tag))
        name_prefix = criteria.get('name_prefix', '')
        if name_prefix:
            escaped_prefix = (name_prefix.replace('\\', '\\\\')
                              .replace('%', '\\%').replace('_', '\\_'))
            statement = statement.where(Model.internal_name.ilike(
                f'{escaped_prefix}%', escape='\\'))
        return [model.summary(_config.model_types) for model in session.exec(statement).all()]

def get_model(id: str) -> dict:
    with Session(_engine) as session:
        model: Model | None = session.get(Model, id)
        if model is None:
            msg = f'model with hash {id} does not exist'
            _logger.info(msg)
            raise ArcException(ArcException.Code.UNKNOWN_MODEL, msg)
        working_path, archive_path = _model_paths(model)
        return model.representation(_config.model_types, working_path, archive_path)


def _paired_object_paths(component_sets: list[ComponentSet], relative_path: str,
                         folder_pairs: list[tuple[Path, Path]]) -> tuple[str | None, str | None]:
    """Resolve actual or prospective directories on both configured sides."""
    roots = {component_set.where: Path(component_set.primary_dir).resolve()
             for component_set in component_sets}
    relative = Path(relative_path)
    for working_root, archive_root in folder_pairs:
        working = Path(working_root).resolve()
        archive = Path(archive_root).resolve()
        if roots.get('w') == working or roots.get('a') == archive:
            return str(working / relative), str(archive / relative)
    return (
        str(roots['w'] / relative) if 'w' in roots else None,
        str(roots['a'] / relative) if 'a' in roots else None,
    )


def _model_paths(model: Model) -> tuple[str | None, str | None]:
    return _paired_object_paths(
        model.component_sets,
        model.relative_path,
        list(_config.model_folders.get(model.type, set())),
    )


def _workflow_paths(workflow: Workflow) -> tuple[str | None, str | None]:
    return _paired_object_paths(
        workflow.component_sets,
        workflow.relative_path,
        _config.workflow_folders,
    )


def _execute_model_actions(actions: list[FileAction],
                           progress: Callable[[dict], None] | None) -> dict:
    bytes_total = sum(action_transfer_size(action) for action in actions)
    files_completed = 0
    bytes_completed = 0

    def report_bytes(count: int) -> None:
        nonlocal bytes_completed
        bytes_completed += count
        if progress is not None:
            progress({'phase': 'executing', 'files_total': len(actions),
                      'files_completed': files_completed,
                      'bytes_total': max(bytes_total, bytes_completed),
                      'bytes_completed': bytes_completed})

    if progress is not None:
        progress({'phase': 'executing', 'files_total': len(actions),
                  'files_completed': 0, 'bytes_total': bytes_total,
                  'bytes_completed': 0})
    for action in actions:
        execute_file_action(action, report_bytes)
        files_completed += 1
        if progress is not None:
            progress({'phase': 'executing', 'files_total': len(actions),
                      'files_completed': files_completed,
                      'bytes_total': max(bytes_total, bytes_completed),
                      'bytes_completed': bytes_completed})
    return {'phase': 'finalizing', 'files_total': len(actions),
            'files_completed': files_completed,
            'bytes_total': max(bytes_total, bytes_completed),
            'bytes_completed': bytes_completed}


def synchronize_model(id: str, simulate: bool = True,
                      progress: Callable[[dict], None] | None = None) -> dict:
    plan = OperationPlan(operation='synchronize', object_type='model',
                         object_id=id, simulate=simulate)
    with Session(_engine) as session:
        model: Model | None = session.get(Model, id)
        if model is None:
            plan.reject('unknown_model', f'model {id} does not exist')
            return plan.to_dict()
        if _config.read_only:
            plan.reject('application_read_only', 'application is running read-only')
            return plan.to_dict()
        if model.read_only:
            plan.reject('model_read_only', f'model has errors: {", ".join(model.errors)}')
            return plan.to_dict()

        sets = {side: [item for item in model.component_sets if item.where == side]
                for side in ('w', 'a')}
        if len(sets['w']) > 1 or len(sets['a']) > 1:
            plan.reject('ambiguous_components', 'model has multiple component sets on one side')
            return plan.to_dict()
        source_side = 'w' if sets['w'] and sets['w'][0].components else (
            'a' if sets['a'] and sets['a'][0].components else None)
        if source_side is None:
            plan.reject('missing_source', 'model has no source files')
            return plan.to_dict()
        destination_side = 'a' if source_side == 'w' else 'w'
        plan.source_side = 'working' if source_side == 'w' else 'archive'
        source_set = sets[source_side][0]
        destination_set = sets[destination_side][0] if sets[destination_side] else None

        destination_primary = None
        destination_examples = None
        if destination_set is not None:
            destination_primary = Path(destination_set.primary_dir)
            destination_examples = (Path(destination_set.examples_dir)
                                    if destination_set.examples_dir else None)
        else:
            source_primary = Path(source_set.primary_dir).resolve()
            for working_root, archive_root in _config.model_folders.get(model.type, set()):
                candidate_root = Path(working_root if source_side == 'w' else archive_root).resolve()
                try:
                    relative_root = source_primary.relative_to(candidate_root)
                except ValueError:
                    continue
                other_root = Path(archive_root if source_side == 'w' else working_root)
                destination_primary = other_root / relative_root
                destination_examples = other_root.parent / 'examples' / model.id
                break
        if destination_primary is None:
            plan.reject('unmapped_destination',
                        f'no configured destination for {source_set.primary_dir}')
            return plan.to_dict()

        def component_key(component: Component) -> tuple[str, str, str]:
            return (str(component.component_type), component.relative_path, component.file_name)

        destination_components = ({component_key(component): component
                                   for component in destination_set.components}
                                  if destination_set else {})
        source_keys = set()
        try:
            for component in source_set.components:
                key = component_key(component)
                source_keys.add(key)
                source_path = Path(component.file_dir) / component.file_name
                destination_root = (destination_examples
                                    if component.component_type == ComponentType.EXAMPLE
                                    else destination_primary)
                if destination_root is None:
                    plan.reject('unmapped_destination', 'examples destination is not configured')
                    return plan.to_dict()
                destination_path = destination_root / component.relative_path / component.file_name
                include_hash = component.component_type != ComponentType.MODEL
                source_snapshot = FileSnapshot.capture(source_path, include_hash=include_hash)
                destination_snapshot = FileSnapshot.capture(destination_path, include_hash=include_hash)
                if not source_snapshot.exists:
                    plan.reject('missing_source', str(source_path))
                    return plan.to_dict()
                needs_copy = not destination_snapshot.exists
                if include_hash and destination_snapshot.exists:
                    needs_copy = source_snapshot.sha256 != destination_snapshot.sha256
                if needs_copy:
                    plan.actions.append(FileAction('copy', str(source_path),
                                                   str(destination_path), source_snapshot,
                                                   destination_snapshot))
            for key, component in destination_components.items():
                if key in source_keys:
                    continue
                destination_path = Path(component.file_dir) / component.file_name
                snapshot = FileSnapshot.capture(destination_path, include_hash=False)
                if snapshot.exists:
                    plan.actions.append(FileAction('remove', None, str(destination_path),
                                                   None, snapshot))
        except OSError as error:
            plan.reject('unreadable_file', str(error))
            return plan.to_dict()

        if simulate:
            return plan.to_dict()
        try:
            final_progress = _execute_model_actions(plan.actions, progress)
            if progress is not None:
                progress(final_progress)
        except (OSError, RuntimeError, ValueError) as error:
            plan.reject('execution_failed', str(error))
            return plan.to_dict()

        if destination_set is not None:
            model.component_sets.remove(destination_set)
            session.delete(destination_set)
            session.flush()
        copied_components = []
        for component in source_set.components:
            root = (destination_examples if component.component_type == ComponentType.EXAMPLE
                    else destination_primary)
            path = root / component.relative_path / component.file_name
            stat = path.stat()
            copied_components.append(Component(file_name=component.file_name,
                                               relative_path=component.relative_path,
                                               size=stat.st_size,
                                               modified_at_ns=stat.st_mtime_ns,
                                               component_type=component.component_type,
                                               touched=model.touched))
        new_destination_set = ComponentSet(where=destination_side,
                                           primary_dir=str(destination_primary),
                                           examples_dir=(str(destination_examples)
                                                         if destination_examples else None),
                                           model=model,
                                           components=copied_components)
        model.component_sets.append(new_destination_set)
        model.deployment = str(DeploymentStatus.SYNCED)
        session.add(model)
        session.commit()
        plan.performed = True
        return plan.to_dict()


def move_model(id: str, destination: DeploymentStatus,
               simulate: bool = True,
               progress: Callable[[dict], None] | None = None) -> dict:
    plan = OperationPlan(operation='move', object_type='model',
                         object_id=id, simulate=simulate)
    try:
        destination = DeploymentStatus(destination)
    except ValueError:
        plan.reject('invalid_destination', str(destination))
        return plan.to_dict()
    if destination not in (DeploymentStatus.WORKING, DeploymentStatus.ARCHIVE):
        plan.reject('invalid_destination', str(destination))
        return plan.to_dict()
    destination_side = 'w' if destination == DeploymentStatus.WORKING else 'a'
    source_side = 'a' if destination_side == 'w' else 'w'
    plan.source_side = 'archive' if source_side == 'a' else 'working'

    with Session(_engine) as session:
        model: Model | None = session.get(Model, id)
        if model is None:
            plan.reject('unknown_model', f'model {id} does not exist')
            return plan.to_dict()
        if _config.read_only or model.read_only:
            plan.reject('read_only', 'model cannot be moved while read-only')
            return plan.to_dict()
        sets = {side: [item for item in model.component_sets if item.where == side]
                for side in ('w', 'a')}
        if len(sets['w']) > 1 or len(sets['a']) > 1:
            plan.reject('ambiguous_components', 'model has multiple component sets on one side')
            return plan.to_dict()
        source_set = sets[source_side][0] if sets[source_side] else None
        destination_set = sets[destination_side][0] if sets[destination_side] else None
        if source_set is None or not source_set.components:
            if destination_set and destination_set.components:
                if not simulate:
                    model.deployment = str(destination)
                    session.add(model)
                    session.commit()
                    plan.performed = True
                return plan.to_dict()
            plan.reject('missing_source', 'model has no files to move')
            return plan.to_dict()

        if destination_set is not None:
            destination_primary = Path(destination_set.primary_dir)
            destination_examples = (Path(destination_set.examples_dir)
                                    if destination_set.examples_dir else None)
        else:
            destination_primary = None
            destination_examples = None
            source_primary = Path(source_set.primary_dir).resolve()
            for working_root, archive_root in _config.model_folders.get(model.type, set()):
                candidate = Path(working_root if source_side == 'w' else archive_root).resolve()
                try:
                    relative_root = source_primary.relative_to(candidate)
                except ValueError:
                    continue
                other_root = Path(archive_root if destination_side == 'a' else working_root)
                destination_primary = other_root / relative_root
                destination_examples = other_root.parent / 'examples' / model.id
                break
        if destination_primary is None:
            plan.reject('unmapped_destination', str(source_set.primary_dir))
            return plan.to_dict()

        def component_key(component: Component) -> tuple[str, str, str]:
            return (str(component.component_type), component.relative_path, component.file_name)

        destination_components = ({component_key(component): component
                                   for component in destination_set.components}
                                  if destination_set else {})
        source_keys = set()
        transfers = []
        source_removals = []
        destination_removals = []
        try:
            for component in source_set.components:
                key = component_key(component)
                source_keys.add(key)
                source_path = Path(component.file_dir) / component.file_name
                root = (destination_examples if component.component_type == ComponentType.EXAMPLE
                        else destination_primary)
                if root is None:
                    plan.reject('unmapped_destination', 'examples destination is not configured')
                    return plan.to_dict()
                destination_path = root / component.relative_path / component.file_name
                include_hash = component.component_type != ComponentType.MODEL
                source_snapshot = FileSnapshot.capture(source_path, include_hash=include_hash)
                destination_snapshot = FileSnapshot.capture(destination_path, include_hash=include_hash)
                if not source_snapshot.exists:
                    plan.reject('missing_source', str(source_path))
                    return plan.to_dict()
                already_present = destination_snapshot.exists and (
                    not include_hash or source_snapshot.sha256 == destination_snapshot.sha256)
                if already_present:
                    source_removals.append(FileAction('remove', None, str(source_path),
                                                      None, source_snapshot))
                else:
                    transfers.append(FileAction('move', str(source_path), str(destination_path),
                                                source_snapshot, destination_snapshot))
            for key, component in destination_components.items():
                if key in source_keys:
                    continue
                path = Path(component.file_dir) / component.file_name
                snapshot = FileSnapshot.capture(path)
                if snapshot.exists:
                    destination_removals.append(FileAction('remove', None, str(path), None, snapshot))
        except OSError as error:
            plan.reject('unreadable_file', str(error))
            return plan.to_dict()
        plan.actions.extend(transfers + destination_removals + source_removals)
        if simulate:
            return plan.to_dict()
        try:
            final_progress = _execute_model_actions(plan.actions, progress)
            if progress is not None:
                progress(final_progress)
        except (OSError, RuntimeError, ValueError) as error:
            plan.reject('execution_failed', str(error))
            return plan.to_dict()

        new_components = []
        for component in source_set.components:
            root = (destination_examples if component.component_type == ComponentType.EXAMPLE
                    else destination_primary)
            path = root / component.relative_path / component.file_name
            stat = path.stat()
            new_components.append(Component(file_name=component.file_name,
                                            relative_path=component.relative_path,
                                            size=stat.st_size,
                                            modified_at_ns=stat.st_mtime_ns,
                                            component_type=component.component_type,
                                            touched=model.touched))
        for item in (source_set, destination_set):
            if item is not None:
                model.component_sets.remove(item)
                session.delete(item)
        session.flush()
        model.component_sets.append(ComponentSet(
            where=destination_side,
            primary_dir=str(destination_primary),
            examples_dir=str(destination_examples) if destination_examples else None,
            model=model,
            components=new_components,
        ))
        model.deployment = str(destination)
        session.add(model)
        session.commit()
        plan.performed = True
        return plan.to_dict()

#-----------------------------------------------------------------------------------
#
# Workflows
#
#-----------------------------------------------------------------------------------

def list_workflows(ordered: bool, search_criteria: dict | None = None) -> list[dict]:
    with Session(_engine) as session:
        if ordered:
            statement = select(Workflow).order_by(Workflow.internal_name)
        else:
            statement = select(Workflow).order_by(Workflow.internal_name)
        criteria = search_criteria or {}
        for tag in criteria.get('required_tags', []):
            statement = statement.where(Workflow.tags.any(Tag.tag == tag))
        for tag in criteria.get('forbidden_tags', []):
            statement = statement.where(~Workflow.tags.any(Tag.tag == tag))
        name_prefix = criteria.get('name_prefix', '')
        if name_prefix:
            escaped_prefix = (name_prefix.replace('\\', '\\\\')
                                          .replace('%', '\\%')
                                          .replace('_', '\\_'))
            statement = statement.where(
                Workflow.internal_name.ilike(f'{escaped_prefix}%', escape='\\'))
        return [workflow.summary() for workflow in session.exec(statement).all()]


def get_workflow(id: str) -> dict:
    with Session(_engine) as session:
        workflow: Workflow | None = session.get(Workflow, id)
        if workflow is None:
            msg = f'workflow with id {id} does not exist'
            _logger.info(msg)
            raise ArcException(ArcException.Code.UNKNOWN_WORKFLOW, msg)
        working_path, archive_path = _workflow_paths(workflow)
        return workflow.representation(working_path, archive_path)


def update_workflow(updates: dict) -> dict:
    """Update workflow metadata in the database and deployed JSON files."""
    if _config.read_only:
        raise ArcException(ArcException.Code.READ_ONLY, 'Workflow updates are disabled')
    with Session(_engine) as session:
        workflow = session.get(Workflow, updates['id'])
        if workflow is None:
            raise ArcException(ArcException.Code.UNKNOWN_WORKFLOW, updates['id'])
        if workflow.read_only:
            raise ArcException(ArcException.Code.READ_ONLY, 'Workflow is read-only')
        try:
            workflow_files.update_workflow(
                workflow, updates['file_name'], updates['internal_name'],
                updates.get('purpose', ''), updates.get('tags', []))
        except (OSError, UnicodeError, ValueError, TypeError) as error:
            raise ArcException(ArcException.Code.INACCESSIBLE_FILE, str(error)) from error
        workflow.file_name = updates['file_name']
        workflow.internal_name = updates['internal_name']
        workflow.purpose = updates.get('purpose', '')
        workflow.tags = resolve_tags(session, updates.get('tags', []))
        workflow.touched = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
        session.add(workflow)
        session.commit()
        working_path, archive_path = _workflow_paths(workflow)
        return workflow.representation(working_path, archive_path)


def update_workflow_tags(ids: list[str], add: list[str], remove: list[str]) -> dict:
    """Apply tag additions and removals to several workflows."""
    results = []
    removed = set(remove)
    for workflow_id in dict.fromkeys(ids):
        current = get_workflow(workflow_id)
        tags = [tag for tag in current['tags'] if tag not in removed]
        tags.extend(tag for tag in add if tag not in tags)
        results.append(update_workflow({**current, 'tags': tags}))
    return {'workflows': results}


def workflow_batch_operation(ids: list[str], operation: str, simulate: bool = True,
                             destination: DeploymentStatus | None = None) -> dict:
    """Preflight and synchronously execute an operation for several workflows."""
    workflow_ids = list(dict.fromkeys(ids))

    def run(workflow_id: str, member_simulate: bool) -> dict:
        if operation == 'synchronize':
            return synchronize_workflow(workflow_id, member_simulate)
        return move_workflow(workflow_id, destination, member_simulate)

    validations = [run(workflow_id, True) for workflow_id in workflow_ids]
    rejected = [result for result in validations if not result['allowed']]
    output = {'operation': operation, 'object_type': 'workflow_batch',
              'object_id': 'batch', 'simulate': simulate, 'allowed': not rejected,
              'performed': False, 'errors': [], 'warnings': [],
              'actions': [action for result in validations for action in result['actions']],
              'members': validations}
    if rejected:
        output['errors'] = [{'code': 'member_validation_failed',
                             'message': f'{result["object_id"]}: {result["errors"]}'}
                            for result in rejected]
        return output
    if simulate:
        return output
    results = [run(workflow_id, False) for workflow_id in workflow_ids]
    output['members'] = results
    output['performed'] = all(result['allowed'] and result['performed'] for result in results)
    output['allowed'] = output['performed']
    if not output['performed']:
        output['errors'].append({'code': 'member_execution_failed',
                                 'message': 'A workflow operation failed'})
    return output


def synchronize_workflow(id: str, simulate: bool = True) -> dict:
    plan = OperationPlan(operation='synchronize', object_type='workflow',
                         object_id=id, simulate=simulate)
    with Session(_engine) as session:
        workflow: Workflow | None = session.get(Workflow, id)
        if workflow is None:
            plan.reject('unknown_workflow', f'workflow {id} does not exist')
            return plan.to_dict()
        if _config.read_only:
            plan.reject('application_read_only', 'application is running read-only')
            return plan.to_dict()
        if workflow.read_only:
            plan.reject('workflow_read_only',
                        f'workflow has errors: {", ".join(workflow.errors)}')
            return plan.to_dict()

        components = {
            side: [(component_set, component)
                   for component_set in workflow.component_sets if component_set.where == side
                   for component in component_set.components
                   if component.component_type == ComponentType.WORKFLOW]
            for side in ('w', 'a')
        }
        if len(components['w']) > 1 or len(components['a']) > 1:
            plan.reject('ambiguous_components', 'workflow has multiple files on one side')
            return plan.to_dict()
        source_side = 'w' if components['w'] else 'a' if components['a'] else None
        if source_side is None:
            plan.reject('missing_source', 'workflow has no source file')
            return plan.to_dict()
        destination_side = 'a' if source_side == 'w' else 'w'
        plan.source_side = 'working' if source_side == 'w' else 'archive'
        source_set, source_component = components[source_side][0]
        source_path = Path(source_component.file_dir) / source_component.file_name

        destination_component = None
        destination_set = None
        if components[destination_side]:
            destination_set, destination_component = components[destination_side][0]
            destination_path = Path(destination_component.file_dir) / destination_component.file_name
        else:
            source_root = Path(source_set.primary_dir).resolve()
            destination_root = None
            for working_root, archive_root in _config.workflow_folders:
                if source_side == 'w' and Path(working_root).resolve() == source_root:
                    destination_root = Path(archive_root)
                    break
                if source_side == 'a' and Path(archive_root).resolve() == source_root:
                    destination_root = Path(working_root)
                    break
            if destination_root is None:
                plan.reject('unmapped_destination',
                            f'no configured destination for {source_set.primary_dir}')
                return plan.to_dict()
            destination_path = (destination_root / source_component.relative_path /
                                source_component.file_name)

        try:
            source_snapshot = FileSnapshot.capture(source_path, include_hash=True)
            destination_snapshot = FileSnapshot.capture(destination_path, include_hash=True)
        except OSError as error:
            plan.reject('unreadable_file', str(error))
            return plan.to_dict()
        if not source_snapshot.exists:
            plan.reject('missing_source', str(source_path))
            return plan.to_dict()
        if (not destination_snapshot.exists or
                source_snapshot.sha256 != destination_snapshot.sha256):
            plan.actions.append(FileAction(action='copy',
                                           source=str(source_path),
                                           destination=str(destination_path),
                                           source_before=source_snapshot,
                                           destination_before=destination_snapshot))
        if simulate:
            return plan.to_dict()

        try:
            for action in plan.actions:
                atomic_copy(action)
        except (OSError, RuntimeError) as error:
            plan.reject('execution_failed', str(error))
            return plan.to_dict()

        destination_stat = destination_path.stat()
        source_stat = source_path.stat()
        source_component.size = source_stat.st_size
        source_component.modified_at_ns = source_stat.st_mtime_ns
        if destination_set is None:
            destination_set = ComponentSet(where=destination_side,
                                           primary_dir=str(destination_root),
                                           workflow=workflow,
                                           components=[])
            workflow.component_sets.append(destination_set)
        if destination_component is None:
            destination_component = Component(
                file_name=source_component.file_name,
                relative_path=source_component.relative_path,
                component_type=ComponentType.WORKFLOW,
                touched=workflow.touched,
            )
            destination_set.components.append(destination_component)
        destination_component.size = destination_stat.st_size
        destination_component.modified_at_ns = destination_stat.st_mtime_ns
        workflow.deployment = str(DeploymentStatus.SYNCED)
        session.add(workflow)
        session.commit()
        plan.performed = True
        return plan.to_dict()


def move_workflow(id: str, destination: DeploymentStatus,
                  simulate: bool = True) -> dict:
    plan = OperationPlan(operation='move', object_type='workflow',
                         object_id=id, simulate=simulate)
    try:
        destination = DeploymentStatus(destination)
    except ValueError:
        plan.reject('invalid_destination', str(destination))
        return plan.to_dict()
    if destination not in (DeploymentStatus.WORKING, DeploymentStatus.ARCHIVE):
        plan.reject('invalid_destination', str(destination))
        return plan.to_dict()
    destination_side = 'w' if destination == DeploymentStatus.WORKING else 'a'
    source_side = 'a' if destination_side == 'w' else 'w'
    plan.source_side = 'archive' if source_side == 'a' else 'working'

    with Session(_engine) as session:
        workflow: Workflow | None = session.get(Workflow, id)
        if workflow is None:
            plan.reject('unknown_workflow', f'workflow {id} does not exist')
            return plan.to_dict()
        if _config.read_only or workflow.read_only:
            plan.reject('read_only', 'workflow cannot be moved while read-only')
            return plan.to_dict()
        sets = {side: [item for item in workflow.component_sets if item.where == side]
                for side in ('w', 'a')}
        if len(sets['w']) > 1 or len(sets['a']) > 1:
            plan.reject('ambiguous_components', 'workflow has multiple component sets on one side')
            return plan.to_dict()
        source_set = sets[source_side][0] if sets[source_side] else None
        destination_set = sets[destination_side][0] if sets[destination_side] else None
        if source_set is None or not source_set.components:
            if destination_set and destination_set.components:
                if not simulate:
                    workflow.deployment = str(destination)
                    session.add(workflow)
                    session.commit()
                    plan.performed = True
                return plan.to_dict()
            plan.reject('missing_source', 'workflow has no files to move')
            return plan.to_dict()
        if len(source_set.components) != 1:
            plan.reject('ambiguous_components', 'workflow source does not contain one file')
            return plan.to_dict()
        source_component = source_set.components[0]
        source_path = Path(source_component.file_dir) / source_component.file_name

        destination_component = (destination_set.components[0]
                                 if destination_set and destination_set.components else None)
        if destination_component is not None:
            destination_path = Path(destination_component.file_dir) / destination_component.file_name
            destination_root = Path(destination_set.primary_dir)
        else:
            destination_root = None
            source_root = Path(source_set.primary_dir).resolve()
            for working_root, archive_root in _config.workflow_folders:
                candidate = Path(archive_root if source_side == 'a' else working_root).resolve()
                if candidate == source_root:
                    destination_root = Path(working_root if destination_side == 'w' else archive_root)
                    break
            if destination_root is None:
                plan.reject('unmapped_destination', str(source_set.primary_dir))
                return plan.to_dict()
            destination_path = destination_root / source_component.relative_path / source_component.file_name
        try:
            source_snapshot = FileSnapshot.capture(source_path, include_hash=True)
            destination_snapshot = FileSnapshot.capture(destination_path, include_hash=True)
        except OSError as error:
            plan.reject('unreadable_file', str(error))
            return plan.to_dict()
        if not source_snapshot.exists:
            plan.reject('missing_source', str(source_path))
            return plan.to_dict()
        if (destination_snapshot.exists and
                destination_snapshot.sha256 == source_snapshot.sha256):
            plan.actions.append(FileAction('remove', None, str(source_path),
                                           None, source_snapshot))
        else:
            plan.actions.append(FileAction('move', str(source_path), str(destination_path),
                                           source_snapshot, destination_snapshot))
        if simulate:
            return plan.to_dict()
        try:
            for action in plan.actions:
                execute_file_action(action)
        except (OSError, RuntimeError, ValueError) as error:
            plan.reject('execution_failed', str(error))
            return plan.to_dict()

        modelled_path = destination_path
        stat = modelled_path.stat()
        for item in (source_set, destination_set):
            if item is not None:
                workflow.component_sets.remove(item)
                session.delete(item)
        session.flush()
        workflow.component_sets.append(ComponentSet(
            where=destination_side,
            primary_dir=str(destination_root),
            workflow=workflow,
            components=[Component(file_name=modelled_path.name,
                                  relative_path=source_component.relative_path,
                                  size=stat.st_size,
                                  modified_at_ns=stat.st_mtime_ns,
                                  component_type=ComponentType.WORKFLOW,
                                  touched=workflow.touched)],
        ))
        workflow.deployment = str(destination)
        session.add(workflow)
        session.commit()
        plan.performed = True
        return plan.to_dict()

#-----------------------------------------------------------------------------------
#
# User-defined types and objects
#
#-----------------------------------------------------------------------------------

SMALL_OBJECT_LIMIT = 1024 * 1024
DEFAULT_OBJECT_LIMIT = 10 * 1024 * 1024


def _normalized_extensions(values: object) -> list[str]:
    if not isinstance(values, list):
        raise ArcException(ArcException.Code.INVALID_USER_TYPE, 'extensions must be a list')
    normalized = []
    for value in values:
        if not isinstance(value, str):
            raise ArcException(ArcException.Code.INVALID_USER_TYPE,
                               'extensions must contain strings')
        extension = value.strip().lower().removeprefix('.')
        if not extension or '/' in extension or '\\' in extension:
            raise ArcException(ArcException.Code.INVALID_USER_TYPE,
                               f'invalid extension {value!r}')
        if extension not in normalized:
            normalized.append(extension)
    return normalized


def _paths_overlap(first: Path, second: Path) -> bool:
    try:
        return first == second or first.is_relative_to(second) or second.is_relative_to(first)
    except ValueError:
        return False


def _validate_user_type(data: dict, current: UserDefinedType | None = None,
                        object_count: int = 0) -> dict:
    name = data.get('name')
    short_name = data.get('short_name')
    purpose = data.get('purpose', '')
    icon = data.get('icon')
    object_class = data.get('object_class')
    small = data.get('small', False)
    size_limit = data.get('size_limit', SMALL_OBJECT_LIMIT if small else DEFAULT_OBJECT_LIMIT)
    if not isinstance(name, str) or not name.strip():
        raise ArcException(ArcException.Code.INVALID_USER_TYPE, 'name is required')
    if (not isinstance(short_name, str) or not short_name.strip() or
            len(short_name.strip()) > 8):
        raise ArcException(ArcException.Code.INVALID_USER_TYPE,
                           'short name is required and cannot exceed 8 characters')
    if not isinstance(purpose, str) or not isinstance(icon, str) or not icon.strip():
        raise ArcException(ArcException.Code.INVALID_USER_TYPE,
                           'purpose and icon are invalid')
    if object_class not in (UserObjectClass.FILE.value, UserObjectClass.FOLDER.value):
        raise ArcException(ArcException.Code.INVALID_USER_TYPE, 'invalid object class')
    if not isinstance(small, bool) or not isinstance(size_limit, int) or size_limit <= 0:
        raise ArcException(ArcException.Code.INVALID_USER_TYPE, 'invalid size limit')
    if small and size_limit > SMALL_OBJECT_LIMIT:
        raise ArcException(ArcException.Code.INVALID_USER_TYPE,
                           'small types cannot exceed 1 MiB')
    extensions = _normalized_extensions(data.get('extensions', []))
    if object_class == UserObjectClass.FILE.value and not extensions:
        raise ArcException(ArcException.Code.INVALID_USER_TYPE,
                           'file types require at least one extension')
    if object_class == UserObjectClass.FOLDER.value and extensions:
        raise ArcException(ArcException.Code.INVALID_USER_TYPE,
                           'folder types cannot define extensions')
    working_value = data.get('working_dir', '')
    archive_value = data.get('archive_dir', '')
    if not isinstance(working_value, str) or not working_value.strip() or not isinstance(
            archive_value, str) or not archive_value.strip():
        raise ArcException(ArcException.Code.INVALID_USER_TYPE, 'both locations are required')
    try:
        working_dir = Path(working_value).resolve(strict=False)
        archive_dir = Path(archive_value).resolve(strict=False)
    except OSError as error:
        raise ArcException(ArcException.Code.INVALID_USER_TYPE, str(error)) from error
    if _paths_overlap(working_dir, archive_dir):
        raise ArcException(ArcException.Code.INVALID_USER_TYPE,
                           'working and archive locations overlap')
    if current is not None and object_count:
        if object_class != current.object_class:
            raise ArcException(ArcException.Code.USER_TYPE_IN_USE,
                               'object class cannot change while objects exist')
        if str(working_dir) != current.working_dir or str(archive_dir) != current.archive_dir:
            raise ArcException(ArcException.Code.USER_TYPE_IN_USE,
                               'locations cannot change while objects exist')
    return {'name': name.strip(), 'short_name': short_name.strip(),
            'purpose': purpose, 'icon': icon.strip(),
            'object_class': object_class, 'small': small, 'size_limit': size_limit,
            'extensions': extensions, 'working_dir': str(working_dir),
            'archive_dir': str(archive_dir)}


def _validate_user_type_roots(session: Session, values: dict,
                              current_id: str | None = None) -> None:
    candidates = [Path(values['working_dir']), Path(values['archive_dir'])]
    configured = []
    if _config is not None:
        configured.extend(Path(path).resolve() for path in _config.all_working)
        configured.extend(Path(path).resolve() for path in _config.all_archive)
    existing = session.exec(select(UserDefinedType)).all()
    configured.extend(Path(item.working_dir) for item in existing if item.id != current_id)
    configured.extend(Path(item.archive_dir) for item in existing if item.id != current_id)
    for candidate in candidates:
        for managed in configured:
            if _paths_overlap(candidate, managed):
                raise ArcException(ArcException.Code.INVALID_USER_TYPE,
                                   f'location overlaps managed root {managed}')
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            next(candidate.iterdir(), None)
            if not os.access(candidate, os.R_OK | os.W_OK):
                raise OSError('location is not readable and writable')
        except OSError as error:
            raise ArcException(ArcException.Code.INACCESSIBLE_FOLDER,
                               f'{candidate}: {error}') from error


def list_user_types() -> list[dict]:
    with Session(_engine) as session:
        statement = select(UserDefinedType).options(
            selectinload(UserDefinedType.objects)).order_by(UserDefinedType.name)
        return [item.summary() for item in session.exec(statement).all()]


def get_user_type(id: str) -> dict:
    with Session(_engine) as session:
        item = session.exec(select(UserDefinedType).where(UserDefinedType.id == id).options(
            selectinload(UserDefinedType.objects))).one_or_none()
        if item is None:
            raise ArcException(ArcException.Code.UNKNOWN_USER_TYPE, id)
        return item.representation()


def create_user_type(data: dict) -> dict:
    if _config is not None and _config.read_only:
        raise ArcException(ArcException.Code.READ_ONLY, 'Type creation is disabled')
    values = _validate_user_type(data)
    with Session(_engine) as session:
        _validate_user_type_roots(session, values)
        duplicate = session.exec(select(UserDefinedType).where(
            func.lower(UserDefinedType.name) == values['name'].lower())).first()
        if duplicate is not None:
            raise ArcException(ArcException.Code.INVALID_USER_TYPE, 'name already exists')
        item = UserDefinedType(**values)
        session.add(item)
        session.commit()
        session.refresh(item)
        return item.representation()


def update_user_type(id: str, data: dict) -> dict:
    if _config is not None and _config.read_only:
        raise ArcException(ArcException.Code.READ_ONLY, 'Type updates are disabled')
    with Session(_engine) as session:
        item = session.exec(select(UserDefinedType).where(UserDefinedType.id == id).options(
            selectinload(UserDefinedType.objects))).one_or_none()
        if item is None:
            raise ArcException(ArcException.Code.UNKNOWN_USER_TYPE, id)
        values = _validate_user_type(data, item, len(item.objects))
        _validate_user_type_roots(session, values, id)
        duplicate = session.exec(select(UserDefinedType).where(
            func.lower(UserDefinedType.name) == values['name'].lower(),
            UserDefinedType.id != id)).first()
        if duplicate is not None:
            raise ArcException(ArcException.Code.INVALID_USER_TYPE, 'name already exists')
        if values['size_limit'] < max((obj.size for obj in item.objects), default=0) and not data.get(
                'confirm_oversized', False):
            raise ArcException(ArcException.Code.CONFIRMATION_REQUIRED,
                               'known objects exceed the new limit')
        for field, value in values.items():
            setattr(item, field, value)
        for user_object in item.objects:
            if user_object.size > values['size_limit'] and (
                    UserObjectError.OVER_SIZE_LIMIT.value not in user_object.errors):
                user_object.errors = [*user_object.errors,
                                      UserObjectError.OVER_SIZE_LIMIT.value]
                session.add(user_object)
        session.add(item)
        session.commit()
        session.refresh(item)
        return item.representation()


def list_user_objects(type_id: str, search_criteria: dict | None = None) -> list[dict]:
    with Session(_engine) as session:
        if session.get(UserDefinedType, type_id) is None:
            raise ArcException(ArcException.Code.UNKNOWN_USER_TYPE, type_id)
        statement = select(UserDefinedObject).where(
            UserDefinedObject.type_id == type_id).order_by(UserDefinedObject.display_name)
        criteria = search_criteria or {}
        for tag in criteria.get('required_tags', []):
            statement = statement.where(UserDefinedObject.tags.any(Tag.tag == tag))
        for tag in criteria.get('forbidden_tags', []):
            statement = statement.where(~UserDefinedObject.tags.any(Tag.tag == tag))
        name_prefix = criteria.get('name_prefix', '')
        if name_prefix:
            escaped_prefix = (name_prefix.replace('\\', '\\\\').replace('%', '\\%')
                               .replace('_', '\\_'))
            statement = statement.where(UserDefinedObject.display_name.ilike(
                f'{escaped_prefix}%', escape='\\'))
        return [item.summary() for item in session.exec(statement).all()]


def user_object_operation_requires_lro(ids: list[str], transfer_bytes: int) -> bool:
    """Classify a planned UDP operation using type class and aggregate bytes."""
    if transfer_bytes > SMALL_OBJECT_LIMIT:
        return True
    with Session(_engine) as session:
        objects = session.exec(select(UserDefinedObject).where(
            UserDefinedObject.id.in_(set(ids))).options(
                selectinload(UserDefinedObject.type))).all() if ids else []
        if {item.id for item in objects} != set(ids):
            missing = set(ids) - {item.id for item in objects}
            raise ArcException(ArcException.Code.UNKNOWN_USER_OBJECT,
                               ', '.join(sorted(missing)))
        return any(not item.type.small for item in objects)


def collection_operation_requires_lro(plan: dict) -> bool:
    """Classify a validated collection plan using all transitive leaves."""
    members = plan.get('members', [])
    if any(member.get('object_type') == 'model' for member in members):
        return True
    user_members = [member for member in members
                    if member.get('object_type') == 'user_object']
    ids = [member['object_id'] for member in user_members]
    transfer_bytes = sum(member.get('transfer_bytes', 0) for member in user_members)
    return user_object_operation_requires_lro(ids, transfer_bytes) if ids else False


def get_user_object(id: str) -> dict:
    with Session(_engine) as session:
        item = session.get(UserDefinedObject, id)
        if item is None:
            raise ArcException(ArcException.Code.UNKNOWN_USER_OBJECT, id)
        return item.representation()


def update_user_object(id: str, data: dict) -> dict:
    if _config is not None and _config.read_only:
        raise ArcException(ArcException.Code.READ_ONLY, 'Object updates are disabled')
    with Session(_engine) as session:
        item = session.get(UserDefinedObject, id)
        if item is None:
            raise ArcException(ArcException.Code.UNKNOWN_USER_OBJECT, id)
        if item.read_only:
            raise ArcException(ArcException.Code.READ_ONLY, 'User-defined object is read-only')
        display_name = data.get('display_name')
        purpose = data.get('purpose', '')
        tags = data.get('tags', [])
        if (not isinstance(display_name, str) or not display_name.strip() or
                not isinstance(purpose, str) or not isinstance(tags, list) or
                any(not isinstance(tag, str) for tag in tags)):
            raise ArcException(ArcException.Code.INVALID_USER_TYPE,
                               'invalid user-object metadata')
        item.display_name = display_name.strip()
        item.purpose = purpose
        item.tags = resolve_tags(session, tags)
        session.add(item)
        session.commit()
        session.refresh(item)
        return item.representation()


def _user_object_snapshot(path: Path, object_class: str,
                          size_limit: int) -> tuple[dict[str, FileSnapshot], int]:
    """Capture one UDP object, raising when it is missing, unreadable, or oversized."""
    if object_class == UserObjectClass.FILE.value:
        if not path.is_file() or path.is_symlink():
            raise FileNotFoundError(path)
        paths = [path]
    else:
        if not path.is_dir() or path.is_symlink():
            raise FileNotFoundError(path)
        paths = [path, *sorted(path.rglob('*'), key=str)]
    snapshots = {}
    total = 0
    for entry in paths:
        if entry.is_symlink():
            continue
        snapshot = FileSnapshot.capture(entry)
        if not snapshot.exists:
            raise OSError(f'unreadable filesystem entry: {entry}')
        relative = '' if entry == path else entry.relative_to(path).as_posix()
        snapshots[relative] = snapshot
        if snapshot.entry_type == 'file':
            with entry.open('rb') as stream:
                stream.read(1)
            total += snapshot.size or 0
            if total > size_limit:
                raise OverflowError(f'{path} exceeds the {size_limit}-byte size limit')
    return snapshots, total


def _user_object_paths(item: UserDefinedObject) -> tuple[Path, Path]:
    return (Path(item.type.working_dir) / item.relative_path,
            Path(item.type.archive_dir) / item.relative_path)


def _add_exact_mirror_actions(plan: OperationPlan, source_root: Path,
                              destination_root: Path,
                              source: dict[str, FileSnapshot],
                              destination: dict[str, FileSnapshot]) -> int:
    """Append actions that make destination exactly match source."""
    removals = []
    creations = []
    transfer_bytes = 0
    for relative, destination_snapshot in destination.items():
        source_snapshot = source.get(relative)
        if source_snapshot is None or source_snapshot.entry_type != destination_snapshot.entry_type:
            path = destination_root if relative == '' else destination_root / relative
            action = 'rmdir' if destination_snapshot.entry_type == 'directory' else 'remove'
            removals.append((relative.count('/'), FileAction(
                action, None, str(path), None, destination_snapshot)))
    for relative, source_snapshot in source.items():
        destination_snapshot = destination.get(relative, FileSnapshot(False))
        path = destination_root if relative == '' else destination_root / relative
        source_path = source_root if relative == '' else source_root / relative
        if source_snapshot.entry_type == 'directory':
            if not destination_snapshot.exists or destination_snapshot.entry_type != 'directory':
                creations.append((relative.count('/'), FileAction(
                    'mkdir', None, str(path), None, FileSnapshot(False))))
        elif (not destination_snapshot.exists or
              destination_snapshot.entry_type != 'file' or
              source_snapshot.size != destination_snapshot.size or
              source_snapshot.modified_at_ns != destination_snapshot.modified_at_ns):
            creations.append((relative.count('/'), FileAction(
                'copy', str(source_path), str(path), source_snapshot,
                FileSnapshot(False) if destination_snapshot.entry_type == 'directory'
                else destination_snapshot)))
            transfer_bytes += source_snapshot.size or 0
    plan.actions.extend(action for _, action in sorted(removals, key=lambda value: -value[0]))
    plan.actions.extend(action for _, action in sorted(creations, key=lambda value: value[0]))
    return transfer_bytes


def _refresh_user_object_state(session: Session, item: UserDefinedObject) -> None:
    """Refresh a UDP object's sets after a completed filesystem operation."""
    working_path, archive_path = _user_object_paths(item)
    sets = []
    selected_size = 0
    selected_mtime = 0
    present = []
    for where, root, path in (('w', Path(item.type.working_dir), working_path),
                              ('a', Path(item.type.archive_dir), archive_path)):
        try:
            snapshots, total = _user_object_snapshot(
                path, item.type.object_class, item.type.size_limit)
        except FileNotFoundError:
            continue
        entries = []
        for relative, snapshot in snapshots.items():
            absolute = path if relative == '' else path / relative
            entries.append(UserObjectEntry(
                relative_path=absolute.relative_to(root).as_posix(),
                entry_type=snapshot.entry_type, size=snapshot.size or 0,
                modified_at_ns=snapshot.modified_at_ns or 0))
        modified = max((entry.modified_at_ns for entry in entries), default=0)
        sets.append(UserObjectSet(where=where, size=total,
                                  modified_at_ns=modified, entries=entries))
        present.append(where)
        if where == 'w' or not selected_size:
            selected_size, selected_mtime = total, modified
    item.sets.clear()
    session.flush()
    item.sets = sets
    item.size = selected_size
    item.modified_at_ns = selected_mtime
    item.errors = []
    item.deployment = str(DeploymentStatus.SYNCED if len(present) == 2 else
                          DeploymentStatus.WORKING if present == ['w'] else
                          DeploymentStatus.ARCHIVE)
    item.touched = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
    session.add(item)


def _user_object_operation(id: str, operation: str, simulate: bool,
                           destination: DeploymentStatus | None = None,
                           progress: Callable[[dict], None] | None = None) -> dict:
    plan = OperationPlan(operation, 'user_object', id, simulate)
    with Session(_engine) as session:
        item = session.exec(select(UserDefinedObject).where(
            UserDefinedObject.id == id).options(
                selectinload(UserDefinedObject.type),
                selectinload(UserDefinedObject.sets))).one_or_none()
        if item is None:
            plan.reject('unknown_user_object', id)
            return plan.to_dict()
        if _config.read_only or item.read_only:
            plan.reject('read_only', 'user-defined object is read-only')
            return plan.to_dict()
        working_path, archive_path = _user_object_paths(item)
        if operation == 'synchronize':
            source_path = working_path if working_path.exists() else archive_path
            destination_path = archive_path if source_path == working_path else working_path
            source_side = 'working' if source_path == working_path else 'archive'
        else:
            destination_side = ('w' if destination == DeploymentStatus.WORKING else 'a')
            destination_path = working_path if destination_side == 'w' else archive_path
            source_path = archive_path if destination_side == 'w' else working_path
            source_side = 'archive' if destination_side == 'w' else 'working'
            if not source_path.exists() and destination_path.exists():
                if not simulate:
                    _refresh_user_object_state(session, item)
                    session.commit()
                    plan.performed = True
                return plan.to_dict()
        plan.source_side = source_side
        try:
            source_snapshot, _ = _user_object_snapshot(
                source_path, item.type.object_class, item.type.size_limit)
        except OverflowError as error:
            plan.reject('over_size_limit', str(error))
            return plan.to_dict()
        except (OSError, ValueError) as error:
            plan.reject('missing_or_unreadable_source', str(error))
            return plan.to_dict()
        try:
            destination_snapshot, _ = _user_object_snapshot(
                destination_path, item.type.object_class, item.type.size_limit)
        except FileNotFoundError:
            destination_snapshot = {}
        except OverflowError as error:
            plan.reject('over_size_limit', str(error))
            return plan.to_dict()
        except (OSError, ValueError) as error:
            plan.warnings.append(OperationIssue('unreadable_destination', str(error)))
            return plan.to_dict()
        transfer_bytes = _add_exact_mirror_actions(
            plan, source_path, destination_path, source_snapshot, destination_snapshot)
        mirror_action_count = len(plan.actions)
        if operation == 'move':
            for relative, snapshot in sorted(
                    source_snapshot.items(), key=lambda value: -value[0].count('/')):
                path = source_path if relative == '' else source_path / relative
                action = 'rmdir' if snapshot.entry_type == 'directory' else 'remove'
                plan.actions.append(FileAction(action, None, str(path), None, snapshot))
        output = plan.to_dict()
        output['transfer_bytes'] = transfer_bytes
        if simulate:
            return output

        completed = 0
        copied = 0
        failures = False
        total = len(plan.actions)
        for index, action in enumerate(plan.actions):
            if operation == 'move' and index >= mirror_action_count and failures:
                break
            try:
                def report_bytes(count: int) -> None:
                    nonlocal copied
                    copied += count
                execute_file_action(action, report_bytes)
                completed += 1
            except (OSError, RuntimeError, ValueError) as error:
                failures = True
                plan.warnings.append(OperationIssue('filesystem_error', str(error)))
            if progress is not None:
                progress({'phase': 'executing', 'files_total': total,
                          'files_completed': completed, 'bytes_total': transfer_bytes,
                          'bytes_completed': copied})
        if not failures:
            _refresh_user_object_state(session, item)
            session.commit()
            plan.performed = True
        output = plan.to_dict()
        output['transfer_bytes'] = transfer_bytes
        return output


def synchronize_user_object(id: str, simulate: bool = True,
                            progress: Callable[[dict], None] | None = None) -> dict:
    return _user_object_operation(id, 'synchronize', simulate, progress=progress)


def move_user_object(id: str, destination: DeploymentStatus,
                     simulate: bool = True,
                     progress: Callable[[dict], None] | None = None) -> dict:
    try:
        destination = DeploymentStatus(destination)
    except ValueError:
        plan = OperationPlan('move', 'user_object', id, simulate)
        plan.reject('invalid_destination', str(destination))
        return plan.to_dict()
    if destination not in (DeploymentStatus.WORKING, DeploymentStatus.ARCHIVE):
        plan = OperationPlan('move', 'user_object', id, simulate)
        plan.reject('invalid_destination', str(destination))
        return plan.to_dict()
    return _user_object_operation(id, 'move', simulate, destination, progress)


def _user_type_deletion_state(session: Session, type_id: str) -> tuple:
    object_ids = tuple(session.exec(select(UserDefinedObject.id).where(
        UserDefinedObject.type_id == type_id)).all())
    links = tuple(sorted((link.user_object_id, link.collection_id) for link in session.exec(
        select(UserObjectCollectionLink).where(
            UserObjectCollectionLink.user_object_id.in_(object_ids))).all())) if object_ids else ()
    collection_ids = set(session.exec(select(Collection.id)).all())
    live = {link.collection_id for link in session.exec(select(ModelCollectionLink)).all()}
    live.update(link.collection_id for link in session.exec(select(WorkflowCollectionLink)).all())
    live.update(link.collection_id for link in session.exec(select(UserObjectCollectionLink)).all()
                if link.user_object_id not in object_ids)
    child_links = session.exec(select(CollectionCollectionLink)).all()
    changed = True
    while changed:
        changed = False
        for link in child_links:
            if link.child_id in live and link.parent_id not in live:
                live.add(link.parent_id)
                changed = True
    emptied = tuple(sorted(collection_ids - live))
    return object_ids, links, emptied


def preview_user_type_deletion(id: str) -> dict:
    with Session(_engine) as session:
        item = session.get(UserDefinedType, id)
        if item is None:
            raise ArcException(ArcException.Code.UNKNOWN_USER_TYPE, id)
        state = _user_type_deletion_state(session, id)
        collection_ids = {collection_id for _, collection_id in state[1]} | set(state[2])
        collections = session.exec(select(Collection).where(
            Collection.id.in_(collection_ids))).all() if collection_ids else []
        token = str(uuid4())
        _user_type_deletion_previews[token] = (monotonic() + 300, id, state)
        return {'confirmation_id': token, 'type': {'id': item.id, 'name': item.name},
                'objects': len(state[0]), 'collection_memberships': len(state[1]),
                'affected_collections': [collection.summary() for collection in collections],
                'collections_deleted': [collection.summary() for collection in collections
                                        if collection.id in state[2]],
                'filesystem_changes': 0}


def delete_user_type(id: str, confirmation_id: str) -> dict:
    if _config is not None and _config.read_only:
        raise ArcException(ArcException.Code.READ_ONLY, 'Type deletion is disabled')
    preview = _user_type_deletion_previews.pop(confirmation_id, None)
    if preview is None or preview[0] < monotonic() or preview[1] != id:
        raise ArcException(ArcException.Code.INVALID_CONFIRMATION, confirmation_id)
    with Session(_engine) as session:
        item = session.exec(select(UserDefinedType).where(UserDefinedType.id == id).options(
            selectinload(UserDefinedType.objects).selectinload(UserDefinedObject.collections),
            selectinload(UserDefinedType.objects).selectinload(UserDefinedObject.tags),
            selectinload(UserDefinedType.objects).selectinload(UserDefinedObject.sets),
        )).one_or_none()
        if item is None:
            raise ArcException(ArcException.Code.UNKNOWN_USER_TYPE, id)
        if _user_type_deletion_state(session, id) != preview[2]:
            raise ArcException(ArcException.Code.INVALID_CONFIRMATION,
                               'deletion impact changed')
        impact = {'id': item.id, 'name': item.name, 'objects_deleted': len(item.objects),
                  'collections_deleted': len(preview[2][2]), 'filesystem_changes': 0}
        for user_object in list(item.objects):
            user_object.collections = []
            user_object.tags = []
        session.flush()
        for collection_id in preview[2][2]:
            collection = session.get(Collection, collection_id)
            if collection is not None:
                session.delete(collection)
        session.delete(item)
        session.commit()
        return impact


#-----------------------------------------------------------------------------------
#
# Collections
#
#-----------------------------------------------------------------------------------

def list_collections(ordered) -> list[dict]:
    with Session(_engine) as session:
        statement = select(Collection).options(selectinload(Collection.parents))
        if ordered:
            statement = statement.order_by(Collection.name)

        return [collection.summary() for collection in session.exec(statement).all()]


def get_collection(id: str) -> dict:
    with Session(_engine) as session:
        collection = session.get(Collection, id)
        if collection is None:
            raise ArcException(ArcException.Code.UNKNOWN_COLLECTION,
                               f'collection {id} does not exist')
        type_map = _config.model_types if _config is not None else {}
        return collection.representation(type_map)


def create_collection(data: dict) -> dict:
    """Create a validated collection.

    For the selected child subgraphs, validation costs O(C + E + M + W) time and
    O(C + M + W) memory. Link queries are batched by graph depth, so query count
    is O(D), where D is the maximum selected collection depth.
    """
    allowed_fields = {'name', 'purpose', 'tags', 'models', 'workflows', 'user_objects',
                      'children'}
    if not isinstance(data, dict) or set(data) - allowed_fields:
        raise ArcException(ArcException.Code.INVALID_COLLECTION,
                           'payload contains unsupported fields')
    name = data.get('name')
    purpose = data.get('purpose', '')
    if not isinstance(name, str) or not name.strip():
        raise ArcException(ArcException.Code.INVALID_COLLECTION,
                           'name must be a non-empty string')
    if not isinstance(purpose, str):
        raise ArcException(ArcException.Code.INVALID_COLLECTION,
                           'purpose must be a string')

    def member_ids(field: str) -> list[str]:
        values = data.get(field, [])
        if not isinstance(values, list):
            raise ArcException(ArcException.Code.INVALID_COLLECTION,
                               f'{field} must be a list')
        result = []
        for value in values:
            member_id = value.get('id') if isinstance(value, dict) else value
            if not isinstance(member_id, str) or not member_id:
                raise ArcException(ArcException.Code.INVALID_COLLECTION,
                                   f'{field} contains an invalid id')
            result.append(member_id)
        if len(result) != len(set(result)):
            raise ArcException(ArcException.Code.DUPLICATE_COLLECTION_MEMBER,
                               f'{field} contains duplicate ids')
        return result

    model_ids = member_ids('models')
    workflow_ids = member_ids('workflows')
    user_object_ids = member_ids('user_objects')
    child_ids = member_ids('children')
    tags = data.get('tags', [])
    if (not isinstance(tags, list) or
            any(not isinstance(tag, str) for tag in tags)):
        raise ArcException(ArcException.Code.INVALID_COLLECTION,
                           'tags must be a list of strings')
    if not model_ids and not workflow_ids and not user_object_ids and not child_ids:
        raise ArcException(ArcException.Code.EMPTY_COLLECTION, name)

    with Session(_engine) as session:
        models = session.exec(select(Model).where(Model.id.in_(model_ids))).all() if model_ids else []
        workflows = (session.exec(select(Workflow).where(Workflow.id.in_(workflow_ids))).all()
                     if workflow_ids else [])
        user_objects = (session.exec(select(UserDefinedObject).where(
            UserDefinedObject.id.in_(user_object_ids))).all() if user_object_ids else [])
        children = (session.exec(select(Collection).where(Collection.id.in_(child_ids))).all()
                    if child_ids else [])
        if {model.id for model in models} != set(model_ids):
            missing = set(model_ids) - {model.id for model in models}
            raise ArcException(ArcException.Code.UNKNOWN_MODEL, ', '.join(sorted(missing)))
        if {workflow.id for workflow in workflows} != set(workflow_ids):
            missing = set(workflow_ids) - {workflow.id for workflow in workflows}
            raise ArcException(ArcException.Code.UNKNOWN_WORKFLOW, ', '.join(sorted(missing)))
        if {item.id for item in user_objects} != set(user_object_ids):
            missing = set(user_object_ids) - {item.id for item in user_objects}
            raise ArcException(ArcException.Code.UNKNOWN_USER_OBJECT, ', '.join(sorted(missing)))
        if {child.id for child in children} != set(child_ids):
            missing = set(child_ids) - {child.id for child in children}
            raise ArcException(ArcException.Code.UNKNOWN_COLLECTION, ', '.join(sorted(missing)))

        child_edges: dict[str, list[str]] = {}
        nested_models: dict[str, list[str]] = {}
        nested_workflows: dict[str, list[str]] = {}
        nested_user_objects: dict[str, list[str]] = {}
        discovered = set(child_ids)
        frontier = set(child_ids)
        while frontier:
            collection_links = session.exec(select(CollectionCollectionLink).where(
                CollectionCollectionLink.parent_id.in_(frontier))).all()
            model_links = session.exec(select(ModelCollectionLink).where(
                ModelCollectionLink.collection_id.in_(frontier))).all()
            workflow_links = session.exec(select(WorkflowCollectionLink).where(
                WorkflowCollectionLink.collection_id.in_(frontier))).all()
            user_object_links = session.exec(select(UserObjectCollectionLink).where(
                UserObjectCollectionLink.collection_id.in_(frontier))).all()
            for collection_id in frontier:
                child_edges.setdefault(collection_id, [])
                nested_models.setdefault(collection_id, [])
                nested_workflows.setdefault(collection_id, [])
                nested_user_objects.setdefault(collection_id, [])
            next_frontier = set()
            for link in collection_links:
                child_edges[link.parent_id].append(link.child_id)
                if link.child_id not in discovered:
                    discovered.add(link.child_id)
                    next_frontier.add(link.child_id)
            for link in model_links:
                nested_models[link.collection_id].append(link.model_id)
            for link in workflow_links:
                nested_workflows[link.collection_id].append(link.workflow_id)
            for link in user_object_links:
                nested_user_objects[link.collection_id].append(link.user_object_id)
            frontier = next_frontier

        visited_collections = set()
        leaf_members = {('model', model_id) for model_id in model_ids}
        leaf_members.update(('workflow', workflow_id) for workflow_id in workflow_ids)
        leaf_members.update(('user_object', object_id) for object_id in user_object_ids)

        def visit(collection_id: str, active_path: set[str]) -> None:
            if collection_id in active_path:
                raise ArcException(ArcException.Code.COLLECTION_CYCLE, collection_id)
            if collection_id in visited_collections:
                raise ArcException(ArcException.Code.DUPLICATE_COLLECTION_MEMBER,
                                   f'collection {collection_id} is reachable more than once')
            visited_collections.add(collection_id)
            path = active_path | {collection_id}
            direct_leaves = ([('model', value) for value in nested_models[collection_id]] +
                             [('workflow', value) for value in nested_workflows[collection_id]] +
                             [('user_object', value)
                              for value in nested_user_objects[collection_id]])
            if not direct_leaves and not child_edges[collection_id]:
                raise ArcException(ArcException.Code.EMPTY_COLLECTION, collection_id)
            for member in direct_leaves:
                if member in leaf_members:
                    raise ArcException(ArcException.Code.DUPLICATE_COLLECTION_MEMBER,
                                       f'{member[0]} {member[1]} is reachable more than once')
                leaf_members.add(member)
            for child_id in child_edges[collection_id]:
                visit(child_id, path)

        for child_id in child_ids:
            visit(child_id, set())

        resolved_tags = resolve_tags(session, tags)
        collection = Collection(name=name.strip(), purpose=purpose,
                                models=models, workflows=workflows, user_objects=user_objects,
                                children=children,
                                tags=resolved_tags)
        session.add(collection)
        session.commit()
        session.refresh(collection)
        return collection.summary()


def validate_collection_roots(session: Session, root_ids: set[str]) -> dict[str, dict[str, set[str]]]:
    """Validate uniqueness, non-emptiness, and acyclicity below each root."""
    child_edges: dict[str, list[str]] = {}
    model_members: dict[str, list[str]] = {}
    workflow_members: dict[str, list[str]] = {}
    user_object_members: dict[str, list[str]] = {}
    discovered = set(root_ids)
    frontier = set(root_ids)
    while frontier:
        collection_links = session.exec(select(CollectionCollectionLink).where(
            CollectionCollectionLink.parent_id.in_(frontier))).all()
        model_links = session.exec(select(ModelCollectionLink).where(
            ModelCollectionLink.collection_id.in_(frontier))).all()
        workflow_links = session.exec(select(WorkflowCollectionLink).where(
            WorkflowCollectionLink.collection_id.in_(frontier))).all()
        user_object_links = session.exec(select(UserObjectCollectionLink).where(
            UserObjectCollectionLink.collection_id.in_(frontier))).all()
        for collection_id in frontier:
            child_edges.setdefault(collection_id, [])
            model_members.setdefault(collection_id, [])
            workflow_members.setdefault(collection_id, [])
            user_object_members.setdefault(collection_id, [])
        next_frontier = set()
        for link in collection_links:
            child_edges[link.parent_id].append(link.child_id)
            if link.child_id not in discovered:
                discovered.add(link.child_id)
                next_frontier.add(link.child_id)
        for link in model_links:
            model_members[link.collection_id].append(link.model_id)
        for link in workflow_links:
            workflow_members[link.collection_id].append(link.workflow_id)
        for link in user_object_links:
            user_object_members[link.collection_id].append(link.user_object_id)
        frontier = next_frontier

    result = {}
    for root_id in root_ids:
        visited = set()
        leaves = set()

        def visit(collection_id: str, active_path: set[str]) -> None:
            if collection_id in active_path:
                raise ArcException(ArcException.Code.COLLECTION_CYCLE, collection_id)
            if collection_id in visited:
                raise ArcException(ArcException.Code.DUPLICATE_COLLECTION_MEMBER,
                                   f'collection {collection_id} is reachable more than once')
            visited.add(collection_id)
            direct_leaves = ([('model', value) for value in model_members[collection_id]] +
                             [('workflow', value) for value in workflow_members[collection_id]] +
                             [('user_object', value)
                              for value in user_object_members[collection_id]])
            if not direct_leaves and not child_edges[collection_id]:
                raise ArcException(ArcException.Code.EMPTY_COLLECTION, collection_id)
            for member in direct_leaves:
                if member in leaves:
                    raise ArcException(ArcException.Code.DUPLICATE_COLLECTION_MEMBER,
                                       f'{member[0]} {member[1]} is reachable more than once')
                leaves.add(member)
            path = active_path | {collection_id}
            for child_id in child_edges[collection_id]:
                visit(child_id, path)

        visit(root_id, set())
        result[root_id] = {
            'models': {value for member_type, value in leaves if member_type == 'model'},
            'workflows': {value for member_type, value in leaves if member_type == 'workflow'},
            'user_objects': {value for member_type, value in leaves
                             if member_type == 'user_object'},
        }
    return result


def update_collection(id: str, data: dict) -> dict:
    """Replace a collection while preserving its ID.

    Validation is O(A + E + sum(T_r)) time, where A is the ancestor graph,
    E its edges, and T_r is the reachable tree size for each affected root.
    Memory use is linear in the union of those reachable subgraphs.
    """
    allowed_fields = {'id', 'name', 'purpose', 'tags', 'models', 'workflows',
                      'user_objects', 'children'}
    if not isinstance(data, dict) or set(data) - allowed_fields:
        raise ArcException(ArcException.Code.INVALID_COLLECTION,
                           'payload contains unsupported fields')
    if 'id' in data and data['id'] != id:
        raise ArcException(ArcException.Code.INVALID_COLLECTION,
                           'collection id cannot change')
    name = data.get('name')
    purpose = data.get('purpose', '')
    if not isinstance(name, str) or not name.strip() or not isinstance(purpose, str):
        raise ArcException(ArcException.Code.INVALID_COLLECTION,
                           'name and purpose are invalid')

    def ids_for(field: str) -> list[str]:
        values = data.get(field, [])
        if not isinstance(values, list):
            raise ArcException(ArcException.Code.INVALID_COLLECTION, f'{field} must be a list')
        result = [value.get('id') if isinstance(value, dict) else value for value in values]
        if any(not isinstance(value, str) or not value for value in result):
            raise ArcException(ArcException.Code.INVALID_COLLECTION,
                               f'{field} contains an invalid id')
        if len(result) != len(set(result)):
            raise ArcException(ArcException.Code.DUPLICATE_COLLECTION_MEMBER,
                               f'{field} contains duplicate ids')
        return result

    model_ids = ids_for('models')
    workflow_ids = ids_for('workflows')
    user_object_ids = ids_for('user_objects')
    child_ids = ids_for('children')
    tags = data.get('tags', [])
    if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
        raise ArcException(ArcException.Code.INVALID_COLLECTION,
                           'tags must be a list of strings')
    if not model_ids and not workflow_ids and not user_object_ids and not child_ids:
        raise ArcException(ArcException.Code.EMPTY_COLLECTION, id)

    with Session(_engine) as session:
        collection = session.get(Collection, id)
        if collection is None:
            raise ArcException(ArcException.Code.UNKNOWN_COLLECTION, id)
        models = session.exec(select(Model).where(Model.id.in_(model_ids))).all() if model_ids else []
        workflows = (session.exec(select(Workflow).where(Workflow.id.in_(workflow_ids))).all()
                     if workflow_ids else [])
        user_objects = (session.exec(select(UserDefinedObject).where(
            UserDefinedObject.id.in_(user_object_ids))).all() if user_object_ids else [])
        children = (session.exec(select(Collection).where(Collection.id.in_(child_ids))).all()
                    if child_ids else [])
        if {item.id for item in models} != set(model_ids):
            raise ArcException(ArcException.Code.UNKNOWN_MODEL,
                               ', '.join(sorted(set(model_ids) - {item.id for item in models})))
        if {item.id for item in workflows} != set(workflow_ids):
            raise ArcException(ArcException.Code.UNKNOWN_WORKFLOW,
                               ', '.join(sorted(set(workflow_ids) - {item.id for item in workflows})))
        if {item.id for item in user_objects} != set(user_object_ids):
            raise ArcException(ArcException.Code.UNKNOWN_USER_OBJECT,
                               ', '.join(sorted(set(user_object_ids) -
                                                {item.id for item in user_objects})))
        if {item.id for item in children} != set(child_ids):
            raise ArcException(ArcException.Code.UNKNOWN_COLLECTION,
                               ', '.join(sorted(set(child_ids) - {item.id for item in children})))

        collection.name = name.strip()
        collection.purpose = purpose
        collection.models = models
        collection.workflows = workflows
        collection.user_objects = user_objects
        collection.children = children
        collection.tags = resolve_tags(session, tags)
        session.add(collection)
        session.flush()

        ancestors = {id}
        frontier = {id}
        parent_edges = []
        while frontier:
            links = session.exec(select(CollectionCollectionLink).where(
                CollectionCollectionLink.child_id.in_(frontier))).all()
            parent_edges.extend(links)
            next_frontier = {link.parent_id for link in links} - ancestors
            ancestors.update(next_frontier)
            frontier = next_frontier
        parent_ids = {link.child_id for link in parent_edges}
        roots = ancestors - parent_ids
        if not roots:
            roots = {id}
        validate_collection_roots(session, roots)
        session.commit()
        session.refresh(collection)
        return collection.summary()


def update_collection_models(id: str, model_ids: list[str], add: bool) -> dict:
    """Add or remove direct model memberships in one validated update."""
    current = get_collection(id)
    selected = set(model_ids)
    existing = [model['id'] for model in current['models']]
    models = (existing + [model_id for model_id in model_ids if model_id not in existing]
              if add else [model_id for model_id in existing if model_id not in selected])
    return update_collection(id, {
        'id': id,
        'name': current['name'],
        'purpose': current['purpose'],
        'tags': current['tags'],
        'models': models,
        'workflows': [workflow['id'] for workflow in current['workflows']],
        'user_objects': [item['id'] for item in current['user_objects']],
        'children': [child['id'] for child in current['children']],
    })


def update_collection_workflows(id: str, workflow_ids: list[str], add: bool) -> dict:
    """Add or remove direct workflow memberships in one validated update."""
    current = get_collection(id)
    selected = set(workflow_ids)
    existing = [workflow['id'] for workflow in current['workflows']]
    workflows = (existing + [item for item in workflow_ids if item not in existing]
                 if add else [item for item in existing if item not in selected])
    return update_collection(id, {
        'id': id, 'name': current['name'], 'purpose': current['purpose'],
        'tags': current['tags'],
        'models': [model['id'] for model in current['models']],
        'workflows': workflows,
        'user_objects': [item['id'] for item in current['user_objects']],
        'children': [child['id'] for child in current['children']],
    })


def update_collection_user_objects(id: str, user_object_ids: list[str], add: bool) -> dict:
    """Add or remove direct user-object memberships in one validated update."""
    current = get_collection(id)
    selected = set(user_object_ids)
    existing = [item['id'] for item in current['user_objects']]
    user_objects = (existing + [item for item in user_object_ids if item not in existing]
                    if add else [item for item in existing if item not in selected])
    return update_collection(id, {
        'id': id, 'name': current['name'], 'purpose': current['purpose'],
        'tags': current['tags'],
        'models': [model['id'] for model in current['models']],
        'workflows': [workflow['id'] for workflow in current['workflows']],
        'user_objects': user_objects,
        'children': [child['id'] for child in current['children']],
    })


def delete_collection(id: str) -> dict:
    """Delete one collection without deleting any of its members.

    Validation is O(P + L) time and O(P) memory, where P is the number of
    direct parents and L is the number of their direct membership links.
    """
    with Session(_engine) as session:
        collection = session.get(Collection, id)
        if collection is None:
            raise ArcException(ArcException.Code.UNKNOWN_COLLECTION, id)
        parent_links = session.exec(select(CollectionCollectionLink).where(
            CollectionCollectionLink.child_id == id)).all()
        parent_ids = {link.parent_id for link in parent_links}
        if parent_ids:
            parent_collection_links = session.exec(select(CollectionCollectionLink).where(
                CollectionCollectionLink.parent_id.in_(parent_ids))).all()
            parent_model_links = session.exec(select(ModelCollectionLink).where(
                ModelCollectionLink.collection_id.in_(parent_ids))).all()
            parent_workflow_links = session.exec(select(WorkflowCollectionLink).where(
                WorkflowCollectionLink.collection_id.in_(parent_ids))).all()
            parent_user_object_links = session.exec(select(UserObjectCollectionLink).where(
                UserObjectCollectionLink.collection_id.in_(parent_ids))).all()
            nonempty_parents = {
                link.parent_id for link in parent_collection_links if link.child_id != id
            }
            nonempty_parents.update(link.collection_id for link in parent_model_links)
            nonempty_parents.update(link.collection_id for link in parent_workflow_links)
            nonempty_parents.update(link.collection_id for link in parent_user_object_links)
            emptied_parents = parent_ids - nonempty_parents
            if emptied_parents:
                raise ArcException(
                    ArcException.Code.EMPTY_COLLECTION,
                    f'deleting {id} would empty parent collections: '
                    f'{", ".join(sorted(emptied_parents))}',
                )
        summary = collection.summary()
        session.delete(collection)
        session.commit()
        return summary


def collection_operation(id: str, operation: str, simulate: bool = True,
                         destination: DeploymentStatus | None = None) -> dict:
    plan = OperationPlan(operation=operation, object_type='collection',
                         object_id=id, simulate=simulate)
    with Session(_engine) as session:
        if session.get(Collection, id) is None:
            plan.reject('unknown_collection', f'collection {id} does not exist')
            return plan.to_dict()
        try:
            leaves = validate_collection_roots(session, {id})[id]
        except ArcException as error:
            plan.reject(str(error.code), error.message)
            return plan.to_dict()

    members = ([('model', member_id) for member_id in sorted(leaves['models'])] +
               [('workflow', member_id) for member_id in sorted(leaves['workflows'])] +
               [('user_object', member_id) for member_id in sorted(leaves['user_objects'])])

    def run_member(member_type: str, member_id: str, member_simulate: bool) -> dict:
        if operation == 'synchronize':
            function = (synchronize_model if member_type == 'model' else
                        synchronize_workflow if member_type == 'workflow' else
                        synchronize_user_object)
            return function(member_id, member_simulate)
        function = (move_model if member_type == 'model' else
                    move_workflow if member_type == 'workflow' else
                    move_user_object)
        return function(member_id, destination, member_simulate)

    validation_results = [run_member(member_type, member_id, True)
                          for member_type, member_id in members]
    rejected = [result for result in validation_results if not result['allowed']]
    if rejected:
        plan.allowed = False
        for result in rejected:
            plan.errors.append(OperationIssue(
                'member_validation_failed',
                f'{result["object_type"]} {result["object_id"]}: '
                f'{result["errors"]}',
            ))
        output = plan.to_dict()
        output['members'] = validation_results
        output['actions'] = [action for result in validation_results
                             for action in result['actions']]
        return output
    if simulate:
        output = plan.to_dict()
        output['members'] = validation_results
        output['actions'] = [action for result in validation_results
                             for action in result['actions']]
        return output

    execution_results = []
    for member_type, member_id in members:
        result = run_member(member_type, member_id, False)
        execution_results.append(result)
        if not result['allowed'] or not result['performed']:
            plan.allowed = False
            plan.errors.append(OperationIssue(
                'member_execution_failed',
                f'{member_type} {member_id}: {result["errors"]}',
            ))
            break
    plan.performed = (len(execution_results) == len(members) and
                      all(result['performed'] for result in execution_results))
    if not plan.performed and execution_results:
        plan.warnings.append(OperationIssue(
            'partial_execution',
            f'{len(execution_results)} of {len(members)} members were attempted',
        ))
    output = plan.to_dict()
    output['members'] = execution_results
    output['actions'] = [action for result in execution_results
                         for action in result['actions']]
    return output


def synchronize_collection(id: str, simulate: bool = True) -> dict:
    """Synchronize every transitive leaf in O(C + E + M + W + F) time."""
    return collection_operation(id, 'synchronize', simulate)


def move_collection(id: str, destination: DeploymentStatus,
                    simulate: bool = True) -> dict:
    """Move every transitive leaf in O(C + E + M + W + F) time."""
    try:
        destination = DeploymentStatus(destination)
    except ValueError:
        plan = OperationPlan('move', 'collection', id, simulate)
        plan.reject('invalid_destination', str(destination))
        return plan.to_dict()
    if destination not in (DeploymentStatus.WORKING, DeploymentStatus.ARCHIVE):
        plan = OperationPlan('move', 'collection', id, simulate)
        plan.reject('invalid_destination', str(destination))
        return plan.to_dict()
    return collection_operation(id, 'move', simulate, destination)

#-----------------------------------------------------------------------------------
#
# Tags
#
#-----------------------------------------------------------------------------------

def list_tags(target_types: Set[PrimaryObjectType] | None, offset: int, limit: int) -> list:
    with Session(_engine) as session:
        if target_types is not None and len(target_types) > 0:
            cond = []
            if PrimaryObjectType.MODEL in target_types:
                cond.append(Tag.models.any())
            if PrimaryObjectType.WORKFLOW in target_types:
                cond.append(Tag.workflows.any())
            if PrimaryObjectType.COLLECTION in target_types:
                cond.append(Tag.collections.any())
            if limit > 0:
                statement = select(Tag).offset(offset).limit(limit).where(or_(*cond))
            else:
                statement = select(Tag).offset(offset).where(or_(*cond))
        else:
            statement = select(Tag).offset(offset).limit(limit)
        found = session.exec(statement).all()
        return [t.tag for t in found]

def resolve_tags(session: Session, tag_names: list[str]) -> list[Tag]:
    cleaned = list({t.strip() for t in tag_names if len(t.strip()) > 0})
    if len(cleaned) == 0:
        return []
    known = {t.tag: t for t in session.exec(select(Tag).where(Tag.tag.in_(cleaned))).all()}

    for tag in cleaned:
        if not tag in known:
            new_tag = Tag(tag=tag)
            session.add(new_tag)
            known[tag] = new_tag

    return [t for t in known.values()]
