# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: backend/directory_browser.py
# purpose: Policy-confined, non-recursive directory browsing
# ---------------------------------------------------------------------------

from pathlib import Path
import stat

from backend.filesystem_policy import FilesystemPolicyError, Role, contains, get_policy


def _directory(path: Path, role: Role) -> Path:
    path = get_policy().check(path, role)
    try:
        if not stat.S_ISDIR(path.lstat().st_mode):
            raise NotADirectoryError(str(path))
    except OSError as error:
        raise FilesystemPolicyError('filesystem_unverifiable', path, role, str(error)) from error
    return path


def roots(role: Role) -> list[dict]:
    result = []
    for path in getattr(get_policy(), f'{role}_roots'):
        issue = None
        try:
            _directory(path, role)
        except FilesystemPolicyError as error:
            issue = error.detail()
        result.append({'path': str(path), 'name': str(path), 'issue': issue})
    return result


def directories(value: str, role: Role) -> dict:
    path = _directory(Path(value), role)
    policy = get_policy()
    root = max((root for root in getattr(policy, f'{role}_roots') if contains(root, path)),
               key=lambda root: len(root.parts))
    path = root.joinpath(*path.parts[len(root.parts):])
    ancestors = [path]
    while ancestors[-1] != root:
        ancestors.append(ancestors[-1].parent)
    children = []
    omitted = 0
    try:
        # Do not inspect grandchildren or resolve a link to determine its type.
        for child in path.iterdir():
            try:
                policy.check(child, role)
                if stat.S_ISDIR(child.lstat().st_mode):
                    children.append({'path': str(child), 'name': child.name, 'issue': None})
            except (FilesystemPolicyError, OSError):
                omitted += 1
    except OSError as error:
        raise FilesystemPolicyError('filesystem_unverifiable', path, role, str(error)) from error
    parent = None
    if path != root:
        parent = str(policy.check(path.parent, role))
    return {'path': str(path), 'parent': parent, 'ancestors': [str(p) for p in reversed(ancestors)],
            'directories': sorted(children, key=lambda item: (item['name'].casefold(), item['name'])),
            'omitted': omitted}
