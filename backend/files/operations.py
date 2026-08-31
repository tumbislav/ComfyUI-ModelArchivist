# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: operations.py
# purpose: Serializable plans for filesystem operations
# ---------------------------------------------------------------------------

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable
import errno
import hashlib
import os
import shutil
from uuid import uuid4


@dataclass
class FileSnapshot:
    exists: bool
    size: int | None = None
    modified_at_ns: int | None = None
    sha256: str | None = None
    entry_type: str | None = None

    @classmethod
    def capture(cls, path: Path, include_hash: bool = False) -> 'FileSnapshot':
        if path.is_dir():
            stat = path.stat()
            return cls(True, 0, stat.st_mtime_ns, None, 'directory')
        if not path.is_file():
            return cls(exists=False)
        stat = path.stat()
        digest = None
        if include_hash:
            hasher = hashlib.sha256()
            with path.open('rb') as source:
                while chunk := source.read(1 << 20):
                    hasher.update(chunk)
            digest = hasher.hexdigest()
        return cls(True, stat.st_size, stat.st_mtime_ns, digest, 'file')

    def matches(self, path: Path) -> bool:
        current = self.capture(path, include_hash=self.sha256 is not None)
        if self.entry_type == 'directory':
            return current.exists and current.entry_type == 'directory'
        return current == self


@dataclass
class FileAction:
    action: str
    source: str | None
    destination: str
    source_before: FileSnapshot | None
    destination_before: FileSnapshot


@dataclass
class OperationIssue:
    code: str
    message: str


@dataclass
class OperationPlan:
    operation: str
    object_type: str
    object_id: str
    simulate: bool
    allowed: bool = True
    performed: bool = False
    source_side: str | None = None
    actions: list[FileAction] = field(default_factory=list)
    errors: list[OperationIssue] = field(default_factory=list)
    warnings: list[OperationIssue] = field(default_factory=list)

    def reject(self, code: str, message: str) -> None:
        self.allowed = False
        self.errors.append(OperationIssue(code, message))

    def to_dict(self) -> dict:
        return asdict(self)


def _existing_parent(path: Path) -> Path:
    candidate = path.parent
    while not candidate.exists() and candidate != candidate.parent:
        candidate = candidate.parent
    return candidate


def action_transfer_size(action: FileAction) -> int:
    """Return the bytes expected to be copied by an action."""
    if action.source_before is None or action.source_before.size is None:
        return 0
    if action.action == 'copy':
        return action.source_before.size
    if action.action != 'move' or action.source is None:
        return 0
    try:
        destination_parent = _existing_parent(Path(action.destination))
        if Path(action.source).stat().st_dev == destination_parent.stat().st_dev:
            return 0
    except OSError:
        pass
    return action.source_before.size


def _copy_contents(source: Path, destination: Path,
                   report_bytes: Callable[[int], None] | None = None) -> None:
    with source.open('rb') as source_file, destination.open('wb') as destination_file:
        while chunk := source_file.read(1 << 20):
            destination_file.write(chunk)
            if report_bytes is not None:
                report_bytes(len(chunk))
    shutil.copystat(source, destination)


def atomic_copy(action: FileAction,
                report_bytes: Callable[[int], None] | None = None) -> None:
    if action.source is None or action.source_before is None:
        raise ValueError('copy action requires a source')
    source = Path(action.source)
    destination = Path(action.destination)
    if not action.source_before.matches(source):
        raise RuntimeError(f'source changed after validation: {source}')
    if not action.destination_before.matches(destination):
        raise RuntimeError(f'destination changed after validation: {destination}')
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f'.{destination.name}.{uuid4().hex}.tmp')
    try:
        _copy_contents(source, temporary, report_bytes)
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def execute_file_action(action: FileAction,
                        report_bytes: Callable[[int], None] | None = None) -> None:
    if action.action == 'copy':
        atomic_copy(action, report_bytes)
        return
    if action.action == 'mkdir':
        destination = Path(action.destination)
        if not action.destination_before.matches(destination):
            raise RuntimeError(f'destination changed after validation: {destination}')
        destination.mkdir(parents=True, exist_ok=True)
        return
    if action.action == 'rmdir':
        destination = Path(action.destination)
        if not action.destination_before.matches(destination):
            raise RuntimeError(f'destination changed after validation: {destination}')
        destination.rmdir()
        return
    if action.action == 'remove':
        destination = Path(action.destination)
        if not action.destination_before.matches(destination):
            raise RuntimeError(f'destination changed after validation: {destination}')
        destination.unlink()
        return
    if action.action == 'move':
        if action.source is None or action.source_before is None:
            raise ValueError('move action requires a source')
        source = Path(action.source)
        destination = Path(action.destination)
        if not action.source_before.matches(source):
            raise RuntimeError(f'source changed after validation: {source}')
        if not action.destination_before.matches(destination):
            raise RuntimeError(f'destination changed after validation: {destination}')
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.replace(source, destination)
        except OSError as error:
            if error.errno != errno.EXDEV:
                raise
            temporary = destination.with_name(f'.{destination.name}.{uuid4().hex}.tmp')
            try:
                _copy_contents(source, temporary, report_bytes)
                copied = FileSnapshot.capture(
                    temporary, include_hash=action.source_before.sha256 is not None)
                if (copied.size != action.source_before.size or
                        (action.source_before.sha256 is not None and
                         copied.sha256 != action.source_before.sha256)):
                    raise RuntimeError(f'copied file verification failed: {source}')
                os.replace(temporary, destination)
                source.unlink()
            finally:
                if temporary.exists():
                    temporary.unlink()
        return
    raise ValueError(f'unknown file action: {action.action}')
