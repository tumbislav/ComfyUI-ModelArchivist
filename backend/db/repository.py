# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: repository.py
# purpose: Database operations
# ---------------------------------------------------------------------------

from sqlmodel import SQLModel, Session, create_engine, select, or_
from pathlib import Path
from typing import Iterable, Set
from .tables import Model, Component, Tag
from ..model.object_types import ArchivistError, ArchivistException, Taggable

import logging

logger = logging.getLogger('model_archivist')


class Repository:
    def __init__(self) -> None:
        self.db_path = None
        self.engine = None
        self.is_first_run = None

    def attach(self, db_path: Path, verbose: bool = False) -> None:
        self.db_path = db_path
        self.is_first_run = not db_path.is_file()
        self.engine = create_engine(f'sqlite:///{db_path}', echo=verbose)
        SQLModel.metadata.create_all(self.engine)

    def save_model(self, model: Model, tag_names: list[str]) -> None:
        """
        Save a full model record. We have the following possibilities:
        - the model is not known: add the model,
        - the model is known, but has not been seen in this scan: update it,
        - the model is known and has already been seen in this scan: raise an exception.
        """
        with Session(self.engine) as session:
            known_models = session.exec(select(Model).where(Model.hash == model.hash)).all()
            if len(known_models) == 0:
                logger.info(f'Repository.save_model:adding model {model.name}')
                model.tags = resolve_tags(session, tag_names)
                session.add(model)
                session.commit()
            else:
                logger.info(f'Repository.save_model:updating model {model.name}')
                if len(known_models) > 1:
                    all_names = ', '.join(m.name for m in known_models)
                    raise ArchivistException(ArchivistError.DUPLICATE_MODEL,
                                             f'{model.hash}, {all_names}')
                old_model = known_models[0]
                if old_model.last_scan_id == model.last_scan_id:
                    raise ArchivistException(ArchivistError.DUPLICATE_MODEL,
                                             f'{model.name} {model.hash}, {old_model.last_scan_id}')
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

    def clean_repository(self, scan_id: str):
        with Session(self.engine) as session:
            models = session.exec(select(Model).where(Model.last_scan_id != scan_id))
            for model in models:
                session.delete(model)
            session.commit()

    def get_models(self, ordered) -> Iterable:
        with Session(self.engine) as session:
            if ordered:
                statement = select(Model).order_by(Model.type, Model.name)
            else:
                statement = select(Model).order_by(Model.type)
            for model in session.exec(statement).all():
                yield model

    def get_tags(self, target_types: Set[Taggable] | None, offset: int, limit: int) -> Iterable:
        with Session(self.engine) as session:
            if target_types is not None:
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

    def get_model_by_hash(self, hash: str) -> Iterable:
        with Session(self.engine) as session:
            return session.get(Model, hash)


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


repo = Repository()
