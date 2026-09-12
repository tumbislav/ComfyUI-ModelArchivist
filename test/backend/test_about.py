# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: test_about.py
# purpose: About information reflects project version and operating mode
# ---------------------------------------------------------------------------

from pathlib import Path
from types import SimpleNamespace
import tomllib

import pytest

from backend.server.routers import admin


@pytest.mark.parametrize('mode', ['standalone', 'comfyui'])
def test_about_uses_project_version_and_runtime_mode(monkeypatch, mode):
    monkeypatch.setattr(admin, 'get_config', lambda: SimpleNamespace(mode=mode))
    with (Path(__file__).resolve().parents[2] / 'pyproject.toml').open('rb') as source:
        version = tomllib.load(source)['project']['version']

    assert admin.about() == {'version': version, 'mode': mode}
