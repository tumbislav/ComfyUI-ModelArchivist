# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: test_repository_startup.py
# purpose: Tests for database-backed repository startup
# ---------------------------------------------------------------------------

from pathlib import Path
from types import SimpleNamespace
import tomllib

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlmodel import SQLModel, Session, create_engine, select

from backend.config import Configuration, DatabaseConfig, LoggingConfig, WebConfig
from backend.exception import ArcException
from backend.environment import ComfyEnvironmentProvider
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
        assert MigrationContext.configure(connection).get_current_revision() == '000000000002'


def test_comfy_model_types_are_created_only_when_user_saves_mappings(tmp_path, monkeypatch):
    models = tmp_path / 'models'
    checkpoints = models / 'checkpoints'
    checkpoints.mkdir(parents=True)
    loras = models / 'loras'
    loras.mkdir()
    provider = ComfyEnvironmentProvider(SimpleNamespace(
        models_dir=str(models),
        folder_names_and_paths={
            'checkpoints': ([str(checkpoints)], {'.safetensors'}),
            'loras': ([str(loras)], {'.safetensors'}),
        },
    ))
    config = repository_config(tmp_path / 'database.db', tmp_path / 'database.log')
    monkeypatch.setattr(repository, 'get_config', lambda: config)
    monkeypatch.setattr(repository, 'get_environment_provider', lambda: provider)
    repository.start_repo()

    assert repository.get_repository_configuration()['model_types'] == []
    with Session(repository._engine) as session:
        assert session.exec(select(ModelLocationSetting)).all() == []

    candidates = repository.propose_model_mappings(
        str(models), str(tmp_path / 'archive'), ['.safetensors'])
    assert {item['name'] for item in candidates} == {'checkpoints', 'loras'}
    assert repository.get_repository_configuration()['model_types'] == []
    selected = next(item for item in candidates if item['name'] == 'checkpoints')
    selected['display_name'] = 'My checkpoints'
    result = repository.update_model_configuration({'model_types': [selected]})

    assert [item['name'] for item in result['model_types']] == ['checkpoints']
    assert result['model_types'][0]['display_name'] == 'My checkpoints'
    assert config.model_folders['checkpoints'] == {
        (checkpoints, tmp_path / 'archive' / 'checkpoints')}
    repository.load_repository_configuration(config)
    assert [item['name'] for item in repository.get_repository_configuration()['model_types']] == [
        'checkpoints']


def test_sql_log_handler_preserves_unicode(tmp_path, monkeypatch):
    config = repository_config(tmp_path / 'database.db', tmp_path / 'database.log')
    monkeypatch.setattr(repository, 'get_config', lambda: config)
    sql_logger = repository.logging.getLogger('sqlalchemy.engine')
    previous_handlers = list(sql_logger.handlers)

    repository.start_repo()

    handler, = [item for item in sql_logger.handlers if item not in previous_handlers]
    message = 'Model \u8272\u60c5\u5927\u5e2b \U0001f7e1 invalid: \ud800'
    handler.handle(repository.logging.LogRecord(
        'sqlalchemy.engine', repository.logging.WARNING, __file__, 0, message, (), None))
    handler.flush()
    assert 'Model \u8272\u60c5\u5927\u5e2b \U0001f7e1 invalid: \\ud800' in Path(
        config.log_file).read_text(encoding='utf-8')


def test_configured_database_loads_paths_without_starting_scan(tmp_path, monkeypatch):
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
    monkeypatch.setattr(repository, 'get_config', lambda: config)
    monkeypatch.setattr(repository, 'create_scanner',
                        lambda: pytest.fail('startup must wait for a browser scan request'))
    monkeypatch.setattr(repository, 'get_scanner', lambda: None)

    repository.start_repo()

    assert config.model_folders['checkpoints'] == {(working, archive)}
    assert repository.repo_status()['ready'] is True


def test_schema_update_is_idempotent(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path / "database.db"}')
    repository.update_database_schema(engine)
    repository.update_database_schema(engine)
    with engine.connect() as connection:
        assert MigrationContext.configure(connection).get_current_revision() == '000000000002'
    engine.dispose()


def test_filesystem_setup_saves_once_and_remains_locked_after_reload(tmp_path, monkeypatch):
    config = repository_config(tmp_path / 'database.db', tmp_path / 'database.log')
    config.cfg_file.write_text(
        '# Keep bootstrap comment\n[database]\ndatabase_file="unchanged.db"\n'
        '[filesystem]\nworking_roots=[]\narchive_roots=[]\nexclusions=[]\n'
        '[other]\nvalue="keep"\n', encoding='utf-8')
    monkeypatch.setattr(repository, 'get_config', lambda: config)
    import backend.filesystem_policy as fs
    monkeypatch.setattr(fs, '_policy', config.filesystem)
    repository.start_repo()
    assert repository.filesystem_setup_available()
    before = config.cfg_file.read_bytes()
    with pytest.raises(fs.FilesystemPolicyError):
        repository.initialize_filesystem_roots(['relative'], [str(tmp_path / 'archive')])
    assert config.cfg_file.read_bytes() == before
    assert repository.filesystem_setup_available()

    working = str(tmp_path / 'models')
    archive = str(tmp_path / 'external' / 'archive')
    result = repository.initialize_filesystem_roots([working], [archive])
    assert result['filesystem_setup_available'] is False
    assert fs.checked_path(Path(archive) / 'checkpoints', 'archive') == Path(archive) / 'checkpoints'
    contents = config.cfg_file.read_text(encoding='utf-8')
    assert contents.startswith('# Keep bootstrap comment')
    values = tomllib.loads(contents)
    assert values['database'] == {'database_file': 'unchanged.db'}
    assert values['other'] == {'value': 'keep'}
    assert values['filesystem']['working_roots'] == [working]
    assert values['filesystem']['archive_roots'] == [archive]
    repository.load_repository_configuration(config)
    with pytest.raises(PermissionError):
        repository.initialize_filesystem_roots([], [])
    assert config.cfg_file.read_text(encoding='utf-8') == contents


def test_filesystem_setup_migration_locks_existing_installations(tmp_path):
    from alembic import command
    from backend.repository.migrations import alembic_config
    engine = create_engine(f'sqlite:///{tmp_path / "existing.db"}')
    try:
        with engine.begin() as connection:
            command.upgrade(alembic_config(connection), '000000000001')
            connection.exec_driver_sql(
                'INSERT INTO applicationsettings '
                '(id, setup_complete, update_json_metadata, ignore_unknown_types, always_recalc_hashes) '
                'VALUES (1, 0, 1, 0, 0)')
        repository.update_database_schema(engine)
        with Session(engine) as session:
            assert session.get(ApplicationSettings, 1).filesystem_setup_complete is True
    finally:
        engine.dispose()


def test_baseline_matches_current_metadata(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path / "database.db"}')
    repository.update_database_schema(engine)
    with engine.connect() as connection:
        differences = compare_metadata(MigrationContext.configure(connection), SQLModel.metadata)
    engine.dispose()

    assert differences == []


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


def test_standalone_bulk_mapping_discovers_only_model_directories(tmp_path, monkeypatch):
    config = repository_config(tmp_path / 'database.db', tmp_path / 'database.log')
    monkeypatch.setattr(repository, 'get_config', lambda: config)
    repository.start_repo()
    working = tmp_path / 'models'
    (working / 'checkpoints' / 'nested').mkdir(parents=True)
    (working / 'checkpoints' / 'nested' / 'model.SAFETENSORS').write_bytes(b'model')
    (working / 'recipes').mkdir()
    (working / 'recipes' / 'recipe.json').write_text('{}', encoding='utf-8')

    result = repository.propose_model_mappings(
        str(working), str(tmp_path / 'archive'), ['.safetensors', '.ckpt'])

    assert result == [{
        'name': 'checkpoints', 'display_name': 'checkpoints',
        'extensions': ['.safetensors'],
        'locations': [{
            'working_dir': str(working / 'checkpoints'),
            'archive_dir': str(tmp_path / 'archive' / 'checkpoints')}],
    }]


def test_standalone_bulk_mapping_stops_after_finding_requested_extensions(tmp_path, monkeypatch):
    config = repository_config(tmp_path / 'database.db', tmp_path / 'database.log')
    monkeypatch.setattr(repository, 'get_config', lambda: config)
    repository.start_repo()
    working = tmp_path / 'models'
    model_dir = working / 'checkpoints'
    model_dir.mkdir(parents=True)
    model_file = model_dir / 'model.safetensors'
    model_file.write_bytes(b'model')

    def entries(*_args, **_kwargs):
        yield model_file
        pytest.fail('mapping discovery continued after finding every requested extension')

    monkeypatch.setattr(repository, 'safe_tree', entries)
    result = repository.propose_model_mappings(
        str(working), str(tmp_path / 'archive'), ['.safetensors'])

    assert result[0]['extensions'] == ['.safetensors']


def test_model_extension_allowlist_persists(tmp_path, monkeypatch):
    config = repository_config(tmp_path / 'database.db', tmp_path / 'database.log')
    monkeypatch.setattr(repository, 'get_config', lambda: config)
    repository.start_repo()
    assert '.safetensors' in repository.get_repository_configuration()['model_extensions']
    result = repository.update_model_extensions(['safetensors'])
    assert result['model_extensions'] == ['.safetensors']
    assert '.ckpt' in result['available_model_extensions']
    repository.load_repository_configuration(config)
    assert config.model_extension_allowlist == ['.safetensors']
    with pytest.raises(ValueError):
        repository.update_model_extensions(['.invalid'])
    assert repository.get_repository_configuration()['model_extensions'] == ['.safetensors']
    repository.update_model_extensions([])
    assert config.model_extension_allowlist == []
