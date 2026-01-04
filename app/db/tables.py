# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: tables.py
# purpose: Database tables
# ---------------------------------------------------------------------------

from sqlmodel import Field, Relationship, SQLModel, CheckConstraint
from app.model.object_types import Location, ComponentType


class TagModelLink(SQLModel, table=True):
    model_id: int | None = Field(default=None, primary_key=True, foreign_key="model.id")
    tag_id: int | None =  Field(default=None, primary_key=True, foreign_key="tag.id")


class Tag(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    tag: str
    models: list['Model'] | None = Relationship(back_populates="tags", link_model=TagModelLink)


class Model(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    sha256: str
    name: str
    type: str
    active_root: str
    inactive_root: str
    archive_root: str
    is_active: bool
    is_inactive: bool
    is_archived: bool
    last_scan_id: str
    scan_errors: str
    tags: list['Tag'] = Relationship(back_populates="models", link_model=TagModelLink)
    components: list['Component'] = Relationship(back_populates="model")


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
    components: list['Component'] = Relationship(back_populates="workflow")


class Component(SQLModel, table=True):
    """
    Part of a model or of a workflow.
    """
    __table_args__ = (CheckConstraint(
            "(model_id IS NOT NULL AND workflow_id IS NULL) OR (model_id IS NULL AND workflow_id IS NOT NULL)"),)
    id: int | None = Field(default=None, primary_key=True)
    location: Location
    relative_path: str # relative to location root
    filename: str # stem+suffix
    component_type: ComponentType
    is_present: bool
    model_id: int | None = Field(default=None, foreign_key="model.id")
    workflow_id: int | None = Field(default=None, foreign_key="workflow.id")

    model: Model | None = Relationship(back_populates="components")
    workflow: Workflow | None = Relationship(back_populates="components")