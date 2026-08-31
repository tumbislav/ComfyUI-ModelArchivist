# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: tables.py
# purpose: Database tables
# ---------------------------------------------------------------------------
from enum import StrEnum
from pathlib import Path

from sqlalchemy import Column, JSON, String, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel, CheckConstraint
from uuid import uuid4

# ---------------------------------------------------------------------------
# Helpful enums
# ---------------------------------------------------------------------------

class PrimaryObjectType(StrEnum):
    MODEL = 'md'
    WORKFLOW = 'wf'
    COLLECTION = 'cl'
    USER_OBJECT = 'uo'


class UserObjectClass(StrEnum):
    FILE = 'file'
    FOLDER = 'folder'


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
    MIXED = 'mixed'


class WorkflowError(StrEnum):
    INVALID_CONFIG = 'invalid_config'
    DUPLICATE_WORKING = 'duplicate_working'
    DUPLICATE_ARCHIVE = 'duplicate_archive'
    LOCATION_MISMATCH = 'location_mismatch'


class ModelError(StrEnum):
    UNREADABLE = 'unreadable'
    DUPLICATE_WORKING = 'duplicate_working'
    DUPLICATE_ARCHIVE = 'duplicate_archive'
    LOCATION_MISMATCH = 'location_mismatch'
    PATH_IDENTITY_CONFLICT = 'path_identity_conflict'
    AMBIGUOUS_STEM = 'ambiguous_stem'
    METADATA_RENAME = 'metadata_rename'


class UserObjectError(StrEnum):
    OVER_SIZE_LIMIT = 'over_size_limit'
    UNREADABLE = 'unreadable'
    LOCATION_MISMATCH = 'location_mismatch'

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


class TagUserObjectLink(SQLModel, table=True):
    user_object_id: str = Field(primary_key=True, foreign_key="userdefinedobject.id")
    tag: str = Field(primary_key=True, foreign_key="tag.tag")


class UserObjectCollectionLink(SQLModel, table=True):
    user_object_id: str = Field(primary_key=True, foreign_key="userdefinedobject.id")
    collection_id: str = Field(primary_key=True, foreign_key="collection.id")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class ApplicationSettings(SQLModel, table=True):
    id: int = Field(default=1, primary_key=True)
    setup_complete: bool = False
    update_json_metadata: bool = True
    ignore_unknown_types: bool = False
    always_recalc_hashes: bool = False


class ModelTypeSetting(SQLModel, table=True):
    name: str = Field(primary_key=True)
    display_name: str
    extensions: list[str] = Field(default_factory=list,
                                  sa_column=Column(JSON, nullable=False))


class ModelLocationSetting(SQLModel, table=True):
    __table_args__ = (UniqueConstraint('working_dir'), UniqueConstraint('archive_dir'))
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    model_type: str = Field(foreign_key='modeltypesetting.name')
    source: str = 'standalone'
    working_dir: str
    archive_dir: str | None = None
    active: bool = True


class WorkflowLocationSetting(SQLModel, table=True):
    __table_args__ = (UniqueConstraint('working_dir'), UniqueConstraint('archive_dir'))
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    source: str = 'standalone'
    working_dir: str
    archive_dir: str | None = None
    active: bool = True

#todo: add notes and civitai.name == version, base model, from_civitai, civitai.model_id + civitai.id (version id)

class Model(SQLModel, table=True):
    id: str = Field(primary_key=True)
    file_name: str
    internal_name: str
    type: str
    file_format: str = ''
    relative_path: str
    deployment: str
    touched: str
    errors: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    component_sets: list['ComponentSet'] = Relationship(back_populates="model", cascade_delete=True)

    tags: list['Tag'] = Relationship(back_populates="models", link_model=TagModelLink)
    collections: list['Collection'] = Relationship(back_populates="models", link_model=ModelCollectionLink)

    @property
    def read_only(self) -> bool:
        return any(error != ModelError.METADATA_RENAME.value for error in self.errors)

    @property
    def metadata_update_available(self) -> bool:
        return ModelError.METADATA_RENAME.value in self.errors

    def update_from(self, other) -> None:
        self.file_name = other.file_name
        self.internal_name = other.internal_name
        self.type = other.type
        self.file_format = other.file_format
        self.relative_path = other.relative_path
        self.deployment = other.deployment
        self.touched = other.touched

    def summary(self, type_map: dict) -> dict:
        return { 'id': self.id,
                 'file_name': self.file_name,
                 'internal_name': self.internal_name,
                 'type': type_map.get(self.type, self.type),
                 'file_format': self.file_format,
                 'deployment': self.deployment,
                 'errors': self.errors,
                 'read_only': self.read_only,
                 'metadata_update_available': self.metadata_update_available }

    def representation(self, type_map: dict, working_path: str | None = None,
                       archive_path: str | None = None) -> dict:
        sets = {component_set.where: component_set.representation()
                for component_set in self.component_sets}
        return { 'id': self.id,
                 'file_name': self.file_name,
                 'internal_name': self.internal_name,
                 'type': type_map.get(self.type, self.type),
                 'raw_type': self.type,
                 'file_format': self.file_format,
                 'working_path': working_path,
                 'archive_path': archive_path,
                 'relative_path': self.relative_path.replace('\\', '/'),
                 'deployment': self.deployment,
                 'touched': self.touched,
                 'errors': self.errors,
                 'read_only': self.read_only,
                 'metadata_update_available': self.metadata_update_available,
                 'tags': [tag.tag for tag in self.tags],
                 'working_set': sets.get('w'),
                 'archive_set': sets.get('a'),
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
    errors: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    component_sets: list['ComponentSet'] = Relationship(back_populates="workflow", cascade_delete=True)

    tags: list['Tag'] = Relationship(back_populates="workflows", link_model=TagWorkflowLink)
    collections: list['Collection'] = Relationship(back_populates="workflows", link_model=WorkflowCollectionLink)

    @property
    def read_only(self) -> bool:
        return len(self.errors) > 0

    def update_from(self, other) -> None:
        self.file_name = other.file_name
        self.internal_name = other.internal_name
        self.purpose = other.purpose
        self.relative_path = other.relative_path
        self.deployment = other.deployment
        self.touched = other.touched
        self.errors = list(other.errors)

    def summary(self) -> dict:
        return { 'id': self.id,
                 'file_name': self.file_name,
                 'internal_name': self.internal_name,
                 'purpose': self.purpose,
                 'deployment': self.deployment,
                 'errors': self.errors,
                 'read_only': self.read_only }

    def representation(self, working_path: str | None = None,
                       archive_path: str | None = None) -> dict:
        sets = {component_set.where: component_set.representation()
                for component_set in self.component_sets}
        return {'id': self.id,
                'file_name': self.file_name,
                'internal_name': self.internal_name,
                'purpose': self.purpose,
                'working_path': working_path,
                'archive_path': archive_path,
                'relative_path': self.relative_path,
                'deployment': self.deployment,
                'touched': self.touched,
                'errors': self.errors,
                'read_only': self.read_only,
                'tags': [tag.tag for tag in self.tags],
                'working_set': sets.get('w'),
                'archive_set': sets.get('a'),
                'collections': [collection.summary() for collection in self.collections]}


# ---------------------------------------------------------------------------
# User-defined types and objects
# ---------------------------------------------------------------------------

class UserDefinedType(SQLModel, table=True):
    __table_args__ = (
        CheckConstraint("object_class IN ('file', 'folder')"),
        CheckConstraint('size_limit > 0'),
        CheckConstraint('small = 0 OR size_limit <= 1048576'),
        UniqueConstraint('working_dir'),
        UniqueConstraint('archive_dir'),
    )
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    name: str = Field(sa_column=Column(String(collation='NOCASE'), unique=True,
                                       nullable=False))
    short_name: str
    object_class: str
    extensions: list[str] = Field(default_factory=list,
                                  sa_column=Column(JSON, nullable=False))
    working_dir: str
    archive_dir: str
    icon: str
    purpose: str = ''
    size_limit: int = 10 * 1024 * 1024
    small: bool = False
    objects: list['UserDefinedObject'] = Relationship(back_populates='type',
                                                       cascade_delete=True)

    def summary(self) -> dict:
        return {'id': self.id, 'name': self.name, 'short_name': self.short_name,
                'object_class': self.object_class,
                'extensions': self.extensions, 'icon': self.icon, 'purpose': self.purpose,
                'size_limit': self.size_limit, 'small': self.small,
                'object_count': len(self.objects)}

    def representation(self) -> dict:
        return {**self.summary(), 'working_dir': self.working_dir,
                'archive_dir': self.archive_dir}


class UserDefinedObject(SQLModel, table=True):
    __table_args__ = (UniqueConstraint('type_id', 'relative_path'),)
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    type_id: str = Field(foreign_key='userdefinedtype.id')
    relative_path: str
    display_name: str
    purpose: str = ''
    deployment: str
    size: int = 0
    modified_at_ns: int = 0
    touched: str
    errors: list[str] = Field(default_factory=list,
                              sa_column=Column(JSON, nullable=False))
    type: UserDefinedType = Relationship(back_populates='objects')
    sets: list['UserObjectSet'] = Relationship(back_populates='object', cascade_delete=True)
    tags: list['Tag'] = Relationship(back_populates='user_objects',
                                     link_model=TagUserObjectLink)
    collections: list['Collection'] = Relationship(back_populates='user_objects',
                                                    link_model=UserObjectCollectionLink)

    @property
    def read_only(self) -> bool:
        return bool(self.errors)

    def summary(self) -> dict:
        return {'id': self.id, 'type_id': self.type_id, 'relative_path': self.relative_path,
                'display_name': self.display_name, 'purpose': self.purpose,
                'deployment': self.deployment, 'size': self.size,
                'modified_at_ns': self.modified_at_ns, 'errors': self.errors,
                'read_only': self.read_only}

    def representation(self) -> dict:
        sets = {item.where: item.representation() for item in self.sets}
        return {**self.summary(), 'touched': self.touched,
                'type': self.type.summary(), 'tags': [tag.tag for tag in self.tags],
                'working_set': sets.get('w'), 'archive_set': sets.get('a'),
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
    user_objects: list['UserDefinedObject'] = Relationship(
        back_populates='collections', link_model=UserObjectCollectionLink)

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
                'name': self.name,
                'parents': [
                    {'id': collection.id, 'name': collection.name}
                    for collection in sorted(
                        self.parents, key=lambda item: (item.name.casefold(), item.id))
                ]}

    @property
    def deployment(self) -> DeploymentStatus:
        """Return the aggregate deployment of all transitive leaf members."""
        deployments: set[str] = set()
        visited: set[str] = set()

        def collect(collection: 'Collection') -> None:
            if collection.id in visited:
                return
            visited.add(collection.id)
            deployments.update(model.deployment for model in collection.models)
            deployments.update(workflow.deployment for workflow in collection.workflows)
            deployments.update(user_object.deployment for user_object in collection.user_objects)
            for child in collection.children:
                collect(child)

        collect(self)
        if deployments == {DeploymentStatus.WORKING.value}:
            return DeploymentStatus.WORKING
        if deployments == {DeploymentStatus.ARCHIVE.value}:
            return DeploymentStatus.ARCHIVE
        if deployments == {DeploymentStatus.SYNCED.value}:
            return DeploymentStatus.SYNCED
        return DeploymentStatus.MIXED

    def representation(self, type_map: dict) -> dict:
        return {'id': self.id,
                'name': self.name,
                'purpose': self.purpose,
                'deployment': self.deployment,
                'tags': [tag.tag for tag in self.tags],
                'models': [model.summary(type_map) for model in self.models],
                'workflows': [workflow.summary() for workflow in self.workflows],
                'user_objects': [user_object.summary() for user_object in self.user_objects],
                'children': [collection.summary() for collection in self.children],
                'parents': [collection.summary() for collection in self.parents]}

# ---------------------------------------------------------------------------
# Component files and component sets
# ---------------------------------------------------------------------------

class ComponentSet(SQLModel, table=True):
    """
    All the components in a set
    """
    __table_args__ = (
        CheckConstraint("\"where\" IN ('w', 'a')"),
        CheckConstraint(
            "(model_id IS NOT NULL AND workflow_id IS NULL) OR "
            "(model_id IS NULL AND workflow_id IS NOT NULL)"),
        UniqueConstraint('model_id', 'where'),
        UniqueConstraint('workflow_id', 'where'),
    )
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
    relative_path: str = ''
    size: int = 0
    modified_at_ns: int = 0
    component_type: str
    touched: str
    component_set_id: str | None = Field(default=None, foreign_key="componentset.id")
    component_set: ComponentSet = Relationship(back_populates="components")

    @property
    def file_dir(self) -> str:
        root = (self.component_set.examples_dir
                if self.component_type == ComponentType.EXAMPLE
                else self.component_set.primary_dir)
        return str(Path(root) / self.relative_path)

    def representation(self) -> dict:
        return { 'id': self.id,
                 'file_name': self.file_name,
                 'relative_path': self.relative_path,
                 'size': self.size,
                 'modified_at_ns': self.modified_at_ns,
                 'component_type': str(self.component_type),
                 'touched': self.touched }


class UserObjectSet(SQLModel, table=True):
    __table_args__ = (
        CheckConstraint("\"where\" IN ('w', 'a')"),
        UniqueConstraint('object_id', 'where'),
    )
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    object_id: str = Field(foreign_key='userdefinedobject.id')
    where: str
    size: int = 0
    modified_at_ns: int = 0
    object: UserDefinedObject = Relationship(back_populates='sets')
    entries: list['UserObjectEntry'] = Relationship(back_populates='object_set',
                                                     cascade_delete=True)

    def representation(self) -> dict:
        return {'id': self.id, 'where': self.where, 'size': self.size,
                'modified_at_ns': self.modified_at_ns,
                'entries': [entry.representation() for entry in self.entries]}


class UserObjectEntry(SQLModel, table=True):
    __table_args__ = (
        CheckConstraint("entry_type IN ('file', 'directory')"),
        UniqueConstraint('object_set_id', 'relative_path'),
    )
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    object_set_id: str = Field(foreign_key='userobjectset.id')
    relative_path: str
    entry_type: str
    size: int = 0
    modified_at_ns: int = 0
    object_set: UserObjectSet = Relationship(back_populates='entries')

    def representation(self) -> dict:
        return {'id': self.id, 'relative_path': self.relative_path,
                'entry_type': self.entry_type, 'size': self.size,
                'modified_at_ns': self.modified_at_ns}

# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------

class Tag(SQLModel, table=True):
    tag: str = Field(default=None, primary_key=True)
    models: list['Model'] | None = Relationship(back_populates="tags", link_model=TagModelLink)
    workflows: list['Workflow'] | None = Relationship(back_populates="tags", link_model=TagWorkflowLink)
    collections: list['Collection'] | None = Relationship(back_populates="tags", link_model=TagCollectionLink)
    user_objects: list['UserDefinedObject'] | None = Relationship(
        back_populates='tags', link_model=TagUserObjectLink)

