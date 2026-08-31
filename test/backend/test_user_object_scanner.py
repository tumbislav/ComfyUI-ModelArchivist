# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: test_user_object_scanner.py
# purpose: Tests for user-defined object filesystem discovery
# ---------------------------------------------------------------------------

import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

import backend.files.scanner as scanner_module
from backend.files.scanner import Scanner
from backend.repository.tables import DeploymentStatus, UserObjectError


def run_scan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, **changes):
    working = tmp_path / 'working'
    archive = tmp_path / 'archive'
    working.mkdir()
    archive.mkdir()
    definition = {
        'id': 'type-id', 'object_class': 'file', 'extensions': ['txt'],
        'working_dir': str(working), 'archive_dir': str(archive),
        'size_limit': 1024,
    }
    definition.update(changes)
    saved = []
    retained = []
    monkeypatch.setattr(scanner_module.repo, 'save_scanned_user_object', saved.append)
    monkeypatch.setattr(
        scanner_module.repo, 'retain_oversized_user_object',
        lambda type_id, relative_path, touched, size:
            retained.append((type_id, relative_path, size)) or False)
    monkeypatch.setattr(scanner_module.repo, 'retain_unreadable_user_type_objects',
                        lambda _type_id, _touched: None)
    scanner = Scanner(start_time=datetime.datetime.now(tz=datetime.timezone.utc))
    scanner.barrier = SimpleNamespace(wait=lambda: None)
    scanner.find_user_objects([definition])
    return working, archive, saved, retained, scanner


def test_file_types_recurse_and_match_compound_extensions(tmp_path, monkeypatch):
    working, _archive, saved, _retained, scanner = run_scan(
        tmp_path, monkeypatch, extensions=['tar.gz'])
    (working / 'nested').mkdir()
    (working / 'nested' / 'dataset.TAR.GZ').write_bytes(b'data')
    (working / 'nested' / 'ignored.gz').write_bytes(b'other')

    scanner.find_user_objects([{
        'id': 'type-id', 'object_class': 'file', 'extensions': ['tar.gz'],
        'working_dir': str(working), 'archive_dir': str(tmp_path / 'archive'),
        'size_limit': 1024,
    }])

    assert len(saved) == 1
    assert saved[0].relative_path == 'nested/dataset.TAR.GZ'
    assert saved[0].deployment == DeploymentStatus.WORKING.value


def test_folder_type_discovers_only_immediate_children_as_objects(tmp_path, monkeypatch):
    working, archive, saved, _retained, scanner = run_scan(
        tmp_path, monkeypatch, object_class='folder', extensions=[])
    (working / 'dataset' / 'images').mkdir(parents=True)
    (working / 'dataset' / 'images' / 'one.bin').write_bytes(b'123')

    scanner.find_user_objects([{
        'id': 'type-id', 'object_class': 'folder', 'extensions': [],
        'working_dir': str(working), 'archive_dir': str(archive),
        'size_limit': 1024,
    }])

    assert [item.relative_path for item in saved] == ['dataset']
    assert {entry.relative_path for entry in saved[0].sets[0].entries} == {
        'dataset', 'dataset/images', 'dataset/images/one.bin'}
    assert saved[0].size == 3


def test_different_snapshots_are_a_location_mismatch(tmp_path, monkeypatch):
    working, archive, saved, _retained, scanner = run_scan(tmp_path, monkeypatch)
    (working / 'object.txt').write_bytes(b'working')
    (archive / 'object.txt').write_bytes(b'archived copy')

    scanner.find_user_objects([{
        'id': 'type-id', 'object_class': 'file', 'extensions': ['txt'],
        'working_dir': str(working), 'archive_dir': str(archive),
        'size_limit': 1024,
    }])

    assert saved[0].deployment == DeploymentStatus.MISMATCH.value
    assert saved[0].errors == [UserObjectError.LOCATION_MISMATCH.value]


def test_oversized_object_is_not_saved_and_is_offered_for_retention(
        tmp_path, monkeypatch):
    working, archive, saved, retained, scanner = run_scan(
        tmp_path, monkeypatch, size_limit=3)
    (working / 'large.txt').write_bytes(b'1234')
    (archive / 'large.txt').write_bytes(b'1')

    scanner.find_user_objects([{
        'id': 'type-id', 'object_class': 'file', 'extensions': ['txt'],
        'working_dir': str(working), 'archive_dir': str(archive),
        'size_limit': 3,
    }])

    assert saved == []
    assert retained == [('type-id', 'large.txt', 4)]
