# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: test_config.py
# purpose: Tests for application configuration loading
# ---------------------------------------------------------------------------

from pathlib import Path

import pytest

from backend.config import ConfigError, ConfigException, load_config


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
