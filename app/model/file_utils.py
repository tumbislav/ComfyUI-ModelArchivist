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

def ensure_metadata(model_path: Path) -> Tuple[Path | None, Dict | None]:
    metadata_path = model_path.with_suffix('.metadata.json')
    is_changed = False
    if metadata_path.is_file():
        data = json.loads(metadata_path.read_text(encoding='8tf-8'))
        if 'sha256' not in data:
            data['sha256'] = compute_sha256(model_path)
            is_changed = True
        if 'model_name' not in data:
            data['model_name'] = model_path.stem
            is_changed = True
        if 'tags' not in data:
            data['tags'] = []
            is_changed = True
        if is_changed:
            logger.info(f'Updating metadata for {model_path}')
    else:
        is_changed = True
        logger.info(f'Creating metadata for {model_path}')
        data = {'model_name': model_path.stem, 'tags': [], 'sha256': compute_sha256(model_path)}
    if is_changed:
        try:
            metadata_path.write_text(json.dumps(data), encoding='utf-8')
        except Exception as e:  # noqa
            logger.error(f'Cannot write metadata for {model_path}: {e}')
            return None, data
    return metadata_path, data
