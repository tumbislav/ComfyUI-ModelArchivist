# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: dispatcher.py
# purpose: Dispatch and report long-running backend operations
# ---------------------------------------------------------------------------

from copy import deepcopy
from datetime import datetime, timezone
from threading import Lock, Thread
from time import sleep
from typing import Callable
from uuid import uuid4

class OperationBusyError(RuntimeError):
    pass


class UnknownOperationError(KeyError):
    pass


OperationTarget = Callable[[Callable[[dict], None]], dict]


def _get_scanner():
    from backend.files.scanner import get_scanner
    return get_scanner()


def _create_scanner():
    from backend.files.scanner import create_scanner
    return create_scanner()


class OperationDispatcher:
    def __init__(self) -> None:
        self._lock = Lock()
        self._operations: dict[str, dict] = {}
        self._active_id: str | None = None

    def submit(self, operation_type: str, target: OperationTarget) -> dict:
        with self._lock:
            scanner = _get_scanner()
            if self._active_id is not None or (
                    scanner is not None and scanner.started and not scanner.finished):
                raise OperationBusyError('another long-running operation is active')
            operation_id = str(uuid4())
            operation = {
                'id': operation_id,
                'type': operation_type,
                'state': 'pending',
                'submitted_at': self._now(),
                'started_at': None,
                'finished_at': None,
                'progress': {'phase': 'pending'},
                'result': None,
                'error': None,
            }
            self._operations[operation_id] = operation
            self._active_id = operation_id
        Thread(target=self._run, args=(operation_id, target), daemon=True).start()
        return self.get(operation_id)

    def get(self, operation_id: str) -> dict:
        with self._lock:
            operation = self._operations.get(operation_id)
            if operation is None:
                raise UnknownOperationError(operation_id)
            return deepcopy(operation)

    def active(self) -> dict | None:
        """Return the active dispatched operation, if there is one."""
        with self._lock:
            if self._active_id is None:
                return None
            return deepcopy(self._operations[self._active_id])

    def current(self) -> dict | None:
        """Return the active LRO, including scans started outside the dispatcher."""
        operation = self.active()
        if operation is not None:
            return operation
        scanner = _get_scanner()
        if scanner is None or not scanner.started or scanner.finished:
            return None
        return {
            'id': scanner.timestamp,
            'type': 'scan',
            'state': 'running',
            'submitted_at': scanner.timestamp,
            'started_at': scanner.timestamp,
            'finished_at': None,
            'progress': scanner.progress(),
            'result': None,
            'error': None,
        }

    def _run(self, operation_id: str, target: OperationTarget) -> None:
        with self._lock:
            operation = self._operations[operation_id]
            operation['state'] = 'running'
            operation['started_at'] = self._now()
            operation['progress'] = {'phase': 'preparing'}
        try:
            result = target(lambda progress: self._report(operation_id, progress))
            with self._lock:
                operation = self._operations[operation_id]
                operation['result'] = result
                if isinstance(result, dict) and result.get('allowed') is False:
                    operation['state'] = 'failed'
                    operation['error'] = {
                        'type': 'operation_rejected',
                        'message': str(result.get('errors', 'operation was rejected')),
                    }
                else:
                    operation['state'] = 'succeeded'
        except Exception as error:
            with self._lock:
                operation = self._operations[operation_id]
                operation['state'] = 'failed'
                operation['error'] = {
                    'type': type(error).__name__,
                    'message': str(error),
                }
        finally:
            with self._lock:
                operation = self._operations[operation_id]
                operation['finished_at'] = self._now()
                if operation['state'] == 'succeeded':
                    operation['progress']['phase'] = 'complete'
                self._active_id = None

    def _report(self, operation_id: str, progress: dict) -> None:
        with self._lock:
            self._operations[operation_id]['progress'] = deepcopy(progress)

    @staticmethod
    def _now() -> str:
        return datetime.now(tz=timezone.utc).isoformat()


dispatcher = OperationDispatcher()


def submit_scan(rehash: bool = False) -> dict:
    def run(report: Callable[[dict], None]) -> dict:
        scanner = _create_scanner()
        if scanner is None:
            raise OperationBusyError('scan cannot be started')
        scan_id = scanner.start(rehash)
        while not scanner.finished:
            report(scanner.progress())
            sleep(0.1)
        progress = scanner.progress()
        report(progress)
        return {'scan_id': scan_id, 'progress': progress}

    return dispatcher.submit('scan', run)
