# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: operations.py
# purpose: Serializable plans for filesystem operations
# ---------------------------------------------------------------------------

from dataclasses import asdict, dataclass, field
from pathlib import Path
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

    @classmethod
    def capture(cls, path: Path, include_hash: bool = False) -> 'FileSnapshot':
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
        return cls(True, stat.st_size, stat.st_mtime_ns, digest)

    def matches(self, path: Path) -> bool:
        current = self.capture(path, include_hash=self.sha256 is not None)
        return current == self


@dataclass
class FileAction:
    action: str
    source: str
    destination: str
    source_before: FileSnapshot
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


def atomic_copy(action: FileAction) -> None:
    source = Path(action.source)
    destination = Path(action.destination)
    if not action.source_before.matches(source):
        raise RuntimeError(f'source changed after validation: {source}')
    if not action.destination_before.matches(destination):
        raise RuntimeError(f'destination changed after validation: {destination}')
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f'.{destination.name}.{uuid4().hex}.tmp')
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()
