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

from sqlmodel import Session, create_engine, select, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.engine.base import Engine
from sqlalchemy import func
from sqlalchemy.orm import selectinload
from backend.repository.tables import (Model, Workflow, Collection, Component, ComponentSet,
                                       ComponentType, Tag, PrimaryObjectType, DeploymentStatus,
                                       ModelError, CollectionCollectionLink, ModelCollectionLink,
                                       WorkflowCollectionLink)
from backend.exception import ArcException
from backend.config import Configuration, get_config
from backend.files.scanner import get_scanner, create_scanner
from backend.repository.migrations import update_database_schema
import backend.files.model_files as model_files
import backend.files.workflow_files as workflow_files
from backend.files.operations import (FileAction, FileSnapshot, OperationIssue, OperationPlan,
                                      action_transfer_size, atomic_copy, execute_file_action)

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


def repository_counts() -> dict[str, int]:
    """Return counts of the logical objects displayed by the application."""
    if not _repo_started:
        return {'models': 0, 'workflows': 0, 'collections': 0}
    with Session(_engine) as session:
        return {
            'models': session.exec(select(func.count()).select_from(Model)).one(),
            'workflows': session.exec(select(func.count()).select_from(Workflow)).one(),
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
    allowed_fields = {'name', 'purpose', 'tags', 'models', 'workflows', 'children'}
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
    child_ids = member_ids('children')
    tags = data.get('tags', [])
    if (not isinstance(tags, list) or
            any(not isinstance(tag, str) for tag in tags)):
        raise ArcException(ArcException.Code.INVALID_COLLECTION,
                           'tags must be a list of strings')
    if not model_ids and not workflow_ids and not child_ids:
        raise ArcException(ArcException.Code.EMPTY_COLLECTION, name)

    with Session(_engine) as session:
        models = session.exec(select(Model).where(Model.id.in_(model_ids))).all() if model_ids else []
        workflows = (session.exec(select(Workflow).where(Workflow.id.in_(workflow_ids))).all()
                     if workflow_ids else [])
        children = (session.exec(select(Collection).where(Collection.id.in_(child_ids))).all()
                    if child_ids else [])
        if {model.id for model in models} != set(model_ids):
            missing = set(model_ids) - {model.id for model in models}
            raise ArcException(ArcException.Code.UNKNOWN_MODEL, ', '.join(sorted(missing)))
        if {workflow.id for workflow in workflows} != set(workflow_ids):
            missing = set(workflow_ids) - {workflow.id for workflow in workflows}
            raise ArcException(ArcException.Code.UNKNOWN_WORKFLOW, ', '.join(sorted(missing)))
        if {child.id for child in children} != set(child_ids):
            missing = set(child_ids) - {child.id for child in children}
            raise ArcException(ArcException.Code.UNKNOWN_COLLECTION, ', '.join(sorted(missing)))

        child_edges: dict[str, list[str]] = {}
        nested_models: dict[str, list[str]] = {}
        nested_workflows: dict[str, list[str]] = {}
        discovered = set(child_ids)
        frontier = set(child_ids)
        while frontier:
            collection_links = session.exec(select(CollectionCollectionLink).where(
                CollectionCollectionLink.parent_id.in_(frontier))).all()
            model_links = session.exec(select(ModelCollectionLink).where(
                ModelCollectionLink.collection_id.in_(frontier))).all()
            workflow_links = session.exec(select(WorkflowCollectionLink).where(
                WorkflowCollectionLink.collection_id.in_(frontier))).all()
            for collection_id in frontier:
                child_edges.setdefault(collection_id, [])
                nested_models.setdefault(collection_id, [])
                nested_workflows.setdefault(collection_id, [])
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
            frontier = next_frontier

        visited_collections = set()
        leaf_members = {('model', model_id) for model_id in model_ids}
        leaf_members.update(('workflow', workflow_id) for workflow_id in workflow_ids)

        def visit(collection_id: str, active_path: set[str]) -> None:
            if collection_id in active_path:
                raise ArcException(ArcException.Code.COLLECTION_CYCLE, collection_id)
            if collection_id in visited_collections:
                raise ArcException(ArcException.Code.DUPLICATE_COLLECTION_MEMBER,
                                   f'collection {collection_id} is reachable more than once')
            visited_collections.add(collection_id)
            path = active_path | {collection_id}
            direct_leaves = ([('model', value) for value in nested_models[collection_id]] +
                             [('workflow', value) for value in nested_workflows[collection_id]])
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
                                models=models, workflows=workflows, children=children,
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
    discovered = set(root_ids)
    frontier = set(root_ids)
    while frontier:
        collection_links = session.exec(select(CollectionCollectionLink).where(
            CollectionCollectionLink.parent_id.in_(frontier))).all()
        model_links = session.exec(select(ModelCollectionLink).where(
            ModelCollectionLink.collection_id.in_(frontier))).all()
        workflow_links = session.exec(select(WorkflowCollectionLink).where(
            WorkflowCollectionLink.collection_id.in_(frontier))).all()
        for collection_id in frontier:
            child_edges.setdefault(collection_id, [])
            model_members.setdefault(collection_id, [])
            workflow_members.setdefault(collection_id, [])
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
                             [('workflow', value) for value in workflow_members[collection_id]])
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
        }
    return result


def update_collection(id: str, data: dict) -> dict:
    """Replace a collection while preserving its ID.

    Validation is O(A + E + sum(T_r)) time, where A is the ancestor graph,
    E its edges, and T_r is the reachable tree size for each affected root.
    Memory use is linear in the union of those reachable subgraphs.
    """
    allowed_fields = {'id', 'name', 'purpose', 'tags', 'models', 'workflows', 'children'}
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
    child_ids = ids_for('children')
    tags = data.get('tags', [])
    if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
        raise ArcException(ArcException.Code.INVALID_COLLECTION,
                           'tags must be a list of strings')
    if not model_ids and not workflow_ids and not child_ids:
        raise ArcException(ArcException.Code.EMPTY_COLLECTION, id)

    with Session(_engine) as session:
        collection = session.get(Collection, id)
        if collection is None:
            raise ArcException(ArcException.Code.UNKNOWN_COLLECTION, id)
        models = session.exec(select(Model).where(Model.id.in_(model_ids))).all() if model_ids else []
        workflows = (session.exec(select(Workflow).where(Workflow.id.in_(workflow_ids))).all()
                     if workflow_ids else [])
        children = (session.exec(select(Collection).where(Collection.id.in_(child_ids))).all()
                    if child_ids else [])
        if {item.id for item in models} != set(model_ids):
            raise ArcException(ArcException.Code.UNKNOWN_MODEL,
                               ', '.join(sorted(set(model_ids) - {item.id for item in models})))
        if {item.id for item in workflows} != set(workflow_ids):
            raise ArcException(ArcException.Code.UNKNOWN_WORKFLOW,
                               ', '.join(sorted(set(workflow_ids) - {item.id for item in workflows})))
        if {item.id for item in children} != set(child_ids):
            raise ArcException(ArcException.Code.UNKNOWN_COLLECTION,
                               ', '.join(sorted(set(child_ids) - {item.id for item in children})))

        collection.name = name.strip()
        collection.purpose = purpose
        collection.models = models
        collection.workflows = workflows
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
            nonempty_parents = {
                link.parent_id for link in parent_collection_links if link.child_id != id
            }
            nonempty_parents.update(link.collection_id for link in parent_model_links)
            nonempty_parents.update(link.collection_id for link in parent_workflow_links)
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
               [('workflow', member_id) for member_id in sorted(leaves['workflows'])])

    def run_member(member_type: str, member_id: str, member_simulate: bool) -> dict:
        if operation == 'synchronize':
            function = synchronize_model if member_type == 'model' else synchronize_workflow
            return function(member_id, member_simulate)
        function = move_model if member_type == 'model' else move_workflow
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
