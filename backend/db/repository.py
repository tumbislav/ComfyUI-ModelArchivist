# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: repository.py
# purpose: Database operations
# ---------------------------------------------------------------------------

from sqlmodel import SQLModel, Session, create_engine, select
from pathlib import Path
from typing import Iterable
from .tables import Model, Workflow
from ..model.object_types import ScanError, Location


def set_scan_error(obj: Model | Workflow | Model, error_code: ScanError, scan_id: str):
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

    def ensure_model_in_location(self, model: Model, location: Location) -> None:
        with Session(self.engine) as session:
            model_ids = session.exec(select(Model.id).where(Model.sha256 == model.sha256)).all()
            if len(model_ids) == 0:
                model.is_active = location == Location.ACTIVE
                model.is_inactive = location == Location.INACTIVE
                model.is_archived = location == Location.ARCHIVE
                session.add(model)
                session.commit()
            else:
                o_model = session.get(Model, model_ids[0])
                o_model.is_active = o_model.is_active or (location == Location.ACTIVE)
                o_model.is_inactive = o_model.is_inactive or (location == Location.INACTIVE)
                o_model.is_archived = o_model.is_archived or (location == Location.ARCHIVE)
                o_model.name = model.name
                o_model.type = model.type
                o_model.active_root = model.active_root
                o_model.inactive_root = model.inactive_root
                o_model.archive_root = model.archive_root
                session.add(o_model)
                session.refresh(o_model)
                known_comps = {}
                for o_comp in o_model.components:
                    if o_comp.location == location:
                        known_comps[(o_comp.filename, o_comp.relative_path)] = o_comp
                for comp in model.components:
                    if (comp.filename, comp.relative_path) not in known_comps:
                        comp.model = o_model
                        session.add(comp)
                        del known_comps[(comp.filename, comp.relative_path)]
                for comp in known_comps.values():
                    comp.is_present = False
                    session.add(comp)
                session.commit()

    def save_model(self, model: Model) -> None:
        with Session(self.engine) as session:
            session.add(model)

    def get_models(self) -> Iterable:
        with Session(self.engine) as session:
            for model in session.exec(select(Model)).all():
                yield model

    def get_model_by_sha(self, sha256: str) -> Iterable:
        with Session(self.engine) as session:
            return session.get(Model, sha256)

repo = Repository()
