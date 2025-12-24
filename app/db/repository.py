# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: repository.py
# purpose: Database operations
# ---------------------------------------------------------------------------

from sqlmodel import SQLModel, Session, create_engine, select
from pathlib import Path
from typing import Sequence
from app.db.tables import ModelTbl
from app.model.object_types import ModelInLocation


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

    def ensure_model_in_location(self, model_in_location: ModelInLocation) -> None:
        pass

    # --- models -----------------------------------------------------------

    def save_model(self, model: ModelTbl) -> None:
        with Session(self.engine) as session:
            session.add(model)

    def get_models(self) -> Sequence[ModelTbl]:
        with Session(self.engine) as session:
            return session.exec(select(ModelTbl)).all()

    def get_model_by_sha(self, sha256: str) -> ModelTbl | None:
        with Session(self.engine) as session:
            return session.get(ModelTbl, sha256)


repo = Repository()
