# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: migrations.py
# purpose: Database schema migration management
# ---------------------------------------------------------------------------

from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect
from sqlalchemy.engine import Connection, Engine
from sqlmodel import SQLModel

from backend.exception import ArcException
import backend.repository.tables  # noqa: F401

BASELINE_REVISION = '16da8f3ac79c'
BASELINE_REMOVED_COLUMNS = {'component': {'size', 'modified_at_ns'}}


def alembic_config(connection: Connection) -> Config:
    project_root = Path(__file__).resolve().parents[2]
    migration_root = project_root / 'alembic'
    config = Config(str(migration_root / 'alembic.ini'))
    config.set_main_option('script_location', migration_root.as_posix())
    config.attributes['connection'] = connection
    config.attributes['skip_logging_config'] = True
    return config


def detect_unversioned_revision(connection: Connection) -> str:
    """Return the revision matching a supported unversioned database schema."""
    inspector = inspect(connection)
    actual_tables = set(inspector.get_table_names()) - {'alembic_version'}
    expected_tables = set(SQLModel.metadata.tables)
    if actual_tables != expected_tables:
        raise ArcException(
            ArcException.Code.INVALID_DATABASE,
            f'unversioned schema has unexpected tables; expected {sorted(expected_tables)}, '
            f'found {sorted(actual_tables)}',
        )
    actual_columns = {
        table_name: {column['name'] for column in inspector.get_columns(table_name)}
        for table_name in expected_tables
    }
    head_columns = {
        table_name: set(SQLModel.metadata.tables[table_name].columns.keys())
        for table_name in expected_tables
    }
    if actual_columns == head_columns:
        return 'head'

    baseline_columns = {
        table_name: columns - BASELINE_REMOVED_COLUMNS.get(table_name, set())
        for table_name, columns in head_columns.items()
    }
    if actual_columns == baseline_columns:
        return BASELINE_REVISION

    mismatches = [
        f'{table_name}: expected {sorted(head_columns[table_name])}, '
        f'found {sorted(actual_columns[table_name])}'
        for table_name in sorted(expected_tables)
        if actual_columns[table_name] != head_columns[table_name]
    ]
    raise ArcException(
        ArcException.Code.INVALID_DATABASE,
        'unversioned schema does not match a supported revision; ' + '; '.join(mismatches),
    )


def update_database_schema(engine: Engine) -> None:
    """Adopt a compatible pre-Alembic database and upgrade it to head."""
    with engine.begin() as connection:
        config = alembic_config(connection)
        context = MigrationContext.configure(connection)
        current_revision = context.get_current_revision()
        actual_tables = set(inspect(connection).get_table_names()) - {'alembic_version'}

        if current_revision is None and actual_tables:
            matching_revision = detect_unversioned_revision(connection)
            command.stamp(config, matching_revision)
        command.upgrade(config, 'head')
