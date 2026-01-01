# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: repository.py
# purpose: Database operations
# ---------------------------------------------------------------------------

from sqlmodel import SQLModel, Session, create_engine, select
# from sqlalchemy.exc import NoResultFound
from pathlib import Path
from typing import Sequence
from app.db.tables import Model, Workflow, ModelFileTbl
from app.model.object_types import ModelInLocation, ScanError


def set_scan_error(obj: Model | Workflow | ModelFileTbl, error_code: ScanError, scan_id: str):
    if obj.last_scan_id == scan_id:
        errors = {_ for _ in obj.scan_errors.split(',')}
        errors.add(str(error_code))
        obj.scan_errors = ','.join(_ for _ in errors)
    else:
        obj.scan_errors = str(error_code)
        obj.last_scan_id = scan_id


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

    def ensure_model_in_location(self, mdl_loc: ModelInLocation, scan_id: str) -> None:
        with Session(self.engine) as session:
            model_ids = session.exec(select(Model.id).where(Model.sha256 == mdl_loc.sha256)).all()
            if len(model_ids) > 1:
                for id in model_ids:
                    model = session.get(Model, id)
                    set_scan_error(model, ScanError.DUPLICATES, scan_id)
                    session.add(model)
                session.commit()
            elif len(model_ids) == 0:
                #TODO create a new model instance
                model = Model()
                model.sha256 = mdl_loc.sha256
                model.name = mdl_loc.name
                model.type = mdl_loc.type
                model.last_scan_id = scan_id
                model.relative_path= mdl_loc.relative_path
                model.is_accessible = True

                model.active_root: Path
                model.inactive_root: Path
                model.archive_root: Path | None
                model.is_active: bool
                model.is_archived: bool
                model.status: str

            else:
                pass #TODO see if model needs updating. If so, set last_scan_id to current scan_id

    def save_model(self, model: Model) -> None:
        with Session(self.engine) as session:
            session.add(model)

    def get_models(self) -> Sequence[Model]:
        with Session(self.engine) as session:
            return session.exec(select(Model)).all()

    def get_model_by_sha(self, sha256: str) -> Model | None:
        with Session(self.engine) as session:
            return session.get(Model, sha256)


repo = Repository()
