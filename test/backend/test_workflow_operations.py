# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: test_workflow_operations.py
# purpose: Tests for workflow filesystem operations
# ---------------------------------------------------------------------------

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlmodel import Session, create_engine

import backend.repository.repository as repository
from backend.repository.migrations import update_database_schema
from backend.repository.tables import (Component, ComponentSet, ComponentType,
                                       DeploymentStatus, Workflow)


@pytest.fixture
def workflow_repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    working = tmp_path / 'working'
    archive = tmp_path / 'archive'
    working.mkdir()
    archive.mkdir()
    engine = create_engine(f'sqlite:///{tmp_path / "operations.db"}')
    update_database_schema(engine)
    monkeypatch.setattr(repository, '_engine', engine)
    monkeypatch.setattr(repository, '_config', SimpleNamespace(
        read_only=False,
        workflow_folders=[(working, archive)],
    ))
    yield engine, working, archive
    engine.dispose()


def add_workflow(engine, root: Path, where: str, content: str) -> str:
    workflow_id = str(uuid4())
    workflow_file = root / 'nested' / 'workflow.json'
    workflow_file.parent.mkdir()
    workflow_file.write_text(content, encoding='utf-8')
    stat = workflow_file.stat()
    workflow = Workflow(
        id=workflow_id,
        file_name='workflow',
        internal_name='Workflow',
        purpose='',
        relative_path='nested',
        deployment='working' if where == 'w' else 'archive',
        touched='timestamp',
        component_sets=[ComponentSet(
            where=where,
            primary_dir=str(root),
            components=[Component(
                file_name='workflow.json',
                relative_path='nested',
                size=stat.st_size,
                modified_at_ns=stat.st_mtime_ns,
                component_type=ComponentType.WORKFLOW,
                touched='timestamp',
            )],
        )],
    )
    with Session(engine) as session:
        session.add(workflow)
        session.commit()
    return workflow_id


def test_synchronize_workflow_simulation_does_not_copy(workflow_repository):
    engine, working, archive = workflow_repository
    workflow_id = add_workflow(engine, working, 'w', '{"working": true}')

    result = repository.synchronize_workflow(workflow_id)

    assert result['allowed'] is True
    assert result['performed'] is False
    assert result['source_side'] == 'working'
    assert result['actions'][0]['action'] == 'copy'
    assert not (archive / 'nested' / 'workflow.json').exists()


def test_synchronize_workflow_executes_plan_and_updates_database(workflow_repository):
    engine, working, archive = workflow_repository
    workflow_id = add_workflow(engine, working, 'w', '{"working": true}')

    result = repository.synchronize_workflow(workflow_id, simulate=False)

    destination = archive / 'nested' / 'workflow.json'
    assert result['allowed'] is True
    assert result['performed'] is True
    assert destination.read_text(encoding='utf-8') == '{"working": true}'
    with Session(engine) as session:
        workflow = session.get(Workflow, workflow_id)
        assert workflow.deployment == 'synced'
        assert {component_set.where for component_set in workflow.component_sets} == {'w', 'a'}


def test_synchronize_workflow_rejects_erroneous_workflow(workflow_repository):
    engine, working, _archive = workflow_repository
    workflow_id = add_workflow(engine, working, 'w', '{}')
    with Session(engine) as session:
        workflow = session.get(Workflow, workflow_id)
        workflow.errors = ['invalid_config']
        session.add(workflow)
        session.commit()

    result = repository.synchronize_workflow(workflow_id, simulate=False)

    assert result['allowed'] is False
    assert result['performed'] is False
    assert result['errors'][0]['code'] == 'workflow_read_only'


def test_synchronize_archive_only_workflow_restores_working_copy(workflow_repository):
    engine, working, archive = workflow_repository
    workflow_id = add_workflow(engine, archive, 'a', '{"archived": true}')

    result = repository.synchronize_workflow(workflow_id, simulate=False)

    assert result['source_side'] == 'archive'
    assert (working / 'nested' / 'workflow.json').read_text(encoding='utf-8') == '{"archived": true}'


def test_synchronize_aborts_if_source_changes_after_planning(
    workflow_repository,
    monkeypatch: pytest.MonkeyPatch,
):
    engine, working, archive = workflow_repository
    workflow_id = add_workflow(engine, working, 'w', '{"working": true}')
    source = working / 'nested' / 'workflow.json'
    real_atomic_copy = repository.atomic_copy

    def change_then_copy(action):
        source.write_text('{"changed": true}', encoding='utf-8')
        real_atomic_copy(action)

    monkeypatch.setattr(repository, 'atomic_copy', change_then_copy)

    result = repository.synchronize_workflow(workflow_id, simulate=False)

    assert result['allowed'] is False
    assert result['errors'][0]['code'] == 'execution_failed'
    assert not (archive / 'nested' / 'workflow.json').exists()


def test_move_workflow_simulation_does_not_change_files(workflow_repository):
    engine, working, archive = workflow_repository
    workflow_id = add_workflow(engine, working, 'w', '{"working": true}')

    result = repository.move_workflow(workflow_id, DeploymentStatus.ARCHIVE)

    assert result['allowed'] is True
    assert result['performed'] is False
    assert result['actions'][0]['action'] == 'move'
    assert (working / 'nested' / 'workflow.json').exists()
    assert not (archive / 'nested' / 'workflow.json').exists()


def test_move_workflow_moves_file_and_updates_database(workflow_repository):
    engine, working, archive = workflow_repository
    workflow_id = add_workflow(engine, working, 'w', '{"working": true}')

    result = repository.move_workflow(
        workflow_id, DeploymentStatus.ARCHIVE, simulate=False)

    assert result['performed'] is True
    assert not (working / 'nested' / 'workflow.json').exists()
    assert (archive / 'nested' / 'workflow.json').read_text(encoding='utf-8') == '{"working": true}'
    with Session(engine) as session:
        workflow = session.get(Workflow, workflow_id)
        assert workflow.deployment == 'archive'
        assert [item.where for item in workflow.component_sets] == ['a']
