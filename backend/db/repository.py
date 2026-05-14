# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: repository.py
# purpose: Database operations
# ---------------------------------------------------------------------------
from sqlalchemy.util.preloaded import sql_dml
from sqlmodel import SQLModel, Session, create_engine, select, or_
from sqlalchemy.engine.base import Engine
from typing import Iterable, Set
from threading import Lock
from .tables import Model, Workflow, Collection, Component, Tag
from ..model.object_types import ArchivistError, ArchivistException, Taggable
from ..config import get_config

import logging

_logger: logging.Logger | None = None
_engine: Engine | None = None

lock = Lock()

def start_repo() -> bool:
    global _engine, _logger
    config = get_config()
    _logger = logging.getLogger('archivist.database')
    is_first_run = not config.db_file.is_file()
    db_name = f'{config.dbms_prefix}{config.db_file}'
    _engine = create_engine(db_name, echo=False)
    sql_logger = logging.getLogger('sqlalchemy.engine')
    sql_logger.addHandler(logging.FileHandler(config.log_file))
    sql_logger.setLevel(config.sql_log_level)
    if is_first_run:
        _logger.info(f'First run, creating the database in {db_name}')
        SQLModel.metadata.create_all(_engine)
    return is_first_run

def save_model(model: Model, tag_names: list[str]) -> None:
    """
    Save a full model record. We have the following possibilities:
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
                raise ArchivistException(ArchivistError.DUPLICATE_MODEL,
                                         f'{model.id}, {all_names}')
            old_model = known_models[0]
            if old_model.last_scan_id == model.last_scan_id:
                _logger.error(f'model {model.name} / {model.id} already seen in this scan')
                raise ArchivistException(ArchivistError.DUPLICATE_MODEL,
                                         f'{model.name} {model.id}, {old_model.last_scan_id}')
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

def save_workflow(workflow: Workflow, tag_names: list[str]) -> None:
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
                raise ArchivistException(ArchivistError.DUPLICATE_MODEL,
                                         f'{workflow.id}, {all_names}')
            old_workflow = known_workflows[0]
            if old_workflow.last_scan_id == workflow.last_scan_id:
                raise ArchivistException(ArchivistError.DUPLICATE_MODEL,
                                         f'{workflow.name} {workflow.id}, {old_workflow.last_scan_id}')
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

def cleanup(scan_id: str):
    with Session(_engine) as session:
        models = session.exec(select(Model).where(Model.last_scan_id != scan_id))
        for model in models:
            _logger.debug(f'deleting model {model.name}')
            session.delete(model)
        session.commit()

def list_models(ordered) -> Iterable:
    with Session(_engine) as session:
        if ordered:
            statement = select(Model).order_by(Model.type, Model.name)
        else:
            statement = select(Model).order_by(Model.type)
        for model in session.exec(statement).all():
            yield model

def list_workflows(ordered) -> Iterable:
    with Session(_engine) as session:
        if ordered:
            statement = select(Workflow).order_by(Workflow.purpose, Workflow.name)
        else:
            statement = select(Workflow).order_by(Workflow.name)
        for workflow in session.exec(statement).all():
            yield workflow

def list_collections(ordered) -> Iterable:
    with Session(_engine) as session:
        if ordered:
            statement = select(Collection).order_by(Collection.type, Collection.name)
        else:
            statement = select(Collection).order_by(Collection.type)
        for collection in session.exec(statement).all():
            yield collection

def get_tags(target_types: Set[Taggable] | None, offset: int, limit: int) -> list:
    with Session(_engine) as session:
        if target_types is not None and len(target_types) > 0:
            cond = []
            if Taggable.MODEL in target_types:
                cond.append(Tag.models.any())
            if Taggable.WORKFLOW in target_types:
                cond.append(Tag.workflows.any())
            if Taggable.COLLECTION in target_types:
                cond.append(Tag.collections.any())
            if limit > 0:
                statement = select(Tag).offset(offset).limit(limit).where(or_(*cond))
            else:
                statement = select(Tag).offset(offset).where(or_(*cond))
        else:
            statement = select(Tag).offset(offset).limit(limit)
        found = session.exec(statement).all()
        return [t.tag for t in found]

def get_model(id: str) -> Model | None:
    with Session(_engine) as session:
        return session.get(Model, id)


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


