# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: test/backend/test_pytest_configuration.py
# purpose: Regression coverage for account-separated pytest temporary and cache paths
# ---------------------------------------------------------------------------

from hashlib import sha256
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

import conftest as configuration


@pytest.mark.skipif(os.name != 'nt', reason='Windows process identity')
def test_windows_account_uses_process_sid_instead_of_inherited_username(monkeypatch):
    monkeypatch.setenv('USERNAME', 'desktop-user')
    identities = iter([
        '"machine\\sandbox","S-1-5-21-1001"\n',
        '"machine\\desktop-user","S-1-5-21-1002"\n',
    ])
    monkeypatch.setattr(configuration.subprocess, 'check_output',
                        lambda *args, **kwargs: next(identities))
    assert configuration._test_account_key() == sha256(b'S-1-5-21-1001').hexdigest()[:16]
    assert configuration._test_account_key() == sha256(b'S-1-5-21-1002').hexdigest()[:16]


@pytest.mark.parametrize('basetemp', [None, 'explicit-base'])
@pytest.mark.parametrize('external_root', [None, 'explicit-root'])
def test_test_paths_preserve_overrides_and_restore_environment(tmp_path, monkeypatch,
                                                              basetemp, external_root):
    monkeypatch.setattr(configuration, '__file__', str(tmp_path / 'conftest.py'))
    monkeypatch.setattr(configuration, '_test_account_key', lambda: 'test-user')
    monkeypatch.setenv('MODEL_ARCHIVIST_PYTEST_ROOT', 'previous-root')
    if external_root is None:
        monkeypatch.delenv('PYTEST_DEBUG_TEMPROOT', raising=False)
    else:
        monkeypatch.setenv('PYTEST_DEBUG_TEMPROOT', external_root)
    cleanups = []
    config = SimpleNamespace(option=SimpleNamespace(basetemp=basetemp), add_cleanup=cleanups.append)

    configuration.configure_test_paths(config)
    root = tmp_path / 'test' / 'temp' / 'account-test-user'
    assert root.is_dir()
    assert os.environ['MODEL_ARCHIVIST_PYTEST_ROOT'] == str(root)
    assert config.option.basetemp == basetemp
    expected_temp = str(root) if basetemp is None and external_root is None else external_root
    assert os.environ.get('PYTEST_DEBUG_TEMPROOT') == expected_temp
    cleanups[0]()
    assert os.environ['MODEL_ARCHIVIST_PYTEST_ROOT'] == 'previous-root'
    assert os.environ.get('PYTEST_DEBUG_TEMPROOT') == external_root


def test_default_cache_and_numbered_temp_runs_use_the_same_account_root(pytestconfig, tmp_path):
    root = Path(os.environ['MODEL_ARCHIVIST_PYTEST_ROOT'])
    if pytestconfig.option.basetemp is None and os.environ.get('PYTEST_DEBUG_TEMPROOT') == str(root):
        assert tmp_path.is_relative_to(root)
        assert tmp_path.parent.name.startswith('pytest-')
    if pytestconfig.getini('cache_dir') == '${MODEL_ARCHIVIST_PYTEST_ROOT}/cache':
        probe = pytestconfig.cache.mkdir('account-isolation')
        assert probe.is_relative_to(root / 'cache')
