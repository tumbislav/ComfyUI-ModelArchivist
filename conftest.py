# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: conftest.py
# purpose: Project-wide pytest configuration
# ---------------------------------------------------------------------------

from pathlib import Path


def pytest_configure(config) -> None:
    """Keep pytest-managed temporary files under the ignored test directory."""
    if config.option.basetemp is None:
        temp_root = Path(__file__).parent / 'test' / 'temp'
        temp_root.mkdir(parents=True, exist_ok=True)
        config.option.basetemp = str(temp_root / 'pytest')
