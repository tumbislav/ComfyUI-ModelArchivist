# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: repository.py
# purpose: Database operations
# ---------------------------------------------------------------------------

from sqlmodel import SQLModel, Session, create_engine, select
from pathlib import Path
from typing import Sequence
from app.db.tables import Model


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

    # --- models -----------------------------------------------------------

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
