# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: backend/filesystem_policy.py
# purpose: Disk-owned filesystem boundaries and traversal without links
# ---------------------------------------------------------------------------

from dataclasses import dataclass
import logging
import os
from pathlib import Path
import stat
from uuid import UUID
from typing import Callable, Literal


Role = Literal['working', 'archive']


class FilesystemPolicyError(Exception):
    def __init__(self, code: str, path: object, role: str | None = None, reason: str = ''):
        self.code = code
        self.params = {'path': str(path), 'role': role or 'working or archive'}
        messages = {
            'filesystem_absolute_required': 'Use a fully qualified path without parent traversal: {path}.',
            'filesystem_outside_roots': 'Folder or file is outside the permitted {role} roots: {path}. '
                'Edit [filesystem] in config.toml and restart Archivist.',
            'filesystem_excluded': 'Folder or file is excluded by config.toml: {path}.',
            'filesystem_link_forbidden': 'Links and junctions are not permitted: {path}. Use the actual location.',
            'filesystem_hardlink_forbidden': 'Files with multiple hard links are not permitted: {path}.',
            'filesystem_mount_forbidden': 'A mounted volume must have an explicitly permitted root: {path}.',
            'filesystem_unverifiable': 'Archivist cannot verify filesystem access or link information: {path}.',
            'filesystem_special_forbidden': 'Only ordinary files and directories are permitted: {path}.',
        }
        self.message = messages[code].format(**self.params)
        if reason:
            self.message += f' {reason}'
        super().__init__(self.message)

    def detail(self) -> dict:
        return {'code': self.code, 'message': self.message, 'params': self.params}


def literal_path(value: str | Path) -> Path:
    path = Path(value)
    if (not path.is_absolute() or '..' in path.parts or '\x00' in str(path)
            or (os.name == 'nt' and (str(path).startswith(('\\\\?\\', '\\\\.\\'))
                                    or any(':' in part for part in path.parts[1:])))):
        raise FilesystemPolicyError('filesystem_absolute_required', value)
    return Path(os.path.abspath(path))


def contains(root: Path, path: Path) -> bool:
    try:
        return os.path.commonpath((os.path.normcase(root), os.path.normcase(path))) == os.path.normcase(root)
    except ValueError:
        return False


@dataclass(frozen=True)
class FilesystemPolicy:
    working_roots: tuple[Path, ...] = ()
    archive_roots: tuple[Path, ...] = ()
    exclusions: tuple[Path, ...] = ()

    @classmethod
    def from_dict(cls, data: dict) -> 'FilesystemPolicy':
        if not isinstance(data, dict) or set(data) != {'working_roots', 'archive_roots', 'exclusions'}:
            raise ValueError('[filesystem] requires working_roots, archive_roots, and exclusions')
        values = {}
        for key, items in data.items():
            if not isinstance(items, list) or any(not isinstance(item, str) for item in items):
                raise ValueError(f'filesystem.{key} must be a list of absolute paths')
            values[key] = tuple(literal_path(item) for item in items)
        return cls(**values)

    def to_dict(self) -> dict:
        return {name: [str(path) for path in getattr(self, name)]
                for name in ('working_roots', 'archive_roots', 'exclusions')}

    def check(self, value: str | Path, role: Role | None = None) -> Path:
        path = literal_path(value)
        roots = (self.working_roots if role == 'working' else self.archive_roots
                 if role == 'archive' else self.working_roots + self.archive_roots)
        matches = [root for root in roots if contains(root, path)]
        if not matches:
            raise FilesystemPolicyError('filesystem_outside_roots', path, role)
        if any(contains(excluded, path) for excluded in self.exclusions):
            raise FilesystemPolicyError('filesystem_excluded', path, role)
        root = max(matches, key=lambda item: len(item.parts))
        for part in (*reversed(path.parents), path):
            try:
                info = part.lstat()
            except FileNotFoundError:
                continue
            except OSError as error:
                raise FilesystemPolicyError('filesystem_unverifiable', part, role, str(error)) from error
            reparse = getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400)
            if stat.S_ISLNK(info.st_mode) or reparse:
                # Windows volume mount points and junctions share a reparse tag.
                # Only an explicit volume GUID target is a volume, never a junction.
                volume = False
                if (os.name == 'nt' and reparse
                        and getattr(info, 'st_reparse_tag', 0) == stat.IO_REPARSE_TAG_MOUNT_POINT):
                    try:
                        target = os.readlink(part)
                        prefix = '\\\\?\\Volume{'
                        if target.startswith(prefix) and target.endswith('}\\'):
                            UUID(target[len(prefix):-2])
                            volume = True
                    except (OSError, ValueError):
                        pass
                if not volume:
                    raise FilesystemPolicyError('filesystem_link_forbidden', part, role)
                if not contains(part, root):
                    raise FilesystemPolicyError('filesystem_mount_forbidden', part, role)
                try:
                    info = part.stat()  # Follow only a verified, explicitly permitted volume mount.
                except OSError as error:
                    raise FilesystemPolicyError('filesystem_unverifiable', part, role, str(error)) from error
            if part != root and contains(root, part) and os.path.ismount(part):
                raise FilesystemPolicyError('filesystem_mount_forbidden', part, role)
            if stat.S_ISREG(info.st_mode):
                count = getattr(info, 'st_nlink', 0)
                if not isinstance(count, int) or count < 1:
                    raise FilesystemPolicyError('filesystem_unverifiable', part, role)
                if count > 1:
                    raise FilesystemPolicyError('filesystem_hardlink_forbidden', part, role)
            elif not stat.S_ISDIR(info.st_mode):
                raise FilesystemPolicyError('filesystem_special_forbidden', part, role)
        # Check canonical containment too. Link checks above must precede realpath.
        try:
            canonical = Path(os.path.realpath(path))
            canonical_root = Path(os.path.realpath(root))
            excluded = any(contains(Path(os.path.realpath(item)), canonical) for item in self.exclusions)
        except (OSError, ValueError) as error:
            raise FilesystemPolicyError('filesystem_unverifiable', path, role, str(error)) from error
        if not contains(canonical_root, canonical):
            raise FilesystemPolicyError('filesystem_outside_roots', path, role)
        if excluded:
            raise FilesystemPolicyError('filesystem_excluded', path, role)
        return path


_policy = FilesystemPolicy()


def get_policy() -> FilesystemPolicy:
    return _policy


def set_policy(policy: FilesystemPolicy) -> None:
    global _policy
    _policy = policy


def checked_path(path: str | Path, role: Role | None = None) -> Path:
    return get_policy().check(path, role)


def safe_children(path: Path, role: Role | None = None,
                  on_blocked: Callable[[FilesystemPolicyError], None] | None = None):
    checked_path(path, role)
    for child in path.iterdir():
        try:
            checked_path(child, role)
        except FilesystemPolicyError as error:
            if on_blocked is None:
                raise
            on_blocked(error)
            continue
        yield child


def safe_walk(path: Path, role: Role | None = None,
              on_blocked: Callable[[FilesystemPolicyError], None] | None = None):
    """Top-down walk with mutable directory names; validate before every descent."""
    children = list(safe_children(path, role, on_blocked))
    directories = [child.name for child in children if child.is_dir()]
    files = [child.name for child in children if child.is_file()]
    yield path, directories, files
    for name in directories:
        child = path / name
        try:
            yield from safe_walk(child, role, on_blocked)
        except FilesystemPolicyError as error:
            if on_blocked is None:
                raise
            on_blocked(error)


def safe_tree(path: Path, role: Role | None = None,
              on_blocked: Callable[[FilesystemPolicyError], None] | None = None):
    for directory, dirs, files in safe_walk(path, role, on_blocked):
        yield from (directory / name for name in dirs + files)


def log_blocked(error: FilesystemPolicyError) -> None:
    logging.getLogger('archivist.files').warning('%s', error)


def check_component_sets(component_sets) -> None:
    """Validate deployed component paths before any member of an object is changed."""
    for component_set in component_sets:
        role = 'working' if component_set.where == 'w' else 'archive'
        checked_path(component_set.primary_dir, role)
        for component in component_set.components:
            checked_path(Path(component.file_dir) / component.file_name, role)


def check_transfer_tree(source: Path, destination: Path, role: Role | None = None) -> None:
    """Preflight a directory rename including excluded or linked descendants."""
    checked_path(source, role)
    checked_path(destination, role)
    if source.is_dir():
        for entry in safe_tree(source, role):
            checked_path(destination / entry.relative_to(source), role)
