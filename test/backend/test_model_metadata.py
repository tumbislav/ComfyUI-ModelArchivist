# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: test_model_metadata.py
# purpose: Tests for model metadata handling
# ---------------------------------------------------------------------------

import json
from pathlib import Path

from backend.files.metadata import load_model_metadata, model_component_stem


def test_imports_legacy_metadata_without_modifying_it(tmp_path):
    model_file = tmp_path / 'example.safetensors'
    legacy_file = tmp_path / 'example.metadata.json'
    archivist_file = tmp_path / 'example.archivist.json'
    model_file.write_bytes(b'model contents')
    legacy_data = {
        'sha256': 'legacy-hash',
        'model_name': 'Imported name',
        'file_name': 'example',
        'tags': ['imported'],
        'lora_manager_only': True,
    }
    legacy_text = json.dumps(legacy_data, indent=2)
    legacy_file.write_text(legacy_text, encoding='utf-8')

    data = load_model_metadata(model_file, archivist_file)

    assert data == legacy_data
    assert json.loads(archivist_file.read_text(encoding='utf-8')) == legacy_data
    assert legacy_file.read_text(encoding='utf-8') == legacy_text


def test_existing_archivist_metadata_takes_precedence_over_legacy(tmp_path):
    model_file = tmp_path / 'example.safetensors'
    legacy_file = tmp_path / 'example.metadata.json'
    archivist_file = tmp_path / 'example.archivist.json'
    model_file.write_bytes(b'model contents')
    legacy_file.write_text(json.dumps({'model_name': 'Legacy'}), encoding='utf-8')
    archivist_data = {
        'sha256': 'archivist-hash',
        'model_name': 'Archivist',
        'file_name': 'example',
        'tags': [],
    }
    archivist_file.write_text(json.dumps(archivist_data), encoding='utf-8')

    data = load_model_metadata(model_file, archivist_file)

    assert data == archivist_data


def test_sidecars_share_the_model_stem():
    assert model_component_stem(Path('example.metadata.json')) == 'example'
    assert model_component_stem(Path('example.archivist.json')) == 'example'
