# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: migrations.py
# purpose: Database schema migration management
# ---------------------------------------------------------------------------

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import Connection, Engine


def alembic_config(connection: Connection) -> Config:
    project_root = Path(__file__).resolve().parents[2]
    migration_root = project_root / 'alembic'
    config = Config(str(migration_root / 'alembic.ini'))
    config.set_main_option('script_location', migration_root.as_posix())
    config.attributes['connection'] = connection
    config.attributes['skip_logging_config'] = True
    return config


def update_database_schema(engine: Engine) -> None:
    with engine.begin() as connection:
        command.upgrade(alembic_config(connection), 'head')
