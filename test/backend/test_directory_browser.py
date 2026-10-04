# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: test_directory_browser.py
# purpose: Non-recursive directory browsing and policy boundary regressions
# ---------------------------------------------------------------------------

import os
from pathlib import Path

import pytest

from backend import directory_browser as browser, filesystem_policy as fs


@pytest.fixture
def tree(tmp_path, monkeypatch):
    working, archive = tmp_path / 'working', tmp_path / 'archive'
    working.mkdir()
    archive.mkdir()
    (working / 'B').mkdir()
    (working / 'a').mkdir()
    (working / 'a' / 'deeper').mkdir()
    (working / 'private').mkdir()
    (working / 'model.bin').write_bytes(b'model')
    monkeypatch.setattr(fs, '_policy', fs.FilesystemPolicy(
        (working,), (archive,), (working / 'private',)))
    return working, archive


def test_roles_roots_and_no_initial_enumeration(tree, monkeypatch):
    working, archive = tree
    monkeypatch.setattr(Path, 'iterdir', lambda path: pytest.fail('root response must not enumerate'))
    assert browser.roots('working') == [{'name': str(working), 'path': str(working), 'issue': None}]
    assert browser.roots('archive')[0]['path'] == str(archive)


def test_listing_is_shallow_and_omits_files_and_exclusions(tree, monkeypatch):
    working, _ = tree
    original = Path.iterdir

    def enumerate_root(path):
        assert path == working
        return original(path)

    monkeypatch.setattr(Path, 'iterdir', enumerate_root)
    listing = browser.directories(str(working), 'working')
    assert [item['name'] for item in listing['directories']] == ['a', 'B']
    assert listing['omitted'] == 1
    assert listing['parent'] is None
    assert listing['ancestors'] == [str(working)]


def test_initial_nested_path_has_bounded_ancestors(tree):
    working, _ = tree
    listing = browser.directories(str(working / 'a' / 'deeper'), 'working')
    assert listing['ancestors'] == [str(working), str(working / 'a'), str(working / 'a' / 'deeper')]
    assert listing['parent'] == str(working / 'a')


@pytest.mark.parametrize('which', ['outside', 'excluded', 'wrong_role', 'traversal'])
def test_denied_navigation_never_enumerates(tree, monkeypatch, which):
    working, archive = tree
    path = {'outside': working.parent, 'excluded': working / 'private',
            'wrong_role': archive, 'traversal': working / 'a' / '..'}[which]
    monkeypatch.setattr(Path, 'iterdir', lambda path: pytest.fail('denied enumeration'))
    with pytest.raises(fs.FilesystemPolicyError):
        browser.directories(str(path), 'working')


def test_missing_file_or_unreadable_folder_has_structured_error(tree, monkeypatch):
    working, _ = tree
    for path in (working / 'missing', working / 'model.bin'):
        with pytest.raises(fs.FilesystemPolicyError) as error:
            browser.directories(str(path), 'working')
        assert error.value.code == 'filesystem_unverifiable'
    def denied(path):
        raise PermissionError('denied by filesystem')
    monkeypatch.setattr(Path, 'iterdir', denied)
    with pytest.raises(fs.FilesystemPolicyError) as error:
        browser.directories(str(working), 'working')
    assert error.value.detail()['params']['path'] == str(working)


def test_links_are_not_followed(tree, monkeypatch):
    from types import SimpleNamespace
    working, _ = tree
    original = Path.lstat
    monkeypatch.setattr(Path, 'lstat', lambda path, **kw:
                        SimpleNamespace(st_mode=0o120777) if path == working / 'a'
                        else original(path, **kw))
    listing = browser.directories(str(working), 'working')
    assert [item['name'] for item in listing['directories']] == ['B']
    with pytest.raises(fs.FilesystemPolicyError):
        browser.directories(str(working / 'a' / 'deeper'), 'working')


def test_missing_root_is_visible_with_reason(tree, monkeypatch):
    working, _ = tree
    missing = working / 'not-created'
    monkeypatch.setattr(fs, '_policy', fs.FilesystemPolicy((missing,), ()))
    assert browser.roots('working')[0]['issue']['code'] == 'filesystem_unverifiable'
    assert browser.roots('archive') == []
    assert not missing.exists()


@pytest.mark.skipif(os.name != 'nt', reason='Windows path case handling')
def test_root_case_variation_does_not_escape_ancestor_boundary(tree):
    working, _ = tree
    listing = browser.directories(str(working).upper(), 'working')
    assert listing['ancestors'] == [str(working)]
    assert listing['parent'] is None
