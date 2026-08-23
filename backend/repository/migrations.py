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


def alembic_config(connection: Connection) -> Config:
    project_root = Path(__file__).resolve().parents[2]
    migration_root = project_root / 'alembic'
    config = Config(str(migration_root / 'alembic.ini'))
    config.set_main_option('script_location', migration_root.as_posix())
    config.attributes['connection'] = connection
    config.attributes['skip_logging_config'] = True
    return config


def validate_baseline_schema(connection: Connection) -> None:
    """Verify an unversioned database matches the current baseline schema."""
    inspector = inspect(connection)
    actual_tables = set(inspector.get_table_names()) - {'alembic_version'}
    expected_tables = set(SQLModel.metadata.tables)
    if actual_tables != expected_tables:
        raise ArcException(
            ArcException.Code.INVALID_DATABASE,
            f'unversioned schema has unexpected tables; expected {sorted(expected_tables)}, '
            f'found {sorted(actual_tables)}',
        )
    for table_name in expected_tables:
        actual_columns = {column['name'] for column in inspector.get_columns(table_name)}
        expected_columns = set(SQLModel.metadata.tables[table_name].columns.keys())
        if actual_columns != expected_columns:
            raise ArcException(
                ArcException.Code.INVALID_DATABASE,
                f'unversioned table {table_name} has unexpected columns; '
                f'expected {sorted(expected_columns)}, found {sorted(actual_columns)}',
            )


def update_database_schema(engine: Engine) -> None:
    """Adopt a compatible pre-Alembic database and upgrade it to head."""
    with engine.begin() as connection:
        config = alembic_config(connection)
        context = MigrationContext.configure(connection)
        current_revision = context.get_current_revision()
        actual_tables = set(inspect(connection).get_table_names()) - {'alembic_version'}

        if current_revision is None and actual_tables:
            validate_baseline_schema(connection)
            command.stamp(config, 'head')
        command.upgrade(config, 'head')
