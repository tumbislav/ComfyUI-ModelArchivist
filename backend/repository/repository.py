# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: repository.py
# purpose: Database operations
# ---------------------------------------------------------------------------

from typing import Set
from threading import Lock
import logging
import datetime
import os
from pathlib import Path

from sqlmodel import Session, create_engine, select, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.engine.base import Engine
from backend.repository.tables import (Model, Workflow, Collection, Component, ComponentSet,
                                       ComponentType, Tag, PrimaryObjectType, DeploymentStatus,
                                       ModelError)
from backend.exception import ArcException
from backend.config import Configuration, get_config
from backend.files.scanner import get_scanner, create_scanner
from backend.repository.migrations import update_database_schema
import backend.files.model_files as model_files
from backend.files.operations import FileAction, FileSnapshot, OperationPlan, atomic_copy

_logger: logging.Logger | None = None
_engine: Engine | None = None
_config: Configuration | None = None

lock = Lock()

_first_run: bool = False
_repo_started: bool = False

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

    _config = config
    _first_run = first_run
    _engine = engine
    sql_logger = logging.getLogger('sqlalchemy.engine')
    sql_logger.addHandler(logging.FileHandler(_config.log_file))
    sql_logger.setLevel(_config.sql_log_level)
    if _first_run and not _config.read_only:
        _logger.info(f'First run, creating the database in {db_name}')
        sc = create_scanner()
        if sc is None:
            msg = 'Cannot create a scanner, aborting'
            _logger.critical(msg)
            raise RuntimeError(msg)
        sc.start(_config.options.always_recalc_hashes)
    _repo_started = True


def repo_status():
    if not _repo_started:
        return {'started': False,
                'ready': False,
                'read_only': True if _config is None else _config.read_only}
    status_dict = {'started': True,
                   'first_run': _first_run,
                   'read_only': _config.read_only}
    sc = get_scanner()
    if sc is None:
        status_dict['ready'] = True
    else:
        scan_progress = sc.progress()
        status_dict['scanning'] = scan_progress['started'] and not scan_progress['finished']
        status_dict['ready'] = not status_dict['scanning']
    return status_dict

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
                old_model.component_sets.extend(model.component_sets)
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
        return model.representation(_config.model_types)

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
        return [model.summary(_config.model_types) for model in session.exec(statement).all()]

def get_model(id: str) -> dict:
    with Session(_engine) as session:
        model: Model | None = session.get(Model, id)
        if model is None:
            msg = f'model with hash {id} does not exist'
            _logger.info(msg)
            raise ArcException(ArcException.Code.UNKNOWN_MODEL, msg)
        rep = model.representation(_config.model_types)
        return model.representation(_config.model_types)

#-----------------------------------------------------------------------------------
#
# Workflows
#
#-----------------------------------------------------------------------------------

def list_workflows(ordered: bool, search_criteria: dict | None = None) -> list[dict]:
    with Session(_engine) as session:
        if ordered:
            statement = select(Workflow).order_by(Workflow.purpose, Workflow.internal_name)
        else:
            statement = select(Workflow).order_by(Workflow.internal_name)
        return [workflow.summary() for workflow in session.exec(statement).all()]


def get_workflow(id: str) -> dict:
    with Session(_engine) as session:
        workflow: Workflow | None = session.get(Workflow, id)
        if workflow is None:
            msg = f'workflow with id {id} does not exist'
            _logger.info(msg)
            raise ArcException(ArcException.Code.UNKNOWN_WORKFLOW, msg)
        return workflow.representation()


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

#-----------------------------------------------------------------------------------
#
# Collections
#
#-----------------------------------------------------------------------------------

def list_collections(ordered) -> list[dict]:
    with Session(_engine) as session:
        if ordered:
            statement = select(Collection).order_by(Collection.type, Collection.name)
        else:
            statement = select(Collection).order_by(Collection.type)

        return [collection.summary() for collection in session.exec(statement).all()]

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
