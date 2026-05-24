# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: tables.py
# purpose: Database tables
# ---------------------------------------------------------------------------

from sqlmodel import Field, Relationship, SQLModel, CheckConstraint
from uuid import uuid4


# ---------------------------------------------------------------------------
# Many-to-many connections
# ---------------------------------------------------------------------------

class TagModelLink(SQLModel, table=True):
    model_id: str | None = Field(default=None, primary_key=True, foreign_key="model.id")
    tag: str | None = Field(default=None, primary_key=True, foreign_key="tag.tag")


class TagWorkflowLink(SQLModel, table=True):
    workflow_id: str | None = Field(default=None, primary_key=True, foreign_key="workflow.id")
    tag: str | None = Field(default=None, primary_key=True, foreign_key="tag.tag")


class TagCollectionLink(SQLModel, table=True):
    collection_id: str | None = Field(default=None, primary_key=True, foreign_key="collection.id")
    tag: str | None = Field(default=None, primary_key=True, foreign_key="tag.tag")


class ModelCollectionLink(SQLModel, table=True):
    model_id: str | None = Field(default=None, primary_key=True, foreign_key="model.id")
    collection_id: str | None = Field(default=None, primary_key=True, foreign_key="collection.id")


class WorkflowCollectionLink(SQLModel, table=True):
    workflow_id: str = Field(default=None, primary_key=True, foreign_key="workflow.id")
    collection_id: str = Field(default=None, primary_key=True, foreign_key="collection.id")


class CollectionCollectionLink(SQLModel, table=True):
    parent_id: str | None = Field(default=None, primary_key=True, foreign_key="collection.id")
    child_id: str | None = Field(default=None, primary_key=True, foreign_key="collection.id")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class Model(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str
    type: str
    relative_path: str
    working_dir: str
    archive_dir: str
    working: int
    archived: int
    scan_timestamp: str
    components: list['Component'] = Relationship(back_populates="model", cascade_delete=True)

    tags: list['Tag'] = Relationship(back_populates="models", link_model=TagModelLink)
    collections: list['Collection'] = Relationship(back_populates="models", link_model=ModelCollectionLink)

    def update_from(self, other) -> None:
        self.name = other.name
        self.type = other.type
        self.relative_path = other.relative_path
        self.working_dir = other.working_dir
        self.archive_dir = other.archive_dir
        self.working = other.working
        self.archived = other.archived
        self.scan_timestamp = other.scan_timestamp

    def summary(self, type_map: dict) -> dict:
        return {'id': self.id,
                'name': self.name,
                'type': type_map.get(self.type, self.type),
                'working': self.working,
                'archived': self.archived}

    def representation(self, type_map: dict) -> dict:
        return {'id': self.id,
                'name': self.name,
                'type': type_map.get(self.type, self.type),
                'raw_type': self.type,
                'working_dir': self.working_dir,
                'archive_dir': self.archive_dir,
                'path': self.relative_path,
                'working': self.working,
                'archived': self.archived,
                'tags': [tag.tag for tag in self.tags],
                'components': [component.representation() for component in self.components],
                'collections': [collection.summary() for collection in self.collections]
                }


# ---------------------------------------------------------------------------
# Workflows
# ---------------------------------------------------------------------------

class Workflow(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str
    purpose: str
    working_dir: str
    archive_dir: str
    relative_path: str
    working: int
    archived: int
    scan_timestamp: str
    components: list['Component'] = Relationship(back_populates="workflow")

    tags: list['Tag'] = Relationship(back_populates="workflows", link_model=TagWorkflowLink)
    collections: list['Collection'] = Relationship(back_populates="workflows", link_model=WorkflowCollectionLink)

    def summary(self) -> dict:
        return {'id': self.id,
                'name': self.name,
                'working': self.working,
                'archived': self.archived}

    def representation(self) -> dict:
        return {'id': self.id,
                'name': self.name,
                'purpose': self.purpose,
                'working_dir': self.working_dir,
                'archive_dir': self.archive_dir,
                'working': self.working,
                'archived': self.archived,
                'relative_path': self.relative_path,
                'last_scanned': self.scan_timestamp,
                'tags': [tag.tag for tag in self.tags],
                'components': [component.representation() for component in self.components],
                'collections': [collection.summary() for collection in self.collections]}

# ---------------------------------------------------------------------------
# Collections
# ---------------------------------------------------------------------------

class Collection(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    name: str
    purpose: str

    tags: list['Tag'] = Relationship(back_populates="collections", link_model=TagCollectionLink)
    models: list['Model'] = Relationship(back_populates="collections", link_model=ModelCollectionLink)
    workflows: list['Workflow'] = Relationship(back_populates="collections", link_model=WorkflowCollectionLink)

    children: list['Collection'] = Relationship(
        back_populates="parents",
        link_model=CollectionCollectionLink,
        sa_relationship_kwargs={
            "primaryjoin": lambda: Collection.id == CollectionCollectionLink.parent_id,
            "secondaryjoin": lambda: Collection.id == CollectionCollectionLink.child_id
        }
    )

    parents: list['Collection'] = Relationship(
        back_populates="children",
        link_model=CollectionCollectionLink,
        sa_relationship_kwargs={
            "primaryjoin": lambda: Collection.id == CollectionCollectionLink.child_id,
            "secondaryjoin": lambda: Collection.id == CollectionCollectionLink.parent_id
        }
    )

    def summary(self) -> dict:
        return {'id': self.id,
                'name': self.name}

    def representation(self, type_map: dict) -> dict:
        return {'id': self.id,
                'name': self.name,
                'purpose': self.purpose,
                'tags': [tag.tag for tag in self.tags],
                'models': [model.summary(type_map) for model in self.models],
                'workflows': [workflow.summary() for workflow in self.workflows],
                'children': [collection.summary() for collection in self.children],
                'parents': [collection.summary() for collection in self.parents]}

# ---------------------------------------------------------------------------
# Component files
# ---------------------------------------------------------------------------

class Component(SQLModel, table=True):
    """
    A file, part of a model or of a workflow.
    """
    __table_args__ = (CheckConstraint(
        "(model_id IS NOT NULL AND workflow_id IS NULL) OR (model_id IS NULL AND workflow_id IS NOT NULL)"),)
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    where: str
    file_name: str
    file_dir: str
    component_type: str
    scan_timestamp: str
    model_id: str | None = Field(default=None, foreign_key="model.id")
    workflow_id: str | None = Field(default=None, foreign_key="workflow.id")

    model: Model | None = Relationship(back_populates="components")
    workflow: Workflow | None = Relationship(back_populates="components")

    def representation(self) -> dict:
        return {'id': self.id,
                'where': self.where,
                'file_name': self.file_name,
                'file_dir': self.file_dir,
                'component_type': str(self.component_type),
                'last_scanned': self.scan_timestamp}

# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------

class Tag(SQLModel, table=True):
    tag: str = Field(default=None, primary_key=True)
    models: list['Model'] | None = Relationship(back_populates="tags", link_model=TagModelLink)
    workflows: list['Workflow'] | None = Relationship(back_populates="tags", link_model=TagWorkflowLink)
    collections: list['Collection'] | None = Relationship(back_populates="tags", link_model=TagCollectionLink)
