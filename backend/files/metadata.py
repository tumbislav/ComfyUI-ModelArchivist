# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: metadata.py
# purpose: Handle metadata sidecar files
# ---------------------------------------------------------------------------

import hashlib
import json
from pathlib import Path
from dataclasses import dataclass


ARCHIVIST_METADATA_SUFFIX = '.archivist.json'
LEGACY_METADATA_SUFFIX = '.metadata.json'
KNOWN_COMPOUND_SIDECAR_SUFFIXES = (ARCHIVIST_METADATA_SUFFIX,
                                   LEGACY_METADATA_SUFFIX,
                                   '.rgthree.json')


@dataclass
class ScannedModelMetadata:
    data: dict
    unreadable: bool
    hash_calculated: bool


def model_component_stem(file_path: Path) -> str:
    """Return the model stem shared by a model and either metadata sidecar."""
    for suffix in KNOWN_COMPOUND_SIDECAR_SUFFIXES:
        if file_path.name.endswith(suffix):
            return file_path.name[:-len(suffix)]
    return file_path.stem


def compute_sha256(path: Path, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as model:
        while chunk := model.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def load_model_metadata(model_file: Path, archivist_file: Path) -> dict:
    """Load Archivist metadata, importing a LoraManager sidecar if necessary."""
    if archivist_file.is_file():
        data = json.loads(archivist_file.read_text(encoding='utf-8'))
    else:
        legacy_file = model_file.with_suffix(LEGACY_METADATA_SUFFIX)
        if legacy_file.is_file():
            data = json.loads(legacy_file.read_text(encoding='utf-8'))
        else:
            data = {'sha256': compute_sha256(model_file),
                    'model_name': model_file.stem,
                    'file_name': model_file.stem,
                    'tags': []}
    if 'sha256' not in data:
        data['sha256'] = compute_sha256(model_file)
    data.setdefault('model_name', model_file.stem)
    data.setdefault('file_name', model_file.stem)
    data.setdefault('tags', [])
    archivist_file.write_text(json.dumps(data), encoding='utf-8')
    return data


def scan_model_metadata(model_file: Path, rehash: bool = False) -> ScannedModelMetadata:
    """Read cached metadata for scanning, computing a hash only when necessary."""
    archivist_file = model_file.with_suffix(ARCHIVIST_METADATA_SUFFIX)
    legacy_file = model_file.with_suffix(LEGACY_METADATA_SUFFIX)
    unreadable = False
    data = None
    for metadata_file in (archivist_file, legacy_file):
        if data is not None or not metadata_file.exists():
            continue
        try:
            loaded = json.loads(metadata_file.read_text(encoding='utf-8'))
            if not isinstance(loaded, dict):
                raise ValueError('metadata root is not an object')
            data = loaded
        except (OSError, UnicodeError, ValueError, TypeError):
            unreadable = True
    if data is None:
        data = {}
    cached_hash = data.get('sha256')
    usable_hash = (isinstance(cached_hash, str) and len(cached_hash) == 64
                   and all(char in '0123456789abcdefABCDEF' for char in cached_hash))
    hash_calculated = rehash or not usable_hash
    if hash_calculated:
        data['sha256'] = compute_sha256(model_file)
    data.setdefault('model_name', model_file.stem)
    data.setdefault('file_name', model_file.stem)
    data.setdefault('tags', [])
    if not unreadable and not archivist_file.exists():
        archivist_file.write_text(json.dumps(data), encoding='utf-8')
    return ScannedModelMetadata(data=data, unreadable=unreadable,
                                hash_calculated=hash_calculated)
