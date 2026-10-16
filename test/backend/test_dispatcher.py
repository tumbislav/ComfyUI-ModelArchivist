# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: test_dispatcher.py
# purpose: Tests for long-running operation dispatch and polling
# ---------------------------------------------------------------------------

from threading import Event
from time import monotonic, sleep

import pytest
from fastapi import HTTPException, Response

import backend.dispatcher as dispatcher_module
from backend.dispatcher import (OperationBusyError, OperationDispatcher,
                                UnknownOperationError)


def await_finished(dispatcher: OperationDispatcher, operation_id: str) -> dict:
    deadline = monotonic() + 2
    while monotonic() < deadline:
        operation = dispatcher.get(operation_id)
        if operation['state'] in ('succeeded', 'failed'):
            return operation
        sleep(0.01)
    pytest.fail('operation did not finish')


def test_dispatcher_reports_progress_and_result(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(dispatcher_module, '_get_scanner', lambda: None)
    dispatcher = OperationDispatcher()

    def target(report):
        report({'phase': 'executing', 'files_total': 2, 'files_completed': 1})
        return {'allowed': True, 'performed': True}

    submitted = dispatcher.submit('model_sync', target)
    result = await_finished(dispatcher, submitted['id'])

    assert result['state'] == 'succeeded'
    assert result['progress']['phase'] == 'complete'
    assert result['progress']['files_completed'] == 1
    assert result['result']['performed'] is True
    assert result['started_at'] is not None
    assert result['finished_at'] is not None


def test_dispatcher_rejects_a_second_active_operation(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(dispatcher_module, '_get_scanner', lambda: None)
    dispatcher = OperationDispatcher()
    release = Event()
    started = Event()

    def target(report):
        started.set()
        release.wait(2)
        return {'allowed': True}

    first = dispatcher.submit('scan', target)
    assert started.wait(1)
    with pytest.raises(OperationBusyError):
        dispatcher.submit('model_move', target)
    release.set()
    await_finished(dispatcher, first['id'])


def test_dispatcher_serializes_worker_exception(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(dispatcher_module, '_get_scanner', lambda: None)
    dispatcher = OperationDispatcher()

    def target(report):
        raise OSError('drive unavailable')

    submitted = dispatcher.submit('scan', target)
    result = await_finished(dispatcher, submitted['id'])

    assert result['state'] == 'failed'
    assert result['error'] == {'type': 'OSError', 'message': 'drive unavailable'}


def test_dispatcher_marks_rejected_repository_result_failed(
        monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(dispatcher_module, '_get_scanner', lambda: None)
    dispatcher = OperationDispatcher()
    submitted = dispatcher.submit(
        'model_move', lambda report: {'allowed': False, 'errors': ['read-only']})

    result = await_finished(dispatcher, submitted['id'])

    assert result['state'] == 'failed'
    assert result['result']['allowed'] is False
    assert result['error']['type'] == 'operation_rejected'


def test_dispatcher_marks_partial_transfer_failed(monkeypatch):
    monkeypatch.setattr(dispatcher_module, '_get_scanner', lambda: None)
    dispatcher = OperationDispatcher()
    submitted = dispatcher.submit('user_object_move', lambda report: {
        'allowed': True, 'performed': False,
        'warnings': [{'code': 'filesystem_error', 'message': 'directory locked'}],
    })
    result = await_finished(dispatcher, submitted['id'])
    assert result['state'] == 'failed'
    assert result['error']['type'] == 'operation_incomplete'
    assert 'directory locked' in result['error']['message']


@pytest.mark.parametrize('action', ['move', 'synchronize'])
def test_user_transfer_returns_before_filesystem_planning_finishes(monkeypatch, action):
    from backend.server.routers import user_types
    from backend.repository.tables import DeploymentStatus

    monkeypatch.setattr(dispatcher_module, '_get_scanner', lambda: None)
    dispatcher = OperationDispatcher()
    monkeypatch.setattr(user_types, 'dispatcher', dispatcher)
    monkeypatch.setattr(user_types.repo, 'user_object_operation_requires_lro',
                        lambda *_args: True)
    entered = Event()
    release = Event()

    def transfer(*args):
        assert args[2 if action == 'move' else 1] is False
        entered.set()
        assert release.wait(2)
        return {'allowed': True, 'performed': True}

    monkeypatch.setattr(user_types.repo, f'{action}_user_object', transfer)
    response = Response()
    endpoint = getattr(user_types, f'{action}_user_object')
    arguments = {'id': 'object', 'response': response, 'simulate': False}
    if action == 'move':
        arguments['destination'] = DeploymentStatus.ARCHIVE
    try:
        submitted = endpoint(**arguments)
        assert response.status_code == 202
        assert entered.wait(1)
        assert dispatcher.get(submitted['id'])['state'] == 'running'
        with pytest.raises(HTTPException) as error:
            endpoint(**arguments)
        assert error.value.status_code == 409
    finally:
        release.set()
    assert await_finished(dispatcher, submitted['id'])['state'] == 'succeeded'


def test_scan_error_summary_does_not_stringify_structured_diagnostics(monkeypatch):
    monkeypatch.setattr(dispatcher_module, '_get_scanner', lambda: None)
    dispatcher = OperationDispatcher()
    issues = [{'code': 'scan_incomplete', 'message': 'Unreadable file', 'params': {'path': 'model'}}]
    submitted = dispatcher.submit('scan', lambda report: {'allowed': False, 'errors': issues})
    result = await_finished(dispatcher, submitted['id'])
    assert result['error']['message'] == 'Scan completed with errors.'
    assert result['result']['errors'] == issues


def test_dispatcher_rejects_unknown_operation(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(dispatcher_module, '_get_scanner', lambda: None)
    dispatcher = OperationDispatcher()

    with pytest.raises(UnknownOperationError):
        dispatcher.get('missing')


def test_dispatcher_returns_active_operation(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(dispatcher_module, '_get_scanner', lambda: None)
    dispatcher = OperationDispatcher()
    release = Event()
    started = Event()

    def target(report):
        started.set()
        release.wait(2)
        return {'allowed': True}

    submitted = dispatcher.submit('model_move', target)
    assert started.wait(1)
    assert dispatcher.current()['id'] == submitted['id']
    release.set()
    await_finished(dispatcher, submitted['id'])
    assert dispatcher.current() is None


def test_dispatcher_surfaces_external_scan(monkeypatch: pytest.MonkeyPatch):
    class ScannerStub:
        started = True
        finished = False
        timestamp = 'scan-id'

        @staticmethod
        def progress():
            return {'started': True, 'finished': False, 'models_scanned': 4}

    monkeypatch.setattr(dispatcher_module, '_get_scanner', lambda: ScannerStub())
    dispatcher = OperationDispatcher()

    operation = dispatcher.current()

    assert operation['id'] == 'scan-id'
    assert operation['type'] == 'scan'
    assert operation['progress']['models_scanned'] == 4
