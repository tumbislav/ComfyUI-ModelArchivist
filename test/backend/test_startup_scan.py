# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: test_startup_scan.py
# purpose: Browser-requested startup scan guards and idempotence
# ---------------------------------------------------------------------------

from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend.server.routers import admin
from backend.dispatcher import OperationBusyError


@pytest.fixture
def scan_requests(monkeypatch):
    config = SimpleNamespace(read_only=False, setup_required=False,
                             options=SimpleNamespace(always_recalc_hashes=True))
    requests = []

    def submit(rehash):
        requests.append(rehash)
        return {'id': 'startup', 'state': 'pending'}

    monkeypatch.setattr(admin, 'get_config', lambda: config)
    monkeypatch.setattr(admin, 'submit_scan', submit)
    monkeypatch.setattr(admin, '_startup_scan_id', None)
    monkeypatch.setattr(admin.dispatcher, 'get',
                        lambda operation_id: {'id': operation_id, 'state': 'succeeded'})
    return config, requests


def test_concurrent_startup_requests_only_submit_once(scan_requests):
    _, requests = scan_requests
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: admin.start_scan(startup=True), range(8)))

    assert requests == [True]
    assert {result['id'] for result in results} == {'startup'}
    assert admin.start_scan(startup=True)['state'] == 'succeeded'


def test_manual_scans_remain_repeatable(scan_requests):
    _, requests = scan_requests
    admin.start_scan(startup=True)
    admin.start_scan()
    admin.start_scan(rehash=True)
    assert requests == [True, False, True]


@pytest.mark.parametrize('guard, status', [('read_only', 403), ('setup_required', 409)])
@pytest.mark.parametrize('startup', [False, True])
def test_unavailable_repository_cannot_scan(scan_requests, guard, status, startup):
    config, requests = scan_requests
    setattr(config, guard, True)

    with pytest.raises(HTTPException) as error:
        admin.start_scan(startup=startup)

    assert error.value.status_code == status
    assert requests == []


def test_busy_rejection_does_not_consume_startup_scan(scan_requests, monkeypatch):
    _, requests = scan_requests
    submit = admin.submit_scan

    def busy(rehash):
        raise OperationBusyError('busy')

    monkeypatch.setattr(admin, 'submit_scan', busy)
    with pytest.raises(HTTPException) as error:
        admin.start_scan(startup=True)
    assert error.value.status_code == 409

    monkeypatch.setattr(admin, 'submit_scan', submit)
    admin.start_scan(startup=True)
    assert requests == [True]
