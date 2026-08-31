# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: test_repository_startup.py
# purpose: Tests for database-backed repository startup
# ---------------------------------------------------------------------------

from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from sqlmodel import Session, create_engine

from backend.config import Configuration, DatabaseConfig, LoggingConfig, WebConfig
from backend.exception import ArcException
import backend.repository.repository as repository
from backend.repository.tables import (ApplicationSettings, ModelLocationSetting,
                                       ModelTypeSetting)


def repository_config(db_file: Path, log_file: Path) -> Configuration:
    config = Configuration(
        database=DatabaseConfig(database_file=str(db_file)),
        web=WebConfig(host='127.0.0.1', port=5173,
                      static_html=str(db_file.parent / 'html')),
        logging=LoggingConfig(level='INFO', sql_level='WARNING', file=str(log_file)))
    app_root = db_file.parent if db_file.parent.is_dir() else db_file.parent.parent
    config.initialize(app_root, app_root / 'config.toml')
    return config


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


def test_start_repo_rejects_corrupt_database(tmp_path, monkeypatch):
    db_file = tmp_path / 'corrupt.db'
    db_file.write_text('not SQLite', encoding='utf-8')
    monkeypatch.setattr(repository, 'get_config',
                        lambda: repository_config(db_file, tmp_path / 'log'))
    with pytest.raises(ArcException) as exc_info:
        repository.start_repo()
    assert exc_info.value.code is ArcException.Code.INVALID_DATABASE


def test_start_repo_reports_inaccessible_database_folder(tmp_path, monkeypatch):
    db_file = tmp_path / 'blocked' / 'database.db'
    config = repository_config(db_file, tmp_path / 'log')
    real_mkdir = Path.mkdir

    def deny(path: Path, *args, **kwargs):
        if path == db_file.parent:
            raise PermissionError('access denied')
        return real_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'mkdir', deny)
    monkeypatch.setattr(repository, 'get_config', lambda: config)
    with pytest.raises(ArcException) as exc_info:
        repository.start_repo()
    assert exc_info.value.code is ArcException.Code.INACCESSIBLE_FOLDER


def test_new_database_starts_in_setup_mode_without_scan(tmp_path, monkeypatch):
    db_file = tmp_path / 'new' / 'database.db'
    config = repository_config(db_file, tmp_path / 'database.log')
    monkeypatch.setattr(repository, 'get_config', lambda: config)
    monkeypatch.setattr(repository, 'create_scanner',
                        lambda: pytest.fail('setup mode must not scan'))

    repository.start_repo()

    assert repository.repo_status()['setup_required'] is True
    assert repository.repo_status()['ready'] is True
    with repository._engine.connect() as connection:
        assert MigrationContext.configure(connection).get_current_revision() == '000000000001'


def test_configured_database_loads_paths_and_starts_scan(tmp_path, monkeypatch):
    db_file = tmp_path / 'database.db'
    engine = create_engine(f'sqlite:///{db_file}')
    repository.update_database_schema(engine)
    working = tmp_path / 'working'
    archive = tmp_path / 'archive'
    with Session(engine) as session:
        session.add(ApplicationSettings(setup_complete=True))
        session.add(ModelTypeSetting(name='checkpoints', display_name='Checkpoint',
                                     extensions=['.safetensors']))
        session.add(ModelLocationSetting(model_type='checkpoints', working_dir=str(working),
                                         archive_dir=str(archive)))
        session.commit()
    engine.dispose()
    config = repository_config(db_file, tmp_path / 'database.log')
    started = []

    class ScannerStub:
        def start(self, rehash):
            started.append(rehash)

    monkeypatch.setattr(repository, 'get_config', lambda: config)
    monkeypatch.setattr(repository, 'create_scanner', ScannerStub)

    repository.start_repo()

    assert config.model_folders['checkpoints'] == {(working, archive)}
    assert started == [False]


def test_schema_update_is_idempotent(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path / "database.db"}')
    repository.update_database_schema(engine)
    repository.update_database_schema(engine)
    with engine.connect() as connection:
        assert MigrationContext.configure(connection).get_current_revision() == '000000000001'
    engine.dispose()


def test_repository_configuration_persists_standalone_locations(tmp_path, monkeypatch):
    db_file = tmp_path / 'database.db'
    config = repository_config(db_file, tmp_path / 'database.log')
    monkeypatch.setattr(repository, 'get_config', lambda: config)
    repository.start_repo()

    result = repository.update_repository_configuration({
        'options': {'update_json_metadata': False},
        'model_types': [{
            'name': 'checkpoints', 'display_name': 'Checkpoint',
            'extensions': ['safetensors'],
            'locations': [{'working_dir': str(tmp_path / 'models'),
                           'archive_dir': str(tmp_path / 'model-archive')}],
        }],
        'workflow_locations': [{'working_dir': str(tmp_path / 'workflows'),
                                'archive_dir': str(tmp_path / 'workflow-archive')}],
    })

    assert result['setup_complete'] is True
    assert result['options']['update_json_metadata'] is False
    assert config.setup_required is False
    assert config.model_extensions_by_type['checkpoints'] == ['.safetensors']

    model_update = repository.update_model_configuration({'model_types': [{
        'name': 'checkpoints', 'display_name': 'Checkpoints',
        'extensions': ['.ckpt'],
        'locations': [{'working_dir': str(tmp_path / 'models'),
                       'archive_dir': str(tmp_path / 'model-archive')}],
    }]})
    assert model_update['workflow_locations'][0]['working_dir'] == str(
        (tmp_path / 'workflows').absolute())
    assert model_update['model_types'][0]['display_name'] == 'Checkpoints'


def test_repository_configuration_rejects_multiple_standalone_locations(
        tmp_path, monkeypatch):
    db_file = tmp_path / 'database.db'
    config = repository_config(db_file, tmp_path / 'database.log')
    monkeypatch.setattr(repository, 'get_config', lambda: config)
    repository.start_repo()

    with pytest.raises(ValueError, match='one working/archive pair'):
        repository.update_repository_configuration({
            'model_types': [{
                'name': 'checkpoints', 'display_name': 'Checkpoint',
                'extensions': ['.safetensors'],
                'locations': [
                    {'working_dir': str(tmp_path / 'models-1'),
                     'archive_dir': str(tmp_path / 'archive-1')},
                    {'working_dir': str(tmp_path / 'models-2'),
                     'archive_dir': str(tmp_path / 'archive-2')},
                ],
            }],
            'workflow_locations': [],
        })
