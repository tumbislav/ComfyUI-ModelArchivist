# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: test_dispatcher.py
# purpose: Tests for long-running operation dispatch and polling
# ---------------------------------------------------------------------------

from threading import Event
from time import monotonic, sleep

import pytest

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


def test_dispatcher_rejects_unknown_operation(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(dispatcher_module, '_get_scanner', lambda: None)
    dispatcher = OperationDispatcher()

    with pytest.raises(UnknownOperationError):
        dispatcher.get('missing')
