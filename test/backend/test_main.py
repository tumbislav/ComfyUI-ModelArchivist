# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: test_main.py
# purpose: Tests for backend startup error handling
# ---------------------------------------------------------------------------

from types import SimpleNamespace

import pytest

import backend.__main__ as backend_main
from backend.config import ConfigError, ConfigException


def test_main_handles_configuration_failure(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture):
    def fail_config(_config_file):
        raise ConfigException(ConfigError.CONFIG_NOT_FOUND, 'missing.toml')

    start_repo_called = False

    def record_start_repo():
        nonlocal start_repo_called
        start_repo_called = True

    monkeypatch.setattr(backend_main, 'load_config', fail_config)
    monkeypatch.setattr(backend_main, 'start_repo', record_start_repo)

    result = backend_main.main([])

    assert result == 1
    assert 'Backend initialization failed' in capsys.readouterr().err
    assert start_repo_called is False


def test_main_handles_repository_failure(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture):
    config = SimpleNamespace(log_config={'version': 1, 'disable_existing_loggers': False})

    monkeypatch.setattr(backend_main, 'load_config', lambda _config_file: config)

    def fail_repo():
        raise RuntimeError('database unavailable')

    monkeypatch.setattr(backend_main, 'start_repo', fail_repo)

    result = backend_main.main([])

    assert result == 1
    assert 'database unavailable' in capsys.readouterr().err
