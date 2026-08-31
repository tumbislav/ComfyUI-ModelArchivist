# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: test_model_scanner.py
# purpose: Tests for normalized model component-set scanning
# ---------------------------------------------------------------------------

import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

import backend.files.scanner as scanner_module
from backend.files.scanner import Scanner


def test_archive_absence_does_not_create_empty_component_set(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    working = tmp_path / 'working' / 'checkpoints'
    archive = tmp_path / 'archive' / 'checkpoints'
    model_dir = working / 'nested'
    model_dir.mkdir(parents=True)
    archive.mkdir(parents=True)
    (model_dir / 'model.safetensors').write_bytes(b'model weights')
    saved = []
    monkeypatch.setattr(scanner_module.repo, 'save_scanned_model',
                        lambda model, _tags: saved.append(model))
    scanner = Scanner(start_time=datetime.datetime.now(tz=datetime.timezone.utc))
    scanner.config = SimpleNamespace(model_extensions=['.safetensors'])
    scanner.barrier = SimpleNamespace(wait=lambda: None)

    scanner.find_models('checkpoints', working, archive, False)

    assert len(saved) == 1
    model = saved[0]
    assert [component_set.where for component_set in model.component_sets] == ['w']
    assert model.component_sets[0].primary_dir == working.as_posix()
    assert {component.relative_path for component in model.component_sets[0].components} == {
        'nested'
    }
