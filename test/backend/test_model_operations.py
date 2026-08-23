# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: test_model_operations.py
# purpose: Tests for model filesystem operations
# ---------------------------------------------------------------------------

from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlmodel import Session, create_engine

import backend.repository.repository as repository
from backend.repository.migrations import update_database_schema
from backend.repository.tables import (Component, ComponentSet, ComponentType,
                                       DeploymentStatus, Model)


MODEL_ID = 'a' * 64


@pytest.fixture
def model_repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    working = tmp_path / 'working' / 'checkpoints'
    archive = tmp_path / 'archive' / 'checkpoints'
    working.mkdir(parents=True)
    archive.mkdir(parents=True)
    engine = create_engine(f'sqlite:///{tmp_path / "operations.db"}')
    update_database_schema(engine)
    monkeypatch.setattr(repository, '_engine', engine)
    monkeypatch.setattr(repository, '_config', SimpleNamespace(
        read_only=False,
        model_folders={'checkpoints': {(working, archive)}},
    ))
    yield engine, working, archive
    engine.dispose()


def make_component(path: Path, component_type: ComponentType) -> Component:
    stat = path.stat()
    return Component(file_name=path.name,
                     size=stat.st_size,
                     modified_at_ns=stat.st_mtime_ns,
                     component_type=component_type,
                     touched='timestamp')


def add_working_model(engine, working: Path, where: str = 'w') -> None:
    model_dir = working / 'nested'
    examples_dir = working.parent / 'examples' / MODEL_ID
    model_dir.mkdir()
    examples_dir.mkdir(parents=True)
    weights = model_dir / 'model.safetensors'
    metadata = model_dir / 'model.archivist.json'
    example = examples_dir / 'preview.png'
    weights.write_bytes(b'weights')
    metadata.write_text('{"source": "working"}', encoding='utf-8')
    example.write_bytes(b'preview')
    model = Model(id=MODEL_ID,
                  file_name='model',
                  internal_name='Model',
                  type='checkpoints',
                  relative_path='nested',
                  deployment='working' if where == 'w' else 'archive',
                  touched='timestamp',
                  component_sets=[ComponentSet(
                      where=where,
                      primary_dir=str(model_dir),
                      examples_dir=str(examples_dir),
                      components=[make_component(weights, ComponentType.MODEL),
                                  make_component(metadata, ComponentType.METADATA),
                                  make_component(example, ComponentType.EXAMPLE)],
                  )])
    with Session(engine) as session:
        session.add(model)
        session.commit()


def test_synchronize_model_simulation_plans_all_components(model_repository):
    engine, working, archive = model_repository
    add_working_model(engine, working)

    result = repository.synchronize_model(MODEL_ID)

    assert result['allowed'] is True
    assert result['performed'] is False
    assert result['source_side'] == 'working'
    assert len(result['actions']) == 3
    assert not (archive / 'nested' / 'model.safetensors').exists()


def test_synchronize_model_copies_components_and_updates_database(model_repository):
    engine, working, archive = model_repository
    add_working_model(engine, working)

    result = repository.synchronize_model(MODEL_ID, simulate=False)

    assert result['allowed'] is True
    assert result['performed'] is True
    assert (archive / 'nested' / 'model.safetensors').read_bytes() == b'weights'
    assert (archive / 'nested' / 'model.archivist.json').read_text(encoding='utf-8') == '{"source": "working"}'
    assert (archive.parent / 'examples' / MODEL_ID / 'preview.png').read_bytes() == b'preview'
    with Session(engine) as session:
        model = session.get(Model, MODEL_ID)
        assert model.deployment == 'synced'
        assert {item.where for item in model.component_sets} == {'w', 'a'}


def test_synchronize_model_reports_file_and_byte_progress(model_repository):
    engine, working, _archive = model_repository
    add_working_model(engine, working)
    updates = []

    result = repository.synchronize_model(
        MODEL_ID, simulate=False, progress=lambda value: updates.append(value.copy()))

    assert result['performed'] is True
    assert updates[0] == {
        'phase': 'executing',
        'files_total': 3,
        'files_completed': 0,
        'bytes_total': 35,
        'bytes_completed': 0,
    }
    assert updates[-1]['files_completed'] == updates[-1]['files_total'] == 3
    assert updates[-1]['bytes_completed'] == updates[-1]['bytes_total'] == 35


def test_synchronize_model_rejects_identity_errors(model_repository):
    engine, working, _archive = model_repository
    add_working_model(engine, working)
    with Session(engine) as session:
        model = session.get(Model, MODEL_ID)
        model.errors = ['duplicate_working']
        session.add(model)
        session.commit()

    result = repository.synchronize_model(MODEL_ID, simulate=False)

    assert result['allowed'] is False
    assert result['errors'][0]['code'] == 'model_read_only'


def test_synchronize_model_uses_working_collection_as_authority(model_repository):
    engine, working, archive = model_repository
    add_working_model(engine, working)
    archive_dir = archive / 'nested'
    archive_examples = archive.parent / 'examples' / MODEL_ID
    archive_dir.mkdir()
    archive_examples.mkdir(parents=True)
    weights = archive_dir / 'model.safetensors'
    metadata = archive_dir / 'model.archivist.json'
    obsolete = archive_dir / 'model.old.txt'
    example = archive_examples / 'preview.png'
    weights.write_bytes(b'weights')
    metadata.write_text('{"source": "archive"}', encoding='utf-8')
    obsolete.write_bytes(b'obsolete')
    example.write_bytes(b'preview')
    with Session(engine) as session:
        model = session.get(Model, MODEL_ID)
        model.component_sets.append(ComponentSet(
            where='a',
            primary_dir=str(archive_dir),
            examples_dir=str(archive_examples),
            components=[make_component(weights, ComponentType.MODEL),
                        make_component(metadata, ComponentType.METADATA),
                        make_component(obsolete, ComponentType.EXTRA),
                        make_component(example, ComponentType.EXAMPLE)],
        ))
        model.deployment = 'mismatch'
        session.add(model)
        session.commit()

    result = repository.synchronize_model(MODEL_ID, simulate=False)

    assert result['source_side'] == 'working'
    assert metadata.read_text(encoding='utf-8') == '{"source": "working"}'
    assert obsolete.exists() is False
    assert {action['action'] for action in result['actions']} == {'copy', 'remove'}


def test_synchronize_archive_only_model_restores_working_collection(model_repository):
    engine, working, archive = model_repository
    add_working_model(engine, archive, where='a')

    result = repository.synchronize_model(MODEL_ID, simulate=False)

    assert result['source_side'] == 'archive'
    assert (working / 'nested' / 'model.safetensors').read_bytes() == b'weights'
    assert (working.parent / 'examples' / MODEL_ID / 'preview.png').read_bytes() == b'preview'


def test_move_model_simulation_plans_direct_moves(model_repository):
    engine, working, archive = model_repository
    add_working_model(engine, working)

    result = repository.move_model(MODEL_ID, DeploymentStatus.ARCHIVE)

    assert result['allowed'] is True
    assert result['performed'] is False
    assert {action['action'] for action in result['actions']} == {'move'}
    assert (working / 'nested' / 'model.safetensors').exists()
    assert not (archive / 'nested' / 'model.safetensors').exists()


def test_move_model_moves_collection_and_updates_database(model_repository):
    engine, working, archive = model_repository
    add_working_model(engine, working)

    result = repository.move_model(
        MODEL_ID, DeploymentStatus.ARCHIVE, simulate=False)

    assert result['performed'] is True
    assert not (working / 'nested' / 'model.safetensors').exists()
    assert not (working.parent / 'examples' / MODEL_ID / 'preview.png').exists()
    assert (archive / 'nested' / 'model.safetensors').read_bytes() == b'weights'
    assert (archive.parent / 'examples' / MODEL_ID / 'preview.png').read_bytes() == b'preview'
    with Session(engine) as session:
        model = session.get(Model, MODEL_ID)
        assert model.deployment == 'archive'
        assert [item.where for item in model.component_sets] == ['a']
