# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: repository.py
# purpose: Database operations
# ---------------------------------------------------------------------------

from sqlmodel import SQLModel, Session, create_engine, select
from pathlib import Path
from typing import Iterable
from .tables import Model, Component
from ..model.object_types import ArchivistError, ArchivistException
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

    def save_model(self, model: Model) -> None:
        """
        Save a full model record. We have the following possibilities:
        - the model is not known: add the model,
        - the model is known, but has not been seen in this scan: update it,
        - the model is known and has already been seen in this scan: raise an exception.
        """
        with Session(self.engine) as session:
            known_models = session.exec(select(Model).where(Model.sha256 == model.sha256)).all()
            if len(known_models) == 0:
                logger.info(f'repository.save_model:adding model {model.name}')
                session.add(model)
                session.commit()
            else:
                logger.info(f'repository.save_model:updating model {model.name}')
                if len(known_models) > 1:
                    all_names = ', '.join(m.name for m in known_models)
                    raise ArchivistException(ArchivistError.DUPLICATE_MODEL,
                                             f'{model.sha256}, {all_names}')
                old_model = known_models[0]
                if old_model.last_scan_id == model.last_scan_id:
                    raise ArchivistException(ArchivistError.DUPLICATE_MODEL,
                                             f'{model.name} {model.sha256}, {old_model.last_scan_id}')
                # see which components no longer exist and remove them
                old_components = {(c.file_name, c.component_type, c.is_archive): c.id for c in old_model.components}
                for c in model.components:
                    if (c.file_name, c.component_type, c.is_archive) in old_components:
                        del old_components[(c.file_name, c.component_type, c.is_archive)]
                for c_id in old_components.values():
                    c = session.exec(select(Component).where(Component.id == c_id)).one()
                    session.delete(c)
                model.id = old_model.id
                session.add(model)
                session.commit()

    def get_models(self) -> Iterable:
        with Session(self.engine) as session:
            for model in session.exec(select(Model)).all():
                yield model

    def get_model_by_sha(self, sha256: str) -> Iterable:
        with Session(self.engine) as session:
            return session.get(Model, sha256)

repo = Repository()
