# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: test_workflow_id_repair.py
# purpose: Duplicate workflow UUID repair, pairing, and rollback regressions
# ---------------------------------------------------------------------------

import datetime
import json
import logging
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlmodel import Session, SQLModel, create_engine, select
from sqlalchemy.exc import SQLAlchemyError

import backend.filesystem_policy as filesystem
import backend.repository.repository as repo
from backend.files.scanner import Scanner
from backend.repository.tables import Collection, Workflow


@pytest.fixture
def duplicate_workflows(tmp_path, monkeypatch):
    working, archive = tmp_path / 'working', tmp_path / 'archive'
    working.mkdir()
    archive.mkdir()
    policy = filesystem.FilesystemPolicy((working,), (archive,), ())
    monkeypatch.setattr(filesystem, '_policy', policy)
    engine = create_engine('sqlite://')
    SQLModel.metadata.create_all(engine)
    with engine.connect() as connection:
        connection.exec_driver_sql('PRAGMA foreign_keys=ON')
    monkeypatch.setattr(repo, '_engine', engine)
    monkeypatch.setattr(repo, '_logger', logging.getLogger('archivist.database'))
    config = SimpleNamespace(read_only=False, workflow_folders=[(working, archive)])
    monkeypatch.setattr(repo, '_config', config)
    workflow_id = str(uuid4())
    paths = []
    for root in (working, archive):
        for filename in ('one.json', 'nested/two.json'):
            path = root / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({
                'id': workflow_id, 'nodes': [{'id': 17}], 'links': [[1, 17, 0]],
                'config': {'name': Path(filename).stem, 'tags': ['example']},
            }), encoding='utf-8')
            paths.append(path)
    scan(config.workflow_folders)
    with Session(engine) as session:
        workflow = session.get(Workflow, workflow_id)
        workflow.collections = [Collection(name='Favorites', purpose='')]
        session.add(workflow)
        session.commit()
    yield engine, config, workflow_id, paths
    engine.dispose()


def scan(pairs):
    scanner = Scanner(start_time=datetime.datetime.now(tz=datetime.timezone.utc))
    scanner.find_workflows(pairs)
    assert scanner.errors == []


def test_fix_splits_duplicates_and_preserves_synced_pairs_and_collections(duplicate_workflows):
    engine, config, old_id, paths = duplicate_workflows
    before = {path: json.loads(path.read_text(encoding='utf-8')) for path in paths}
    result = repo.fix_workflow_ids(old_id)
    assert result['id'] != old_id
    assert result['errors'] == []
    assert result['deployment'] == 'synced'
    assert result['relative_path'] == 'nested'
    ids = {}
    for path in paths:
        data = json.loads(path.read_text(encoding='utf-8'))
        assert str(UUID(data['id'])) == data['id']
        assert data['id'] != old_id
        assert {key: value for key, value in data.items() if key != 'id'} == {
            key: value for key, value in before[path].items() if key != 'id'}
        ids.setdefault(path.name, set()).add(data['id'])
    assert all(len(values) == 1 for values in ids.values())
    assert len(set.union(*ids.values())) == 2
    with Session(engine) as session:
        assert session.get(Workflow, old_id) is None
        workflows = session.exec(select(Workflow)).all()
        assert len(workflows) == 2
        for workflow in workflows:
            assert workflow.errors == []
            assert workflow.deployment == 'synced'
            assert [collection.name for collection in workflow.collections] == ['Favorites']
            assert [tag.tag for tag in workflow.tags] == ['example']
            assert all(len(component_set.components) == 1 for component_set in workflow.component_sets)
    scan(config.workflow_folders)
    with Session(engine) as session:
        assert all(not workflow.errors for workflow in session.exec(select(Workflow)).all())


@pytest.mark.parametrize('side', ['working', 'archive'])
def test_fix_handles_duplicates_on_only_one_side(duplicate_workflows, side):
    engine, config, old_id, paths = duplicate_workflows
    for path in paths:
        if side not in path.parts:
            path.unlink()
    result = repo.fix_workflow_ids(old_id)
    assert result['deployment'] == side
    with Session(engine) as session:
        workflows = session.exec(select(Workflow)).all()
        assert len(workflows) == 2
        assert all(workflow.deployment == side and not workflow.errors for workflow in workflows)


def test_write_failure_restores_files_and_original_database_row(duplicate_workflows, monkeypatch):
    engine, _, old_id, paths = duplicate_workflows
    before = {path: path.read_bytes() for path in paths}
    original_write = Path.write_bytes
    failed = False

    def fail_once(path, data):
        nonlocal failed
        if path == paths[2] and not failed:
            failed = True
            raise PermissionError('Injected write failure')
        return original_write(path, data)

    monkeypatch.setattr(Path, 'write_bytes', fail_once)
    with pytest.raises(PermissionError, match='Injected write failure'):
        repo.fix_workflow_ids(old_id)
    assert all(path.read_bytes() == content for path, content in before.items())
    with Session(engine) as session:
        assert [workflow.id for workflow in session.exec(select(Workflow)).all()] == [old_id]
        assert session.get(Workflow, old_id).collections[0].name == 'Favorites'


def test_repository_read_only_blocks_id_repair(duplicate_workflows):
    _, config, old_id, paths = duplicate_workflows
    before = {path: path.read_bytes() for path in paths}
    config.read_only = True
    with pytest.raises(repo.WorkflowIdentityError) as error:
        repo.fix_workflow_ids(old_id)
    assert error.value.code == 'filesystem_read_only'
    assert all(path.read_bytes() == content for path, content in before.items())


def test_database_failure_restores_original_file_ids(duplicate_workflows, monkeypatch):
    engine, _, old_id, paths = duplicate_workflows
    before = {path: path.read_bytes() for path in paths}

    def fail_commit(session):
        raise SQLAlchemyError('Injected database failure')

    monkeypatch.setattr(Session, 'commit', fail_commit)
    with pytest.raises(SQLAlchemyError, match='Injected database failure'):
        repo.fix_workflow_ids(old_id)
    assert all(path.read_bytes() == content for path, content in before.items())
    with Session(engine) as session:
        assert [workflow.id for workflow in session.exec(select(Workflow)).all()] == [old_id]
        assert session.get(Workflow, old_id).collections[0].name == 'Favorites'


def test_stale_duplicate_error_does_not_change_a_single_remaining_file(duplicate_workflows):
    _, _, old_id, paths = duplicate_workflows
    for path in paths[1:]:
        path.unlink()
    before = paths[0].read_bytes()
    with pytest.raises(repo.WorkflowIdentityError) as error:
        repo.fix_workflow_ids(old_id)
    assert error.value.code == 'workflow_not_duplicate'
    assert paths[0].read_bytes() == before
