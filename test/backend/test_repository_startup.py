# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: test_repository_startup.py
# purpose: Tests for repository startup
# ---------------------------------------------------------------------------

import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic.migration import MigrationContext
from sqlmodel import Session, SQLModel

from backend.exception import ArcException
import backend.repository.repository as repository
from backend.repository.tables import Tag


def repository_config(db_file: Path, log_file: Path):
    return SimpleNamespace(
        db_file=db_file,
        dbms_prefix='sqlite:///',
        log_file=str(log_file),
        sql_log_level='WARNING',
        read_only=False,
        options=SimpleNamespace(always_recalc_hashes=False),
    )


@pytest.fixture(autouse=True)
def reset_repository_state(monkeypatch: pytest.MonkeyPatch):
    sql_logger = repository.logging.getLogger('sqlalchemy.engine')
    original_handlers = list(sql_logger.handlers)
    monkeypatch.setattr(repository, '_engine', None)
    monkeypatch.setattr(repository, '_config', None)
    monkeypatch.setattr(repository, '_first_run', False)
    monkeypatch.setattr(repository, '_repo_started', False)
    yield
    if repository._engine is not None:
        repository._engine.dispose()
    for handler in sql_logger.handlers:
        if handler not in original_handlers:
            sql_logger.removeHandler(handler)
            handler.close()


def test_start_repo_rejects_corrupt_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_file = tmp_path / 'corrupt.db'
    db_file.write_text('this is not SQLite', encoding='utf-8')
    config = repository_config(db_file, tmp_path / 'database.log')
    monkeypatch.setattr(repository, 'get_config', lambda: config)

    with pytest.raises(ArcException) as exc_info:
        repository.start_repo()

    assert exc_info.value.code is ArcException.Code.INVALID_DATABASE
    assert repository._repo_started is False


def test_start_repo_reports_inaccessible_database_folder(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    db_file = tmp_path / 'blocked' / 'database.db'
    config = repository_config(db_file, tmp_path / 'database.log')
    real_mkdir = Path.mkdir

    def deny_database_folder(path: Path, *args, **kwargs):
        if path == db_file.parent:
            raise PermissionError('access denied')
        return real_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'mkdir', deny_database_folder)
    monkeypatch.setattr(repository, 'get_config', lambda: config)

    with pytest.raises(ArcException) as exc_info:
        repository.start_repo()

    assert exc_info.value.code is ArcException.Code.INACCESSIBLE_FOLDER
    assert repository._repo_started is False


def test_start_repo_rejects_incompatible_unversioned_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    db_file = tmp_path / 'existing.db'
    with sqlite3.connect(db_file) as connection:
        connection.execute('CREATE TABLE existing (id INTEGER PRIMARY KEY)')
    config = repository_config(db_file, tmp_path / 'database.log')
    monkeypatch.setattr(repository, 'get_config', lambda: config)

    with pytest.raises(ArcException) as exc_info:
        repository.start_repo()

    assert exc_info.value.code is ArcException.Code.INVALID_DATABASE
    assert repository._repo_started is False


def test_start_repo_adopts_compatible_unversioned_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    db_file = tmp_path / 'existing.db'
    engine = repository.create_engine(f'sqlite:///{db_file}')
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Tag(tag='preserved'))
        session.commit()
    engine.dispose()
    config = repository_config(db_file, tmp_path / 'database.log')
    monkeypatch.setattr(repository, 'get_config', lambda: config)

    repository.start_repo()

    with Session(repository._engine) as session:
        assert session.get(Tag, 'preserved') is not None
    with repository._engine.connect() as connection:
        assert MigrationContext.configure(connection).get_current_revision() == 'a7c4f02d91e8'
    assert repository._first_run is False


def test_start_repo_creates_parent_and_new_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_file = tmp_path / 'new' / 'database.db'
    config = repository_config(db_file, tmp_path / 'database.log')
    scanner = SimpleNamespace(start=lambda _rehash: None)
    monkeypatch.setattr(repository, 'get_config', lambda: config)
    monkeypatch.setattr(repository, 'create_scanner', lambda: scanner)

    repository.start_repo()

    assert db_file.is_file()
    assert repository._repo_started is True
    assert repository._first_run is True
    with repository._engine.connect() as connection:
        assert MigrationContext.configure(connection).get_current_revision() == 'a7c4f02d91e8'


def test_start_repo_does_not_scan_in_read_only_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_file = tmp_path / 'readonly' / 'database.db'
    config = repository_config(db_file, tmp_path / 'database.log')
    config.read_only = True
    monkeypatch.setattr(repository, 'get_config', lambda: config)

    def unexpected_scanner():
        pytest.fail('read-only startup must not create a scanner')

    monkeypatch.setattr(repository, 'create_scanner', unexpected_scanner)

    repository.start_repo()

    assert repository.repo_status()['read_only'] is True
    assert repository._repo_started is True


def test_schema_update_is_idempotent(tmp_path: Path):
    db_file = tmp_path / 'database.db'
    engine = repository.create_engine(f'sqlite:///{db_file}')

    repository.update_database_schema(engine)
    repository.update_database_schema(engine)

    with engine.connect() as connection:
        assert MigrationContext.configure(connection).get_current_revision() == 'a7c4f02d91e8'
    engine.dispose()


def test_migration_failure_leaves_repository_unstarted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    config = repository_config(tmp_path / 'database.db', tmp_path / 'database.log')
    monkeypatch.setattr(repository, 'get_config', lambda: config)

    def fail_migration(_engine):
        raise RuntimeError('migration failed')

    monkeypatch.setattr(repository, 'update_database_schema', fail_migration)

    with pytest.raises(RuntimeError, match='migration failed'):
        repository.start_repo()

    assert repository._repo_started is False
    assert repository._engine is None
