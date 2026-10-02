# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: test/backend/test_release_metadata.py
# purpose: Regression tests for release metadata and tag validation
# ---------------------------------------------------------------------------

import runpy
import shutil
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
validate = runpy.run_path(str(ROOT / 'scripts' / 'check-release.py'))['validate']


@pytest.fixture
def release_root(tmp_path):
    for name in ['pyproject.toml', 'requirements.txt', 'README.md', 'LICENSE.md']:
        shutil.copyfile(ROOT / name, tmp_path / name)
    return tmp_path


def test_release_metadata_matches_requirements(release_root):
    validate(release_root)


def test_release_rejects_dependency_drift(release_root):
    (release_root / 'requirements.txt').write_text('different-package>=1\n')
    with pytest.raises(ValueError, match='dependencies differ'):
        validate(release_root)


def test_release_rejects_wrong_tag_before_git_operations(release_root):
    with pytest.raises(ValueError, match='Release tag must be'):
        validate(release_root, 'main')


def test_release_rejects_missing_license(release_root):
    (release_root / 'LICENSE.md').unlink()
    with pytest.raises(ValueError, match='missing file'):
        validate(release_root)
