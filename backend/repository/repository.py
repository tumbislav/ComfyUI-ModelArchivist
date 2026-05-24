# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: repository.py
# purpose: Database operations
# ---------------------------------------------------------------------------

from typing import Set
from threading import Lock
import logging

from sqlmodel import SQLModel, Session, create_engine, select, or_
from sqlalchemy.engine.base import Engine
from .tables import Model, Workflow, Collection, Component, Tag
from backend.exception import ArcException
from backend.config import Configuration, get_config
from backend.files.scanner import get_scanner, create_scanner
from enum import StrEnum


class PrimaryObjectType(StrEnum):
    MODEL = 'md'
    WORKFLOW = 'wf'
    COLLECTION = 'cl'

_logger: logging.Logger | None = None
_engine: Engine | None = None
_config: Configuration | None = None

lock = Lock()

_first_run: bool = False
_repo_started: bool = False

def start_repo():
    global _engine, _logger, _config, _first_run, _repo_started
    if _repo_started:
        return
    _config = get_config()
    _logger = logging.getLogger('archivist.database')
    _first_run = not _config.db_file.is_file()
    db_name = f'{_config.dbms_prefix}{_config.db_file}'
    _engine = create_engine(db_name, echo=False)
    sql_logger = logging.getLogger('sqlalchemy.engine')
    sql_logger.addHandler(logging.FileHandler(_config.log_file))
    sql_logger.setLevel(_config.sql_log_level)
    if _first_run:
        _logger.info(f'First run, creating the database in {db_name}')
        SQLModel.metadata.create_all(_engine)
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
                'ready': False}
    status_dict = {'started': True,
                   'first_run': _first_run}
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
        known_models = session.exec(select(Model).where(Model.id == model.id)).all()
        if len(known_models) == 0:
            _logger.debug(f'adding model {model.name}')
            model.tags = resolve_tags(session, tag_names)
            session.add(model)
            session.commit()
        else:
            _logger.debug(f'updating model {model.name}')
            if len(known_models) > 1:
                all_names = ', '.join(m.name for m in known_models)
                raise ArcException(ArcException.Code.DUPLICATE_MODEL,
                                         f'{model.id}, {all_names}')
            old_model = known_models[0]
            if old_model.scan_timestamp == model.scan_timestamp:
                _logger.error(f'model {model.name} / {model.id} already seen in this scan')
                raise ArcException(ArcException.Code.DUPLICATE_MODEL,
                                         f'{model.name} {model.id}, {old_model.scan_timestamp}')
            # see which components no longer exist and remove them
            known_components = {(c.file_name, c.component_type, c.is_archive): c.id for c in old_model.components}
            # update the old model
            old_model.update_from(model)
            old_model.tags = resolve_tags(session, tag_names)
            session.add(old_model)
            session.commit()
            # add new components
            for c in model.components:
                if (c.file_name, c.component_type, c.is_archive) in known_components:
                    del known_components[(c.file_name, c.component_type, c.is_archive)]
                else:
                    c.model = old_model
                    session.add(c)
            # remove components that no longer exist
            for c_id in known_components.values():
                c = session.exec(select(Component).where(Component.id == c_id)).one()
                session.delete(c)
            session.commit()

def save_scanned_workflow(workflow: Workflow, tag_names: list[str]) -> None:
    """
    Save a full workflow record.
    """
    with Session(_engine) as session:
        known_workflows = session.exec(select(Workflow).where(Workflow.id == workflow.id)).all()
        if len(known_workflows) == 0:
            _logger.debug(f'adding workflow {workflow.name}')
            workflow.tags = resolve_tags(session, tag_names)
            session.add(workflow)
            session.commit()
        else:
            _logger.debug(f'updating workflow {workflow.name}')
            if len(known_workflows) > 1:
                all_names = ', '.join(w.name for w in known_workflows)
                raise ArcException(ArcException.Code.DUPLICATE_MODEL,
                                         f'{workflow.id}, {all_names}')
            old_workflow = known_workflows[0]
            if old_workflow.scan_timestamp == workflow.scan_timestamp:
                raise ArcException(ArcException.Code.DUPLICATE_MODEL,
                                         f'{workflow.name} {workflow.id}, {old_workflow.scan_timestamp}')
            # see which components no longer exist and remove them
            known_components = {(c.file_name, c.component_type, c.is_archive): c.id for c in old_workflow.components}
            # update the old workflow
            old_workflow.update_from(workflow)
            old_workflow.tags = resolve_tags(session, tag_names)
            session.add(old_workflow)
            session.commit()
            # add new components
            for c in workflow.components:
                if (c.file_name, c.component_type, c.is_archive) in known_components:
                    del known_components[(c.file_name, c.component_type, c.is_archive)]
                else:
                    c.workflow = old_workflow
                    session.add(c)
            # remove components that no longer exist
            for c_id in known_components.values():
                c = session.exec(select(Component).where(Component.id == c_id)).one()
                session.delete(c)
            session.commit()

def scan_cleanup(scan_timestamp: str):
    with Session(_engine) as session:
        models = session.exec(select(Model).where(Model.scan_timestamp != scan_timestamp))
        for model in models:
            _logger.debug(f'deleting model {model.name}')
            session.delete(model)
        session.commit()

#-----------------------------------------------------------------------------------
#
# Models
#
#-----------------------------------------------------------------------------------

def update_model(changes: dict) -> dict:
    """
    Update an existing model. The items that may change are the name, the tags and collection membership.
    """
    with Session(_engine) as session:
        known_models = session.exec(select(Model).where(Model.id == changes['id'])).all()
        if len(known_models) != 1:
            msg = f'unknown model {changes["id"]} ({changes["name"]})'
            _logger.error(msg)
            raise ArcException(ArcException.Code.UNKNOWN_MODEL, msg)
        _logger.debug(f'updating model {changes["id"]}')
        old_model = known_models[0]
        old_model.name = changes['name']
        old_model.tags = resolve_tags(session, changes['tags'])
        return {}
#        old_model.collections =

def list_models(ordered, search_criteria: dict | None = None) -> list[dict]:
    with Session(_engine) as session:
        if ordered:
            statement = select(Model).order_by(Model.type, Model.name)
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
        return model.representation(_config.model_types)

#-----------------------------------------------------------------------------------
#
# Workflows
#
#-----------------------------------------------------------------------------------

def list_workflows(ordered: bool, search_criteria: dict | None = None) -> list[dict]:
    with Session(_engine) as session:
        if ordered:
            statement = select(Workflow).order_by(Workflow.purpose, Workflow.name)
        else:
            statement = select(Workflow).order_by(Workflow.name)
        return [workflow.summary() for workflow in session.exec(statement).all()]


def get_workflow(id: str) -> dict:
    with Session(_engine) as session:
        workflow: Workflow | None = session.get(Workflow, id)
        if workflow is None:
            msg = f'workflow with id {id} does not exist'
            _logger.info(msg)
            raise ArcException(ArcException.Code.UNKNOWN_WORKFLOW, msg)
        return workflow.representation()

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
                cond.append(Tag.children.any())
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


