# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: tables.py
# purpose: Database tables
# ---------------------------------------------------------------------------

from sqlmodel import Field, Relationship, SQLModel
from app.model.object_types import Location
from pathlib import Path


class ModelTagsTbl(SQLModel, table=True):
    model_id: int | None = Field(default=None, primary_key=True, foreign_key='modeltbl.id')
    tag_id: int | None = Field(default=None, primary_key=True, foreign_key='tagtbl.id')


class ModelTbl(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    sha256: str
    name: str
    type: str
    active_root: Path
    inactive_root: Path
    archive_root: Path | None
    relative_path: Path
    is_active: bool
    is_archived: bool
    status: str
    is_accessible: bool
    last_scan: str
    scan_errors: str

    tags: list['TagTbl'] = Relationship(back_populates='tag', link_model=ModelTagsTbl)


class TagTbl(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    tag: str

    models: list['ModelTbl'] = Relationship(back_populates='model', link_model=ModelTagsTbl)


class ModelFile(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    model_id: int | None = Field(default=None, foreign_key='modeltbl.id')
    loc: Location
    path: Path
    type: str
    is_present: bool


class CollectionTbl(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    purpose: str
    is_active: bool

class CollectionModelsTbl(SQLModel, table=True):
    collection_id: int = Field(primary_key=True, foreign_key='collectiontbl.id')
    model_id: int = Field(default=None, primary_key=True, foreign_key='modeltbl.id')


class WorkflowTbl(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    purpose: str
    relative_path: str
    is_archived: bool
    is_active: bool


class WorkflowsCollectionsTbl(SQLModel, table=True):
    workflow_id: int = Field(default=None, primary_key=True, foreign_key='Workflowtbl.id')
    collection_id: int = Field(default=None, primary_key=True, foreign_key='CollectionTbl.id')
