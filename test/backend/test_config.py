# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: test_config.py
# purpose: Tests for bootstrap and runtime configuration
# ---------------------------------------------------------------------------

from pathlib import Path

import pytest

from backend.config import (ConfigError, ConfigException, Configuration, DatabaseConfig,
                            LoggingConfig, WebConfig, load_config)


def make_configuration(tmp_path: Path, mode: str = 'standalone') -> Configuration:
    config = Configuration(
        database=DatabaseConfig(database_file=str(tmp_path / 'database.db')),
        web=WebConfig(host='127.0.0.1', port=5173,
                      static_html=str(tmp_path / 'html')),
        logging=LoggingConfig(level='INFO', sql_level='WARNING',
                              file=str(tmp_path / 'archivist.log')))
    config.initialize(tmp_path, tmp_path / 'config.toml', mode)
    return config


def test_load_config_reports_missing_file(tmp_path: Path):
    config_file = tmp_path / 'missing.toml'
    with pytest.raises(ConfigException) as exc_info:
        load_config(config_file)
    assert exc_info.value.code is ConfigError.CONFIG_NOT_FOUND


def test_load_config_reports_malformed_toml(tmp_path: Path):
    config_file = tmp_path / 'malformed.toml'
    config_file.write_text('[database\nfile = "unterminated', encoding='utf-8')
    with pytest.raises(ConfigException) as exc_info:
        load_config(config_file)
    assert exc_info.value.code is ConfigError.INVALID_CONFIG


def test_load_config_reports_missing_required_sections(tmp_path: Path):
    config_file = tmp_path / 'incomplete.toml'
    config_file.write_text('[database]\ndatabase_file = "db.sqlite"', encoding='utf-8')
    with pytest.raises(ConfigException) as exc_info:
        load_config(config_file)
    assert exc_info.value.code is ConfigError.INVALID_CONFIG


def test_load_config_reports_invalid_bootstrap_value_type(tmp_path: Path):
    config_file = tmp_path / 'invalid-value.toml'
    config_file.write_text('''
[database]
database_file = "database.db"
[web]
host = "127.0.0.1"
port = "not-a-port"
static_html = "frontend/build"
[logging]
level = "INFO"
sql_level = "WARNING"
file = "archivist.log"
''', encoding='utf-8')
    with pytest.raises(ConfigException) as exc_info:
        load_config(config_file)
    assert exc_info.value.code is ConfigError.INVALID_CONFIG


def test_load_config_reports_unreadable_file(tmp_path: Path,
                                             monkeypatch: pytest.MonkeyPatch):
    config_file = tmp_path / 'unreadable.toml'
    config_file.touch()
    monkeypatch.setattr(Path, 'read_text',
                        lambda *_args, **_kwargs: (_ for _ in ()).throw(
                            PermissionError('access denied')))
    with pytest.raises(ConfigException) as exc_info:
        load_config(config_file)
    assert exc_info.value.code is ConfigError.CONFIG_UNREADABLE


def test_runtime_path_failure_sets_dimension_flag(tmp_path: Path,
                                                  monkeypatch: pytest.MonkeyPatch):
    config = make_configuration(tmp_path)
    working = tmp_path / 'working'
    archive = tmp_path / 'archive'
    real_iterdir = Path.iterdir

    def deny_archive(path: Path):
        if path == archive:
            raise PermissionError('access denied')
        return real_iterdir(path)

    monkeypatch.setattr(Path, 'iterdir', deny_archive)
    config.add_model_locations('checkpoints', working, archive)

    assert config.model_working_accessible is True
    assert config.model_archive_accessible is False
    assert config.read_only is True


def test_standalone_rejects_multiple_locations_for_one_type(tmp_path: Path):
    config = make_configuration(tmp_path)
    config.add_model_locations('checkpoints', tmp_path / 'working-1',
                               tmp_path / 'archive-1')
    with pytest.raises(ConfigException) as exc_info:
        config.add_model_locations('checkpoints', tmp_path / 'working-2',
                                   tmp_path / 'archive-2')
    assert exc_info.value.code is ConfigError.MULTIPLE_PATHS_PER_TYPE


def test_comfy_mode_allows_multiple_locations_for_one_type(tmp_path: Path):
    config = make_configuration(tmp_path, 'comfyui')
    config.add_model_locations('checkpoints', tmp_path / 'working-1',
                               tmp_path / 'archive-1')
    config.add_model_locations('checkpoints', tmp_path / 'working-2',
                               tmp_path / 'archive-2')
    assert len(config.model_folders['checkpoints']) == 2
