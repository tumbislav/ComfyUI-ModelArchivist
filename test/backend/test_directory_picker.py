# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: test_directory_picker.py
# purpose: Tests for host-side directory selection
# ---------------------------------------------------------------------------

import base64
from pathlib import Path
from types import SimpleNamespace

import backend.directory_picker as picker


def test_windows_picker_is_not_restricted_to_initial_directory(monkeypatch):
    captured = {}

    def run(arguments, **kwargs):
        captured['arguments'] = arguments
        captured['kwargs'] = kwargs
        return SimpleNamespace(returncode=0, stdout='C:\\模型\\🟡', stderr='')

    monkeypatch.setattr(picker.sys, 'platform', 'win32')
    monkeypatch.setattr(picker.subprocess, 'run', run)

    selected = picker.pick_directory('C:\\application\\models')

    script = base64.b64decode(captured['arguments'][-1]).decode('utf-16le')
    assert "BrowseForFolder(0, 'Select folder', 0)" in script
    assert 'ARCHIVIST_PICKER_INITIAL' not in script
    assert selected == str(Path('C:\\模型\\🟡').resolve(strict=False))
    assert captured['kwargs']['encoding'] == 'utf-8'


def test_windows_picker_cancellation_returns_none(monkeypatch):
    monkeypatch.setattr(picker.sys, 'platform', 'win32')
    monkeypatch.setattr(
        picker.subprocess, 'run',
        lambda *_args, **_kwargs:
            SimpleNamespace(returncode=0, stdout='', stderr=''))

    assert picker.pick_directory('C:\\application\\models') is None
