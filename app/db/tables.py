# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: tables.py
# purpose: Database tables
# ---------------------------------------------------------------------------

from sqlmodel import Field, Relationship, SQLModel


class TagInModelTbl(SQLModel, table=True):
    model_id: int | None = Field(default=None, primary_key=True, foreign_key='model.id')
    tag_id: int | None = Field(default=None, primary_key=True, foreign_key='tag.id')


class ModelTbl(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    sha256: str
    name: str
    type: str
    active_path: str
    inactive_path: str
    archive_path: str | None
    is_archived: bool
    is_active: bool
    has_metadata: bool
    status: str
    is_accessible: bool

    tags: list['TagTbl'] = Relationship(back_populates='tag', link_model=TagInModelTbl)


class TagTbl(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    tag: str

    models: list['ModelTbl'] = Relationship(back_populates='model', link_model=TagInModelTbl)


"""
class Attachments(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    model_id: int = Field(index=True, foreign_key='Models.id')
    type: str
    relative_path: str
    filename: str


class Collections(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    purpose: str


class CollectionMembers(SQLModel, table=True):
    collection_id: int = Field(primary_key=True, foreign_key='Collections.id')
    model_id: int = Field(default=None, primary_key=True, foreign_key='Models.id')


class Workflows(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    purpose: str
    active_path: str
    inactive_path: str
    archive_path: str | None
    is_archived: bool
    is_active: bool


class WorkflowsCollections(SQLModel, table=True):
    workflow_id: int = Field(default=None, primary_key=True, foreign_key='Workflows.id')
    collection_id: int = Field(default=None, primary_key=True, foreign_key='Collections.id')
"""