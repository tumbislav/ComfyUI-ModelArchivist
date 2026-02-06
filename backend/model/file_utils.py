# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: file_utils.py
# purpose: Various utility functions
# ---------------------------------------------------------------------------

import hashlib
import json
import logging
from pathlib import Path
from typing import Dict, Tuple

logger = logging.getLogger('model_archivist')

def compute_sha256(path: Path, chunk_size: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()

def ensure_metadata(model_file: Path, metadata_file) -> Dict:
    if metadata_file.is_file():
        data = json.loads(metadata_file.read_text(encoding='utf-8'))
    else:
        data = {}
    is_changed = False
    if 'sha256' not in data:
        data['sha256'] = compute_sha256(model_file)
        is_changed = True
    if 'model_name' not in data:
        data['model_name'] = model_file.stem
        is_changed = True
    if 'tags' not in data:
        data['tags'] = []
        is_changed = True
    if is_changed:
        logger.info(f'Updating metadata for {model_file}')
        metadata_file.write_text(json.dumps(data), encoding='utf-8')
    return data
