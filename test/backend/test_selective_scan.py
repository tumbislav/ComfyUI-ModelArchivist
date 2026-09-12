# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: test_selective_scan.py
# purpose: Selective scan isolation, scope validation, and repository statistics
# ---------------------------------------------------------------------------

import logging
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlmodel import Session, create_engine, select

import backend.files.scanner as scanner_module
import backend.repository.repository as repo
from backend.repository.migrations import update_database_schema
from backend.repository.tables import Model, Workflow, UserDefinedType, UserDefinedObject, Collection
from backend.server.routers import admin


@pytest.fixture
def database(tmp_path, monkeypatch):
    engine = create_engine(f'sqlite:///{tmp_path / "repository.db"}')
    update_database_schema(engine)
    monkeypatch.setattr(repo, '_engine', engine)
    monkeypatch.setattr(repo, '_logger', logging.getLogger('test.selective'))
    with Session(engine) as session:
        for type_id in ('first', 'second'):
            session.add(UserDefinedType(id=type_id, name=type_id, short_name=type_id,
                                       object_class='file', working_dir=f'w/{type_id}',
                                       archive_dir=f'a/{type_id}', icon='file'))
            session.add(Model(id=type_id, file_name=type_id, internal_name=type_id,
                              type=type_id, relative_path='', deployment='working', touched='old'))
            session.add(UserDefinedObject(id=type_id, type_id=type_id, relative_path=type_id,
                                          display_name=type_id, deployment='archive', touched='old'))
        session.add(Workflow(id='workflow', file_name='workflow', internal_name='workflow', purpose='',
                             relative_path='', deployment='synced', touched='old'))
        session.commit()
    yield engine
    engine.dispose()


@pytest.mark.parametrize('scope,type_id,models,users,workflows', [
    ('models', 'first', {'second'}, {'first', 'second'}, {'workflow'}),
    ('models', ['first'], {'second'}, {'first', 'second'}, {'workflow'}),
    ('models', ['first', 'second'], set(), {'first', 'second'}, {'workflow'}),
    ('models', None, set(), {'first', 'second'}, {'workflow'}),
    ('user_objects', 'first', {'first', 'second'}, {'second'}, {'workflow'}),
    ('user_objects', ['first'], {'first', 'second'}, {'second'}, {'workflow'}),
    ('user_objects', ['first', 'second'], {'first', 'second'}, set(), {'workflow'}),
    ('user_objects', None, {'first', 'second'}, set(), {'workflow'}),
    ('workflows', None, {'first', 'second'}, {'first', 'second'}, set()),
    ('all', None, set(), set(), set()),
])
def test_cleanup_only_removes_unseen_objects_in_scope(database, scope, type_id,
                                                     models, users, workflows):
    with Session(database) as session:
        session.add(Model(id='retained', file_name='retained', internal_name='retained',
                          type='first', relative_path='', deployment='working', touched='new'))
        session.commit()

    repo.scan_cleanup('new', scope, type_id)

    with Session(database) as session:
        assert set(session.exec(select(Model.id)).all()) == models | {'retained'}
        assert set(session.exec(select(UserDefinedObject.id)).all()) == users
        assert set(session.exec(select(Workflow.id)).all()) == workflows


@pytest.mark.parametrize('scope,type_id,expected', [
    ('all', None, ['find_models', 'find_models', 'find_workflows', 'find_user_objects', 'cleanup']),
    ('models', 'first', ['find_models', 'cleanup']),
    ('workflows', None, ['find_workflows', 'cleanup']),
    ('user_objects', 'second', ['find_user_objects', 'cleanup']),
])
def test_scanner_only_launches_selected_workers(monkeypatch, scope, type_id, expected):
    jobs = []

    class ThreadStub:
        def __init__(self, target, args):
            jobs.append((target.__name__, args))

        def start(self):
            pass

    monkeypatch.setattr(scanner_module, 'Thread', ThreadStub)
    monkeypatch.setattr(scanner_module, 'get_config', lambda: SimpleNamespace(
        model_folders={'first': [('w1', 'a1')], 'second': [('w2', 'a2')]},
        workflow_folders=[('ww', 'aw')]))
    monkeypatch.setattr(repo, 'user_types_for_scan', lambda: [{'id': 'first'}, {'id': 'second'}])
    scanner = scanner_module.Scanner()
    scanner.start(False, scope, type_id)

    assert [name for name, _ in jobs] == expected
    if scope == 'models':
        assert jobs[0][1][0] == 'first'
    if scope == 'user_objects':
        assert jobs[0][1][0] == [{'id': 'second'}]
    assert scanner.progress()['scope'] == scope
    assert scanner.progress()['type_id'] == type_id


def test_summary_counts_disjoint_locations_and_nested_collection_errors(database):
    with Session(database) as session:
        model = session.get(Model, 'first')
        model.deployment = 'synced'
        model.errors = ['metadata_rename', 'unreadable']
        second = session.get(Model, 'second')
        second.deployment = 'mismatch'
        child = Collection(id='child', name='Child', purpose='', models=[model])
        parent = Collection(id='parent', name='Parent', purpose='', children=[child], models=[model])
        session.add_all([model, second, child, parent])
        session.commit()

    summary = repo.repository_summary()
    assert summary['models'] == dict(working=0, archive=0, synced=1, total=2, errors=1)
    assert summary['workflows'] == dict(working=0, archive=0, synced=1, total=1, errors=0)
    assert summary['user_objects'] == dict(working=0, archive=2, synced=0, total=2, errors=0)
    assert summary['collections'] == dict(working=0, archive=0, synced=2, total=2, errors=2)


@pytest.mark.parametrize('scope,type_id,startup', [
    ('models', 'missing', False), ('workflows', 'first', False),
    ('user_objects', 'missing', False), ('all', 'first', False),
    ('models', 'first', True), ('collections', None, False),
])
def test_invalid_scopes_rejected_before_dispatch(monkeypatch, scope, type_id, startup):
    monkeypatch.setattr(admin, 'get_config', lambda: SimpleNamespace(
        read_only=False, setup_required=False, model_folders={'first': []}))
    monkeypatch.setattr(admin, 'user_types_for_scan', lambda: [{'id': 'first'}])
    monkeypatch.setattr(admin, 'submit_scan', lambda *args: pytest.fail('must not submit'))
    with pytest.raises(HTTPException) as error:
        admin.start_scan(scope=scope, type_id=type_id, startup=startup)
    assert error.value.status_code == 422
    assert error.value.detail['code'] == 'invalid_scan_scope'
