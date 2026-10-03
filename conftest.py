# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: conftest.py
# purpose: Project-wide pytest configuration
# ---------------------------------------------------------------------------

import csv
from hashlib import sha256
import os
from pathlib import Path
import subprocess

import pytest


def _test_account_key() -> str:
    """Use the process account, not USERNAME inherited from the desktop user."""
    if os.name == 'nt':
        identity = subprocess.check_output(
            ['whoami', '/user', '/fo', 'csv', '/nh'],
            text=True, encoding='utf-8', errors='replace')
        account = next(csv.reader(identity.splitlines()))[1]
    else:
        account = str(os.getuid())
    return sha256(account.encode('utf-8')).hexdigest()[:16]


def configure_test_paths(config) -> None:
    """Separate private pytest output by account while retaining numbered runs."""
    root = Path(__file__).parent / 'test' / 'temp' / f'account-{_test_account_key()}'
    root.mkdir(parents=True, exist_ok=True)
    changes = {'MODEL_ARCHIVIST_PYTEST_ROOT': str(root)}
    if config.option.basetemp is None and 'PYTEST_DEBUG_TEMPROOT' not in os.environ:
        changes['PYTEST_DEBUG_TEMPROOT'] = str(root)
    previous = {name: os.environ.get(name) for name in changes}
    os.environ.update(changes)

    def restore_environment():
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    config.add_cleanup(restore_environment)


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    # Run before pytest's cache and temporary-directory plugins configure themselves.
    configure_test_paths(config)


@pytest.fixture(autouse=True)
def isolated_filesystem_policy(tmp_path, monkeypatch):
    """Tests explicitly permit their own temporary tree, never the host filesystem."""
    from backend import filesystem_policy
    policy = filesystem_policy.FilesystemPolicy((tmp_path,), (tmp_path,))
    monkeypatch.setattr(filesystem_policy, '_policy', policy)
