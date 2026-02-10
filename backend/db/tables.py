# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: tables.py
# purpose: Database tables
# ---------------------------------------------------------------------------

from sqlmodel import Field, Relationship, SQLModel, CheckConstraint
from ..model.object_types import ComponentType


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
    relative_path: str
    active_type_dir: str
    archive_type_dir: str
    is_active: bool
    is_archived: bool
    last_scan_id: str
    tags: list['Tag'] = Relationship(back_populates="models", link_model=TagModelLink)
    components: list['Component'] = Relationship(back_populates="model", cascade_delete=True)

    def update_from(self, other) -> None:
        self.last_scan_id = other.last_scan_id
        self.name = other.name
        self.relative_path = other.relative_path
        self.is_active = other.is_active
        self.active_type_dir = other.active_type_dir
        self.archive_type_dir = other.archive_type_dir
        self.type = other.type


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
    A file, part of a model or of a workflow.
    """
    __table_args__ = (CheckConstraint(
            "(model_id IS NOT NULL AND workflow_id IS NULL) OR (model_id IS NULL AND workflow_id IS NOT NULL)"),)
    id: int | None = Field(default=None, primary_key=True)
    is_archive: bool
    file_name: str
    file_dir: str
    component_type: ComponentType
    last_scan_id: str
    model_id: int | None = Field(default=None, foreign_key="model.id")
    workflow_id: int | None = Field(default=None, foreign_key="workflow.id")

    model: Model | None = Relationship(back_populates="components")
    workflow: Workflow | None = Relationship(back_populates="components")