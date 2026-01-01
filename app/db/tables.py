# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: tables.py
# purpose: Database tables
# ---------------------------------------------------------------------------

from sqlmodel import Field, Relationship, SQLModel
from app.model.object_types import Location, ComponentType
from pathlib import Path


class ModelTagLink(SQLModel, table=True):
    model_id: int | None = Field(default=None, primary_key=True, foreign_key="model.id")
    tag_id: int | None = Field(default=None, primary_key=True, foreign_key="tag.id")


class Model(SQLModel, table=True):
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
    last_scan_id: str
    scan_errors: str
    tags: list['Tag'] = Relationship(back_populates='models', link_model=ModelTagLink)


class Tag(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    tag: str
    models: list[Model] = Relationship(back_populates='tags', link_model=ModelTagLink)


class Component(SQLModel, table=True):
    """
    Part of a model or of a workflow.
    """
    id: int | None = Field(default=None, primary_key=True)
    workflow_id: int | None = Field(default=None, foreign_key="workflow.id")
    model_id: int | None = Field(default=None, foreign_key="model.id")
    location: Location
    relative_path: Path # relative to location root
    filename: Path # stem+suffix
    component_type: ComponentType
    is_present: bool

class WorkflowCollectionLink(SQLModel, table=True):
    workflow_id: int = Field(default=None, primary_key=True, foreign_key="workflow.id")
    collection_id: int = Field(default=None, primary_key=True, foreign_key="collection.id")


class Collection(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    purpose: str
    is_active: bool


class CollectionModelLink(SQLModel, table=True):
    collection_id: int = Field(primary_key=True, foreign_key="collection.id")
    model_id: int = Field(default=None, primary_key=True, foreign_key="model.id")


class Workflow(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    purpose: str
    relative_path: str
    is_archived: bool
    is_active: bool
    last_scan_id: str
    scan_errors: str
