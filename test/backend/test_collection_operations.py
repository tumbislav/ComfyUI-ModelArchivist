# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: test_collection_operations.py
# purpose: Tests for collection creation and structural validation
# ---------------------------------------------------------------------------

from pathlib import Path

import pytest
from sqlmodel import Session, create_engine

import backend.repository.repository as repository
from backend.exception import ArcException
from backend.repository.migrations import update_database_schema
from backend.repository.tables import Collection, DeploymentStatus, Model, Workflow


MODEL_ID = 'a' * 64
WORKFLOW_ID = '11111111-1111-1111-1111-111111111111'


def member_plan(object_type: str, object_id: str, simulate: bool,
                allowed: bool = True, performed: bool | None = None) -> dict:
    return {
        'operation': 'test',
        'object_type': object_type,
        'object_id': object_id,
        'simulate': simulate,
        'allowed': allowed,
        'performed': allowed and not simulate if performed is None else performed,
        'source_side': None,
        'actions': [{'object_id': object_id}],
        'errors': [] if allowed else [{'code': 'blocked', 'message': 'blocked'}],
        'warnings': [],
    }


@pytest.fixture
def collection_repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    engine = create_engine(f'sqlite:///{tmp_path / "collections.db"}')
    update_database_schema(engine)
    monkeypatch.setattr(repository, '_engine', engine)
    with Session(engine) as session:
        session.add(Model(id=MODEL_ID, file_name='model', internal_name='Model',
                          type='checkpoints', relative_path='', deployment='working',
                          touched='timestamp'))
        session.add(Workflow(id=WORKFLOW_ID, file_name='workflow', internal_name='Workflow',
                             purpose='', relative_path='', deployment='working',
                             touched='timestamp'))
        session.commit()
    yield engine
    engine.dispose()


def test_create_collection_with_direct_members(collection_repository):
    result = repository.create_collection({
        'name': 'Direct',
        'purpose': 'Test',
        'tags': ['favorite'],
        'models': [MODEL_ID],
        'workflows': [{'id': WORKFLOW_ID}],
    })

    assert result['name'] == 'Direct'
    with Session(collection_repository) as session:
        collection = session.get(Collection, result['id'])
        assert {model.id for model in collection.models} == {MODEL_ID}
        assert {workflow.id for workflow in collection.workflows} == {WORKFLOW_ID}
        assert {tag.tag for tag in collection.tags} == {'favorite'}


def test_update_collection_models_adds_and_removes_selected_models(collection_repository):
    second_id = 'b' * 64
    with Session(collection_repository) as session:
        session.add(Model(id=second_id, file_name='second', internal_name='Second',
                          type='checkpoints', relative_path='', deployment='working',
                          touched='timestamp'))
        session.commit()
    collection = repository.create_collection({
        'name': 'Models', 'purpose': '', 'models': [MODEL_ID]
    })

    repository.update_collection_models(collection['id'], [second_id], True)
    repository.update_collection_models(collection['id'], [MODEL_ID], False)

    with Session(collection_repository) as session:
        stored = session.get(Collection, collection['id'])
        assert {model.id for model in stored.models} == {second_id}


def test_update_collection_workflows_adds_and_removes_selected_workflows(
        collection_repository):
    second_id = '22222222-2222-2222-2222-222222222222'
    with Session(collection_repository) as session:
        session.add(Workflow(id=second_id, file_name='second', internal_name='Second',
                             purpose='', relative_path='', deployment='working',
                             touched='timestamp'))
        session.commit()
    collection = repository.create_collection({
        'name': 'Workflows', 'purpose': '', 'workflows': [WORKFLOW_ID]})

    repository.update_collection_workflows(collection['id'], [second_id], True)
    repository.update_collection_workflows(collection['id'], [WORKFLOW_ID], False)

    with Session(collection_repository) as session:
        stored = session.get(Collection, collection['id'])
        assert {workflow.id for workflow in stored.workflows} == {second_id}


def test_create_collection_rejects_empty_collection(collection_repository):
    with pytest.raises(ArcException) as exc_info:
        repository.create_collection({'name': 'Empty', 'purpose': ''})

    assert exc_info.value.code is ArcException.Code.EMPTY_COLLECTION


def test_create_collection_rejects_unknown_member(collection_repository):
    with pytest.raises(ArcException) as exc_info:
        repository.create_collection({'name': 'Unknown', 'models': ['missing']})

    assert exc_info.value.code is ArcException.Code.UNKNOWN_MODEL


def test_create_collection_rejects_direct_and_nested_duplicate(collection_repository):
    child = repository.create_collection({'name': 'Child', 'models': [MODEL_ID]})

    with pytest.raises(ArcException) as exc_info:
        repository.create_collection({
            'name': 'Parent',
            'models': [MODEL_ID],
            'children': [child['id']],
        })

    assert exc_info.value.code is ArcException.Code.DUPLICATE_COLLECTION_MEMBER


def test_create_collection_rejects_duplicate_between_child_branches(collection_repository):
    first = repository.create_collection({'name': 'First', 'models': [MODEL_ID]})
    second = repository.create_collection({'name': 'Second', 'models': [MODEL_ID]})

    with pytest.raises(ArcException) as exc_info:
        repository.create_collection({
            'name': 'Parent',
            'children': [first['id'], second['id']],
        })

    assert exc_info.value.code is ArcException.Code.DUPLICATE_COLLECTION_MEMBER


def test_collection_can_have_multiple_unrelated_parents(collection_repository):
    child = repository.create_collection({'name': 'Shared child', 'models': [MODEL_ID]})

    first = repository.create_collection({'name': 'First parent', 'children': [child['id']]})
    second = repository.create_collection({'name': 'Second parent', 'children': [child['id']]})

    assert first['id'] != second['id']


def test_list_collections_includes_shallow_parent_summaries(collection_repository):
    child = repository.create_collection({'name': 'Child', 'models': [MODEL_ID]})
    second = repository.create_collection({'name': 'Zulu parent', 'children': [child['id']]})
    first = repository.create_collection({'name': 'Alpha parent', 'children': [child['id']]})

    collections = repository.list_collections(ordered=True)

    listed_child = next(item for item in collections if item['id'] == child['id'])
    assert listed_child['parents'] == [
        {'id': first['id'], 'name': 'Alpha parent'},
        {'id': second['id'], 'name': 'Zulu parent'},
    ]
    assert all('parents' not in parent for parent in listed_child['parents'])


@pytest.mark.parametrize('member_deployment, expected', [
    (DeploymentStatus.WORKING, DeploymentStatus.WORKING),
    (DeploymentStatus.ARCHIVE, DeploymentStatus.ARCHIVE),
    (DeploymentStatus.SYNCED, DeploymentStatus.SYNCED),
    (DeploymentStatus.MISMATCH, DeploymentStatus.MIXED),
])
def test_get_collection_reports_uniform_transitive_deployment(
        collection_repository, member_deployment: DeploymentStatus,
        expected: DeploymentStatus):
    child = repository.create_collection({'name': 'Child', 'models': [MODEL_ID]})
    parent = repository.create_collection({
        'name': 'Parent', 'workflows': [WORKFLOW_ID], 'children': [child['id']]})
    with Session(collection_repository) as session:
        session.get(Model, MODEL_ID).deployment = member_deployment
        session.get(Workflow, WORKFLOW_ID).deployment = member_deployment
        session.commit()

    result = repository.get_collection(parent['id'])

    assert result['deployment'] == expected


def test_get_collection_reports_mixed_transitive_deployment(collection_repository):
    child = repository.create_collection({'name': 'Child', 'models': [MODEL_ID]})
    parent = repository.create_collection({
        'name': 'Parent', 'workflows': [WORKFLOW_ID], 'children': [child['id']]})
    with Session(collection_repository) as session:
        session.get(Model, MODEL_ID).deployment = DeploymentStatus.ARCHIVE
        session.get(Workflow, WORKFLOW_ID).deployment = DeploymentStatus.WORKING
        session.commit()

    result = repository.get_collection(parent['id'])

    assert result['deployment'] == DeploymentStatus.MIXED
    assert {item['id'] for item in result['models']} == set()
    assert {item['id'] for item in result['workflows']} == {WORKFLOW_ID}
    assert {item['id'] for item in result['children']} == {child['id']}


def test_get_collection_rejects_unknown_id(collection_repository):
    with pytest.raises(ArcException) as exc_info:
        repository.get_collection('missing')

    assert exc_info.value.code is ArcException.Code.UNKNOWN_COLLECTION


def test_create_collection_rejects_cycle_in_existing_child_graph(collection_repository):
    first = repository.create_collection({'name': 'First', 'models': [MODEL_ID]})
    second = repository.create_collection({'name': 'Second', 'workflows': [WORKFLOW_ID]})
    with Session(collection_repository) as session:
        first_collection = session.get(Collection, first['id'])
        second_collection = session.get(Collection, second['id'])
        first_collection.children.append(second_collection)
        second_collection.children.append(first_collection)
        session.add(first_collection)
        session.add(second_collection)
        session.commit()

    with pytest.raises(ArcException) as exc_info:
        repository.create_collection({'name': 'Parent', 'children': [first['id']]})

    assert exc_info.value.code is ArcException.Code.COLLECTION_CYCLE


def test_update_collection_changes_properties_but_preserves_id(collection_repository):
    original = repository.create_collection({'name': 'Original', 'models': [MODEL_ID]})

    result = repository.update_collection(original['id'], {
        'id': original['id'],
        'name': 'Updated',
        'purpose': 'New purpose',
        'tags': ['updated'],
        'workflows': [WORKFLOW_ID],
    })

    assert result == {'id': original['id'], 'name': 'Updated', 'parents': []}
    with Session(collection_repository) as session:
        collection = session.get(Collection, original['id'])
        assert collection.purpose == 'New purpose'
        assert collection.models == []
        assert {item.id for item in collection.workflows} == {WORKFLOW_ID}
        assert {tag.tag for tag in collection.tags} == {'updated'}


def test_update_collection_rejects_id_change(collection_repository):
    original = repository.create_collection({'name': 'Original', 'models': [MODEL_ID]})

    with pytest.raises(ArcException) as exc_info:
        repository.update_collection(original['id'], {
            'id': 'different',
            'name': 'Updated',
            'models': [MODEL_ID],
        })

    assert exc_info.value.code is ArcException.Code.INVALID_COLLECTION


def test_update_collection_rejects_empty_result(collection_repository):
    original = repository.create_collection({'name': 'Original', 'models': [MODEL_ID]})

    with pytest.raises(ArcException) as exc_info:
        repository.update_collection(original['id'], {'name': 'Empty'})

    assert exc_info.value.code is ArcException.Code.EMPTY_COLLECTION


def test_update_collection_validates_affected_parent_trees(collection_repository):
    model_child = repository.create_collection({'name': 'Model child', 'models': [MODEL_ID]})
    changing_child = repository.create_collection({
        'name': 'Changing child', 'workflows': [WORKFLOW_ID]})
    repository.create_collection({
        'name': 'Parent', 'children': [model_child['id'], changing_child['id']]})

    with pytest.raises(ArcException) as exc_info:
        repository.update_collection(changing_child['id'], {
            'name': 'Changing child',
            'models': [MODEL_ID],
        })

    assert exc_info.value.code is ArcException.Code.DUPLICATE_COLLECTION_MEMBER
    with Session(collection_repository) as session:
        unchanged = session.get(Collection, changing_child['id'])
        assert {item.id for item in unchanged.workflows} == {WORKFLOW_ID}


def test_update_collection_rejects_new_cycle(collection_repository):
    child = repository.create_collection({'name': 'Child', 'models': [MODEL_ID]})
    parent = repository.create_collection({'name': 'Parent', 'children': [child['id']]})

    with pytest.raises(ArcException) as exc_info:
        repository.update_collection(child['id'], {
            'name': 'Child',
            'models': [MODEL_ID],
            'children': [parent['id']],
        })

    assert exc_info.value.code is ArcException.Code.COLLECTION_CYCLE


def test_delete_top_level_collection_preserves_its_members(collection_repository):
    child = repository.create_collection({'name': 'Child', 'models': [MODEL_ID]})
    parent = repository.create_collection({'name': 'Parent', 'children': [child['id']]})

    result = repository.delete_collection(parent['id'])

    assert result == parent
    with Session(collection_repository) as session:
        assert session.get(Collection, parent['id']) is None
        assert session.get(Collection, child['id']) is not None
        assert session.get(Model, MODEL_ID) is not None


def test_delete_nested_collection_when_parent_remains_nonempty(collection_repository):
    child = repository.create_collection({'name': 'Child', 'workflows': [WORKFLOW_ID]})
    parent = repository.create_collection({
        'name': 'Parent', 'models': [MODEL_ID], 'children': [child['id']]})

    repository.delete_collection(child['id'])

    with Session(collection_repository) as session:
        stored_parent = session.get(Collection, parent['id'])
        assert stored_parent.children == []
        assert {item.id for item in stored_parent.models} == {MODEL_ID}


def test_delete_collection_rejects_emptying_parent(collection_repository):
    child = repository.create_collection({'name': 'Child', 'models': [MODEL_ID]})
    parent = repository.create_collection({'name': 'Parent', 'children': [child['id']]})

    with pytest.raises(ArcException) as exc_info:
        repository.delete_collection(child['id'])

    assert exc_info.value.code is ArcException.Code.EMPTY_COLLECTION
    with Session(collection_repository) as session:
        assert session.get(Collection, child['id']) is not None
        assert session.get(Collection, parent['id']) is not None


def test_delete_collection_checks_every_parent(collection_repository):
    child = repository.create_collection({'name': 'Child', 'workflows': [WORKFLOW_ID]})
    safe_parent = repository.create_collection({
        'name': 'Safe parent', 'models': [MODEL_ID], 'children': [child['id']]})
    repository.create_collection({'name': 'Empty parent', 'children': [child['id']]})

    with pytest.raises(ArcException) as exc_info:
        repository.delete_collection(child['id'])

    assert exc_info.value.code is ArcException.Code.EMPTY_COLLECTION
    with Session(collection_repository) as session:
        assert session.get(Collection, child['id']) is not None
        assert session.get(Collection, safe_parent['id']) is not None


def test_delete_collection_rejects_unknown_id(collection_repository):
    with pytest.raises(ArcException) as exc_info:
        repository.delete_collection('missing')

    assert exc_info.value.code is ArcException.Code.UNKNOWN_COLLECTION


def test_synchronize_collection_includes_transitive_leaves(
        collection_repository, monkeypatch: pytest.MonkeyPatch):
    child = repository.create_collection({'name': 'Child', 'models': [MODEL_ID]})
    parent = repository.create_collection({
        'name': 'Parent', 'workflows': [WORKFLOW_ID], 'children': [child['id']]})
    calls = []

    def synchronize_model(id: str, simulate: bool = True) -> dict:
        calls.append(('model', id, simulate))
        return member_plan('model', id, simulate)

    def synchronize_workflow(id: str, simulate: bool = True) -> dict:
        calls.append(('workflow', id, simulate))
        return member_plan('workflow', id, simulate)

    monkeypatch.setattr(repository, 'synchronize_model', synchronize_model)
    monkeypatch.setattr(repository, 'synchronize_workflow', synchronize_workflow)

    result = repository.synchronize_collection(parent['id'])

    assert result['allowed'] is True
    assert result['performed'] is False
    assert calls == [('model', MODEL_ID, True), ('workflow', WORKFLOW_ID, True)]
    assert {member['object_id'] for member in result['members']} == {
        MODEL_ID, WORKFLOW_ID}
    assert len(result['actions']) == 2


def test_collection_operation_preflights_every_member_before_execution(
        collection_repository, monkeypatch: pytest.MonkeyPatch):
    collection = repository.create_collection({
        'name': 'Mixed', 'models': [MODEL_ID], 'workflows': [WORKFLOW_ID]})
    calls = []

    def synchronize_model(id: str, simulate: bool = True) -> dict:
        calls.append(('model', simulate))
        return member_plan('model', id, simulate)

    def synchronize_workflow(id: str, simulate: bool = True) -> dict:
        calls.append(('workflow', simulate))
        return member_plan('workflow', id, simulate, allowed=False)

    monkeypatch.setattr(repository, 'synchronize_model', synchronize_model)
    monkeypatch.setattr(repository, 'synchronize_workflow', synchronize_workflow)

    result = repository.synchronize_collection(collection['id'], simulate=False)

    assert result['allowed'] is False
    assert result['performed'] is False
    assert calls == [('model', True), ('workflow', True)]
    assert result['errors'][0]['code'] == 'member_validation_failed'


def test_move_collection_forwards_direction_and_executes_all_members(
        collection_repository, monkeypatch: pytest.MonkeyPatch):
    collection = repository.create_collection({
        'name': 'Mixed', 'models': [MODEL_ID], 'workflows': [WORKFLOW_ID]})
    calls = []

    def move_model(id: str, destination: DeploymentStatus,
                   simulate: bool = True) -> dict:
        calls.append(('model', destination, simulate))
        return member_plan('model', id, simulate)

    def move_workflow(id: str, destination: DeploymentStatus,
                      simulate: bool = True) -> dict:
        calls.append(('workflow', destination, simulate))
        return member_plan('workflow', id, simulate)

    monkeypatch.setattr(repository, 'move_model', move_model)
    monkeypatch.setattr(repository, 'move_workflow', move_workflow)

    result = repository.move_collection(
        collection['id'], DeploymentStatus.ARCHIVE, simulate=False)

    assert result['allowed'] is True
    assert result['performed'] is True
    assert calls == [
        ('model', DeploymentStatus.ARCHIVE, True),
        ('workflow', DeploymentStatus.ARCHIVE, True),
        ('model', DeploymentStatus.ARCHIVE, False),
        ('workflow', DeploymentStatus.ARCHIVE, False),
    ]


def test_collection_execution_stops_and_reports_partial_failure(
        collection_repository, monkeypatch: pytest.MonkeyPatch):
    collection = repository.create_collection({
        'name': 'Mixed', 'models': [MODEL_ID], 'workflows': [WORKFLOW_ID]})
    calls = []

    def synchronize_model(id: str, simulate: bool = True) -> dict:
        calls.append(('model', simulate))
        if not simulate:
            return member_plan('model', id, False, performed=False)
        return member_plan('model', id, True)

    def synchronize_workflow(id: str, simulate: bool = True) -> dict:
        calls.append(('workflow', simulate))
        return member_plan('workflow', id, simulate)

    monkeypatch.setattr(repository, 'synchronize_model', synchronize_model)
    monkeypatch.setattr(repository, 'synchronize_workflow', synchronize_workflow)

    result = repository.synchronize_collection(collection['id'], simulate=False)

    assert result['allowed'] is False
    assert result['performed'] is False
    assert calls == [('model', True), ('workflow', True), ('model', False)]
    assert result['warnings'][0]['code'] == 'partial_execution'


def test_move_collection_rejects_invalid_destination(collection_repository):
    collection = repository.create_collection({'name': 'Models', 'models': [MODEL_ID]})

    result = repository.move_collection(collection['id'], 'somewhere')

    assert result['allowed'] is False
    assert result['errors'][0]['code'] == 'invalid_destination'


def test_collection_operation_rejects_unknown_collection(collection_repository):
    result = repository.synchronize_collection('missing')

    assert result['allowed'] is False
    assert result['errors'][0]['code'] == 'unknown_collection'
