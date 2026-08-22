# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: tables.py
# purpose: Database tables
# ---------------------------------------------------------------------------
from enum import StrEnum

from sqlmodel import Field, Relationship, SQLModel, CheckConstraint
from uuid import uuid4

# ---------------------------------------------------------------------------
# Helpful enums
# ---------------------------------------------------------------------------

class PrimaryObjectType(StrEnum):
    MODEL = 'md'
    WORKFLOW = 'wf'
    COLLECTION = 'cl'


class ComponentType(StrEnum):
    MODEL = 'model'
    METADATA = 'metadata'
    EXTRA = 'extra'
    EXAMPLE = 'example'
    WORKFLOW = 'workflow'


class DeploymentStatus(StrEnum):
    WORKING = 'working'
    ARCHIVE = 'archive'
    SYNCED = 'synced'
    MISMATCH = 'mismatch'

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

#todo: add notes and civitai.name == version, base model, from_civitai, civitai.model_id + civitai.id (version id)

class Model(SQLModel, table=True):
    id: str = Field(primary_key=True)
    file_name: str
    internal_name: str
    type: str
    relative_path: str
    deployment: str
    touched: str
    component_sets: list['ComponentSet'] = Relationship(back_populates="model", cascade_delete=True)

    tags: list['Tag'] = Relationship(back_populates="models", link_model=TagModelLink)
    collections: list['Collection'] = Relationship(back_populates="models", link_model=ModelCollectionLink)

    def update_from(self, other) -> None:
        self.file_name = other.file_name
        self.internal_name = other.internal_name
        self.type = other.type
        self.relative_path = other.relative_path
        self.deployment = other.deployment
        self.touched = other.touched

    def summary(self, type_map: dict) -> dict:
        return { 'id': self.id,
                 'file_name': self.file_name,
                 'internal_name': self.internal_name,
                 'type': type_map.get(self.type, self.type),
                 'deployment': self.deployment }

    def representation(self, type_map: dict) -> dict:
        return { 'id': self.id,
                 'file_name': self.file_name,
                 'internal_name': self.internal_name,
                 'type': type_map.get(self.type, self.type),
                 'raw_type': self.type,
                 'relative_path': self.relative_path.replace('\\', '/'),
                 'deployment': self.deployment,
                 'touched': self.touched,
                 'tags': [tag.tag for tag in self.tags],
                 'component_sets': [cs.representation() for cs in self.component_sets],
                 'collections': [collection.summary() for collection in self.collections] }


# ---------------------------------------------------------------------------
# Workflows
# ---------------------------------------------------------------------------

class Workflow(SQLModel, table=True):
    id: str = Field(primary_key=True)
    file_name: str
    internal_name: str
    purpose: str
    relative_path: str
    deployment: str
    touched: str
    component_sets: list['ComponentSet'] = Relationship(back_populates="workflow", cascade_delete=True)

    tags: list['Tag'] = Relationship(back_populates="workflows", link_model=TagWorkflowLink)
    collections: list['Collection'] = Relationship(back_populates="workflows", link_model=WorkflowCollectionLink)

    def summary(self) -> dict:
        return { 'id': self.id,
                 'file_name': self.file_name,
                 'internal_name': self.file_name,
                 'working': self.working,
                 'archived': self.archived,
                 'deployment': self.deployment }

    def representation(self) -> dict:
        return {'id': self.id,
                'file_name': self.name,
                'internal_name': self.name,
                'purpose': self.purpose,
                'relative_path': self.relative_path,
                'deployment': self.deployment,
                'touched': self.touched,
                'tags': [tag.tag for tag in self.tags],
                'component_sets': [cs.representation() for cs in self.component_sets],
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
# Component files and component sets
# ---------------------------------------------------------------------------

class ComponentSet(SQLModel, table=True):
    """
    All the components in a set
    """
    __table_args__ = (CheckConstraint(
        "(model_id IS NOT NULL AND workflow_id IS NULL) OR (model_id IS NULL AND workflow_id IS NOT NULL)"),)
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    where: str
    primary_dir: str
    examples_dir: str | None
    model_id: str | None = Field(default=None, foreign_key="model.id")
    model: Model | None = Relationship(back_populates='component_sets')

    workflow_id: str | None = Field(default=None, foreign_key="workflow.id")
    workflow: Workflow | None = Relationship(back_populates='component_sets')

    components: list['Component'] = Relationship(back_populates="component_set", cascade_delete=True)

    def representation(self) -> dict:
        return { 'id': self.id,
                 'where': self.where,
                 'primary_dir': self.primary_dir,
                 'examples_dir': self.examples_dir,
                 'components': [c.representation() for c in self.components] }

class Component(SQLModel, table=True):
    """
    A file, part of a model or of a workflow.
    """
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    file_name: str
    component_type: str
    touched: str
    component_set_id: str | None = Field(default=None, foreign_key="componentset.id")
    component_set: ComponentSet = Relationship(back_populates="components")

    def representation(self) -> dict:
        return { 'id': self.id,
                 'file_name': self.file_name,
                 'component_type': str(self.component_type),
                 'touched': self.touched }

# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------

class Tag(SQLModel, table=True):
    tag: str = Field(default=None, primary_key=True)
    models: list['Model'] | None = Relationship(back_populates="tags", link_model=TagModelLink)
    workflows: list['Workflow'] | None = Relationship(back_populates="tags", link_model=TagWorkflowLink)
    collections: list['Collection'] | None = Relationship(back_populates="tags", link_model=TagCollectionLink)

