# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: scripts/check-release.py
# purpose: Validate publication metadata and release tag provenance without publishing
# ---------------------------------------------------------------------------

import argparse
import re
import subprocess
import tomllib
from pathlib import Path


def validate(root: Path, tag: str | None = None) -> None:
    metadata = tomllib.loads((root / 'pyproject.toml').read_text(encoding='utf-8'))
    project = metadata['project']
    comfy = metadata['tool']['comfy']
    version = project['version']
    if not re.fullmatch(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)', version):
        raise ValueError('Publication requires a version in X.Y.Z format.')
    if not comfy.get('PublisherId') or not comfy.get('DisplayName'):
        raise ValueError('Registry publisher and display name are required.')
    if not project.get('urls', {}).get('Repository', '').startswith('https://github.com/'):
        raise ValueError('A GitHub repository URL is required.')
    if 'frontend/build' not in comfy.get('includes', []):
        raise ValueError('Registry packages must include frontend/build.')
    requirements = {
        re.sub(r'\s+', '', line.split('#', 1)[0])
        for line in (root / 'requirements.txt').read_text().splitlines()
        if line.split('#', 1)[0].strip()
    }
    if requirements != {re.sub(r'\s+', '', item) for item in project['dependencies']}:
        raise ValueError('Runtime dependencies differ between pyproject.toml and requirements.txt.')
    for name in [project['readme'], *project.get('license-files', [])]:
        if not (root / name).is_file():
            raise ValueError(f'Metadata references a missing file: {name}')

    migration_root = root / 'alembic' / 'versions'
    migration_files = sorted(migration_root.glob('*.py'))
    if not migration_files:
        raise ValueError('No Alembic migration revisions are present.')

    try:
        git_root = Path(subprocess.check_output(
            ['git', 'rev-parse', '--show-toplevel'],
            cwd=root,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()).resolve()
    except (OSError, subprocess.CalledProcessError):
        git_root = None

    if git_root == root.resolve():
        tracked_files = set(subprocess.check_output(
            ['git', 'ls-files', '--', 'alembic/versions/*.py'],
            cwd=root,
            text=True,
        ).splitlines())
        untracked_migrations = [
            migration.relative_to(root).as_posix()
            for migration in migration_files
            if migration.relative_to(root).as_posix() not in tracked_files
        ]
        if untracked_migrations:
            names = ', '.join(untracked_migrations)
            raise ValueError(f'Alembic migration revisions are not tracked by Git: {names}')

    if tag is not None:
        if tag != f'v{version}':
            raise ValueError(f'Release tag must be v{version}, matching pyproject.toml.')

        def git(*args: str) -> str:
            return subprocess.check_output(['git', *args], cwd=root, text=True).strip()

        revision = git('rev-parse', '--verify', f'refs/tags/{tag}^{{commit}}')
        if revision != git('rev-parse', 'HEAD'):
            raise ValueError('The checkout does not match the release tag.')
        subprocess.run(['git', 'merge-base', '--is-ancestor', revision, 'origin/master'],
                       cwd=root, check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', help='Require this release tag at HEAD, reachable from origin/master')
    args = parser.parse_args()
    try:
        validate(Path(__file__).resolve().parents[1], args.tag)
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'Release validation failed: {error}\n')
    print('Release metadata validated.' if args.tag is None else f'Release {args.tag} validated.')
