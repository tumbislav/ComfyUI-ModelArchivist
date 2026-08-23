# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: test_config.py
# purpose: Tests for application configuration loading
# ---------------------------------------------------------------------------

from pathlib import Path

import pytest

from backend.config import (
    ConfigError,
    ConfigException,
    Configuration,
    DatabaseConfig,
    LoggingConfig,
    ModelsConfig,
    OptionsConfig,
    PathsConfig,
    WebConfig,
    WorkflowConfig,
    WorkflowFolders,
    load_config,
)


def make_configuration(tmp_path: Path) -> tuple[Configuration, dict[str, Path]]:
    comfy_root = tmp_path / 'comfy'
    model_working = comfy_root / 'models'
    model_archive = tmp_path / 'archive' / 'models'
    workflow_working = tmp_path / 'user' / 'workflows'
    workflow_archive = tmp_path / 'archive' / 'workflows'
    (model_working / 'checkpoints').mkdir(parents=True)
    model_archive.mkdir(parents=True)

    config = Configuration(
        paths=PathsConfig(
            comfy=str(comfy_root),
            archive=str(tmp_path / 'archive'),
            user=str(tmp_path / 'user'),
            database=str(tmp_path / 'database'),
            html=str(tmp_path / 'html'),
        ),
        database=DatabaseConfig(database_file='database.db', dbms_prefix='sqlite:///'),
        models=ModelsConfig(
            working=str(model_working),
            archive=str(model_archive),
            extras=[],
            types={'checkpoints': 'Checkpoint'},
            extensions=['.safetensors'],
        ),
        workflows=WorkflowConfig(
            folders=[WorkflowFolders(working=str(workflow_working), archive=str(workflow_archive))]
        ),
        web=WebConfig(host='127.0.0.1', port=5173, static_html='html'),
        options=OptionsConfig(
            update_json_metadata=True,
            ignore_unknown_types=False,
            always_recalc_hashes=False,
        ),
        logging=LoggingConfig(level='INFO', sql_level='WARNING', file='archivist.log'),
    )
    folders = {
        'model_working_accessible': model_working / 'checkpoints',
        'model_archive_accessible': model_archive / 'checkpoints',
        'workflow_working_accessible': workflow_working,
        'workflow_archive_accessible': workflow_archive,
    }
    return config, folders


def test_load_config_reports_missing_file(tmp_path: Path):
    config_file = tmp_path / 'missing.toml'

    with pytest.raises(ConfigException) as exc_info:
        load_config(config_file)

    assert exc_info.value.code is ConfigError.CONFIG_NOT_FOUND
    assert str(config_file) in exc_info.value.message


def test_load_config_reports_malformed_toml(tmp_path: Path):
    config_file = tmp_path / 'malformed.toml'
    config_file.write_text('[paths\ncomfy = "unterminated', encoding='utf-8')

    with pytest.raises(ConfigException) as exc_info:
        load_config(config_file)

    assert exc_info.value.code is ConfigError.INVALID_CONFIG
    assert str(config_file) in exc_info.value.message


def test_load_config_reports_missing_required_sections(tmp_path: Path):
    config_file = tmp_path / 'incomplete.toml'
    config_file.write_text('[paths]\ncomfy = "comfy"', encoding='utf-8')

    with pytest.raises(ConfigException) as exc_info:
        load_config(config_file)

    assert exc_info.value.code is ConfigError.INVALID_CONFIG
    assert 'missing sections' in exc_info.value.message


def test_load_config_reports_unreadable_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config_file = tmp_path / 'unreadable.toml'
    config_file.touch()

    def deny_read(_path: Path, *args, **kwargs):
        raise PermissionError('access denied')

    monkeypatch.setattr(Path, 'read_text', deny_read)

    with pytest.raises(ConfigException) as exc_info:
        load_config(config_file)

    assert exc_info.value.code is ConfigError.CONFIG_UNREADABLE
    assert str(config_file) in exc_info.value.message


@pytest.mark.parametrize(
    'inaccessible_flag',
    [
        'model_working_accessible',
        'model_archive_accessible',
        'workflow_working_accessible',
        'workflow_archive_accessible',
    ],
)
def test_resolve_paths_flags_inaccessible_folders(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    inaccessible_flag: str,
):
    config, folders = make_configuration(tmp_path)
    inaccessible_folder = folders[inaccessible_flag]
    real_iterdir = Path.iterdir

    def deny_selected_folder(path: Path):
        if path == inaccessible_folder:
            raise PermissionError('access denied')
        return real_iterdir(path)

    monkeypatch.setattr(Path, 'iterdir', deny_selected_folder)

    config.resolve_paths(tmp_path, tmp_path / 'config.toml')

    for flag in folders:
        assert getattr(config, flag) is (flag != inaccessible_flag)
    assert config.read_only is True
