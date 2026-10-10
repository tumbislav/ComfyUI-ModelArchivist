# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: test_model_operations.py
# purpose: Tests for model filesystem operations
# ---------------------------------------------------------------------------

import logging
import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import IntegrityError
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
    monkeypatch.setattr(repository, '_logger', logging.getLogger('test.model.operations'))
    monkeypatch.setattr(repository, '_config', SimpleNamespace(
        read_only=False,
        all_working={working},
        all_archive={archive},
        model_types={},
        model_folders={'checkpoints': {(working, archive)}},
    ))
    yield engine, working, archive
    engine.dispose()


def make_component(path: Path, component_type: ComponentType,
                   relative_path: str = '') -> Component:
    stat = path.stat()
    return Component(file_name=path.name,
                     size=stat.st_size,
                     modified_at_ns=stat.st_mtime_ns,
                     relative_path=relative_path,
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
                      primary_dir=str(working),
                      examples_dir=str(examples_dir),
                      components=[make_component(weights, ComponentType.MODEL, 'nested'),
                                  make_component(metadata, ComponentType.METADATA, 'nested'),
                                  make_component(example, ComponentType.EXAMPLE)],
                  )])
    with Session(engine) as session:
        session.add(model)
        session.commit()


@pytest.mark.parametrize('operation', ['move', 'synchronize'])
def test_transfer_denied_before_any_component_changes(model_repository, monkeypatch, operation):
    from backend import filesystem_policy as fs

    engine, working, archive = model_repository
    add_working_model(engine, working)
    blocked = archive / 'nested' / 'model.archivist.json'
    monkeypatch.setattr(fs, '_policy', fs.FilesystemPolicy(
        (working.parent,), (archive.parent,), (blocked,)))
    with pytest.raises(fs.FilesystemPolicyError) as error:
        if operation == 'move':
            repository.move_model(MODEL_ID, DeploymentStatus.ARCHIVE, simulate=False)
        else:
            repository.synchronize_model(MODEL_ID, simulate=False)
    assert error.value.code == 'filesystem_excluded'
    assert (working / 'nested' / 'model.safetensors').read_bytes() == b'weights'
    assert not (archive / 'nested').exists()


def test_model_representation_includes_actual_and_prospective_paths(model_repository):
    engine, working, archive = model_repository
    add_working_model(engine, working)

    result = repository.get_model(MODEL_ID)

    assert result['working_path'] == str(working / 'nested')
    assert result['archive_path'] == str(archive / 'nested')
    assert result['working_set']['where'] == 'w'
    assert result['archive_set'] is None
    assert result['base_model'] == ''
    assert result['base_model_abbreviation'] == ''
    assert result['has_tags'] is False
    assert result['has_collections'] is False
    assert 'component_sets' not in result


def test_relocate_model_moves_components_but_not_examples(model_repository):
    engine, working, _archive = model_repository
    add_working_model(engine, working)

    preview = repository.relocate_objects('models', [MODEL_ID], 'organized', True)
    result = repository.relocate_objects('models', [MODEL_ID], 'organized', False)

    assert preview['allowed'] is True
    assert result['performed'] is True
    assert (working / 'organized' / 'model.safetensors').is_file()
    assert (working / 'organized' / 'model.archivist.json').is_file()
    assert (working.parent / 'examples' / MODEL_ID / 'preview.png').is_file()
    assert repository.get_model(MODEL_ID)['relative_path'] == 'organized'


def test_relocate_model_rejects_duplicate_filename(model_repository):
    engine, working, _archive = model_repository
    add_working_model(engine, working)
    destination = working / 'organized' / 'model.safetensors'
    destination.parent.mkdir()
    destination.write_bytes(b'another model')

    result = repository.relocate_objects('models', [MODEL_ID], 'organized', False)

    assert result['allowed'] is False
    assert result['errors'][0]['code'] == 'duplicate_filename'
    assert (working / 'nested' / 'model.safetensors').is_file()


def test_update_model_base_model_updates_database_and_archivist_sidecar(model_repository):
    engine, working, _ = model_repository
    add_working_model(engine, working)
    changed = repository.get_model(MODEL_ID)
    changed['base_model'] = '  Flux.1 D  '

    result = repository.update_model(changed)

    assert result['base_model'] == 'Flux.1 D'
    assert result['base_model_abbreviation'] == 'F1D'
    metadata = working / 'nested' / 'model.archivist.json'
    assert '"base_model": "Flux.1 D"' in metadata.read_text(encoding='utf-8')
    with Session(engine) as session:
        assert session.get(Model, MODEL_ID).base_model == 'Flux.1 D'


def test_bulk_base_model_update_can_clear_value(model_repository):
    engine, working, _ = model_repository
    add_working_model(engine, working)

    repository.update_model_base_models([MODEL_ID], 'SDXL 1.0')
    result = repository.update_model_base_models([MODEL_ID], '   ')

    assert result['models'][0]['base_model'] == ''
    assert result['models'][0]['base_model_abbreviation'] == ''
    metadata = working / 'nested' / 'model.archivist.json'
    assert '"base_model": ""' in metadata.read_text(encoding='utf-8')


def test_bulk_base_model_read_only_guard_runs_before_model_access(monkeypatch):
    monkeypatch.setattr(repository, '_config', SimpleNamespace(read_only=True))
    monkeypatch.setattr(repository, 'get_model',
                        lambda *args: pytest.fail('must reject before model access'))
    with pytest.raises(repository.ArcException) as caught:
        repository.update_model_base_models([MODEL_ID], 'Flux')
    assert caught.value.code == repository.ArcException.Code.READ_ONLY


def test_bulk_base_model_read_only_is_reported_with_filesystem_reason(monkeypatch):
    from fastapi import HTTPException
    from backend.server.routers import models as router
    issue = {'code': 'filesystem_unverifiable', 'message': 'Cannot access archive folder Z:/archive.',
             'params': {'path': 'Z:/archive'}}
    config = SimpleNamespace(read_only=True, filesystem_issues=[issue])
    monkeypatch.setattr(repository, '_config', config)
    monkeypatch.setattr(router, 'get_config', lambda: config)
    monkeypatch.setattr(repository, 'get_model',
                        lambda *args: pytest.fail('read-only batch must not read or update models'))

    with pytest.raises(HTTPException) as caught:
        asyncio.run(router.update_model_base_models(
            router.ModelBaseModelUpdate(ids=[MODEL_ID], base_model='Flux')))

    assert caught.value.status_code == 403
    assert caught.value.detail['code'] == 'application_read_only'
    assert issue['message'] in caught.value.detail['message']
    assert caught.value.detail['issues'] == [issue]


def test_bulk_base_model_unknown_model_is_a_structured_not_found(monkeypatch):
    from fastapi import HTTPException
    from backend.exception import ArcException
    from backend.server.routers import models as router

    def reject(*args):
        raise ArcException(ArcException.Code.UNKNOWN_MODEL, 'Model does not exist')

    monkeypatch.setattr(repository, 'update_model_base_models', reject)
    with pytest.raises(HTTPException) as caught:
        asyncio.run(router.update_model_base_models(
            router.ModelBaseModelUpdate(ids=[MODEL_ID], base_model='Flux')))
    assert caught.value.status_code == 404
    assert caught.value.detail['code'] == 'unknown_model'


def test_list_base_models_is_distinct_case_insensitively_and_omits_blank(model_repository):
    engine, working, _ = model_repository
    add_working_model(engine, working)
    first = repository.get_model(MODEL_ID)
    first['base_model'] = 'SDXL 1.0'
    repository.update_model(first)
    with Session(engine) as session:
        session.add(Model(id='b' * 64, file_name='second', internal_name='Second',
                          type='checkpoints', base_model='sdxl 1.0', relative_path='',
                          deployment='archive', touched='timestamp'))
        session.add(Model(id='c' * 64, file_name='third', internal_name='Third',
                          type='checkpoints', base_model='', relative_path='',
                          deployment='archive', touched='timestamp'))
        session.commit()

    assert len(repository.list_base_models()) == 1
    assert repository.list_base_models()[0].casefold() == 'sdxl 1.0'.casefold()


def test_database_rejects_two_component_sets_on_same_model_side(model_repository):
    engine, working, _ = model_repository
    model = Model(id=MODEL_ID,
                  file_name='model',
                  internal_name='Model',
                  type='checkpoints',
                  relative_path='',
                  deployment='working',
                  touched='timestamp',
                  component_sets=[
                      ComponentSet(where='w', primary_dir=str(working), components=[]),
                      ComponentSet(where='w', primary_dir=str(working), components=[]),
                  ])

    with Session(engine) as session:
        session.add(model)
        with pytest.raises(IntegrityError):
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
            primary_dir=str(archive),
            examples_dir=str(archive_examples),
            components=[make_component(weights, ComponentType.MODEL, 'nested'),
                        make_component(metadata, ComponentType.METADATA, 'nested'),
                        make_component(obsolete, ComponentType.EXTRA, 'nested'),
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


def test_model_batch_operation_preflights_and_executes(model_repository):
    engine, working, archive = model_repository
    add_working_model(engine, working)
    progress = []

    validation = repository.model_batch_operation(
        [MODEL_ID], 'synchronize', True)
    result = repository.model_batch_operation(
        [MODEL_ID], 'synchronize', False, progress=progress.append)

    assert validation['allowed'] is True
    assert validation['performed'] is False
    assert result['performed'] is True
    assert len(result['members']) == 1
    assert progress[0]['bytes_total'] > 0
    assert progress[-1]['bytes_completed'] == progress[-1]['bytes_total']
    assert progress[-1]['files_completed'] == progress[-1]['files_total']
    assert (archive / 'nested' / 'model.safetensors').exists()
