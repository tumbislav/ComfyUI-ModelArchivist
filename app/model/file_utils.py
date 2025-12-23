# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: file_utils.py
# purpose: Various utility functions
# ---------------------------------------------------------------------------

import hashlib
from pathlib import Path


def compute_sha256(path: Path, chunk_size: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()
