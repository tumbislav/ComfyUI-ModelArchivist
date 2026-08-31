# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: test_user_defined_types.py
# purpose: Tests for user-defined type and object persistence
# ---------------------------------------------------------------------------

from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlmodel import Session, create_engine

import backend.repository.repository as repository
from backend.exception import ArcException
from backend.repository.migrations import update_database_schema
from backend.repository.tables import (Collection, DeploymentStatus, UserDefinedObject,
                                       UserDefinedType, UserObjectEntry, UserObjectSet)


@pytest.fixture
def user_type_repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    engine = create_engine(f'sqlite:///{tmp_path / "user-types.db"}')
    update_database_schema(engine)
    monkeypatch.setattr(repository, '_engine', engine)
    monkeypatch.setattr(repository, '_config', SimpleNamespace(
        all_working=set(), all_archive=set(), model_types={}, read_only=False))
    repository._user_type_deletion_previews.clear()
    yield engine, tmp_path
    engine.dispose()


def type_input(tmp_path: Path, **changes) -> dict:
    values = {
        'name': 'Documents', 'short_name': 'Docs', 'object_class': 'file',
        'extensions': ['.TXT', 'md'],
        'working_dir': str(tmp_path / 'working'),
        'archive_dir': str(tmp_path / 'archive'),
        'icon': 'document', 'purpose': 'Text files', 'small': True,
        'size_limit': 1024 * 1024,
    }
    values.update(changes)
    return values


def add_object(engine, type_id: str, relative_path: str = 'nested/readme.txt',
               size: int = 100) -> str:
    item = UserDefinedObject(type_id=type_id, relative_path=relative_path,
                             display_name='Readme', purpose='', deployment='working',
                             size=size, modified_at_ns=10, touched='timestamp',
                             sets=[UserObjectSet(where='w', size=size, modified_at_ns=10,
                                entries=[UserObjectEntry(relative_path=relative_path,
                                                         entry_type='file', size=size,
                                                         modified_at_ns=10)])])
    with Session(engine) as session:
        session.add(item)
        session.commit()
        return item.id


def test_create_user_type_normalizes_extensions_and_creates_roots(user_type_repository):
    _engine, tmp_path = user_type_repository

    result = repository.create_user_type(type_input(tmp_path))

    assert result['extensions'] == ['txt', 'md']
    assert result['small'] is True
    assert Path(result['working_dir']).is_dir()
    assert Path(result['archive_dir']).is_dir()


def test_small_type_rejects_limit_over_one_mib(user_type_repository):
    _engine, tmp_path = user_type_repository

    with pytest.raises(ArcException) as exc_info:
        repository.create_user_type(type_input(tmp_path, size_limit=1024 * 1024 + 1))

    assert exc_info.value.code is ArcException.Code.INVALID_USER_TYPE


def test_user_type_rejects_long_short_name(user_type_repository):
    _engine, tmp_path = user_type_repository

    with pytest.raises(ArcException) as exc_info:
        repository.create_user_type(type_input(tmp_path, short_name='Too long!'))

    assert exc_info.value.code is ArcException.Code.INVALID_USER_TYPE


def test_user_type_locations_cannot_overlap(user_type_repository):
    _engine, tmp_path = user_type_repository

    with pytest.raises(ArcException) as exc_info:
        repository.create_user_type(type_input(
            tmp_path, archive_dir=str(tmp_path / 'working' / 'archive')))

    assert exc_info.value.code is ArcException.Code.INVALID_USER_TYPE


def test_populated_type_cannot_change_class_or_locations(user_type_repository):
    engine, tmp_path = user_type_repository
    item = repository.create_user_type(type_input(tmp_path))
    add_object(engine, item['id'])

    with pytest.raises(ArcException) as exc_info:
        repository.update_user_type(item['id'], type_input(
            tmp_path, object_class='folder', extensions=[]))

    assert exc_info.value.code is ArcException.Code.USER_TYPE_IN_USE


def test_lowering_limit_below_known_object_requires_confirmation(user_type_repository):
    engine, tmp_path = user_type_repository
    item = repository.create_user_type(type_input(tmp_path))
    add_object(engine, item['id'], size=900_000)
    changed = type_input(tmp_path, size_limit=800_000)

    with pytest.raises(ArcException) as exc_info:
        repository.update_user_type(item['id'], changed)
    changed['confirm_oversized'] = True
    result = repository.update_user_type(item['id'], changed)

    assert exc_info.value.code is ArcException.Code.CONFIRMATION_REQUIRED
    assert result['size_limit'] == 800_000


def test_update_user_object_changes_database_metadata(user_type_repository):
    engine, tmp_path = user_type_repository
    item = repository.create_user_type(type_input(tmp_path))
    object_id = add_object(engine, item['id'])

    result = repository.update_user_object(object_id, {
        'display_name': 'Notes', 'purpose': 'Reference', 'tags': ['text']})

    assert result['display_name'] == 'Notes'
    assert result['purpose'] == 'Reference'
    assert result['tags'] == ['text']


def test_user_object_search_and_lro_classification(user_type_repository):
    engine, tmp_path = user_type_repository
    item = repository.create_user_type(type_input(tmp_path))
    object_id = add_object(engine, item['id'])
    repository.update_user_object(object_id, {
        'display_name': 'Notes', 'purpose': '', 'tags': ['text']})

    found = repository.list_user_objects(item['id'], {
        'name_prefix': 'no', 'required_tags': ['text'], 'forbidden_tags': []})

    assert [value['id'] for value in found] == [object_id]
    assert repository.user_object_operation_requires_lro([object_id], 1024 * 1024) is False
    assert repository.user_object_operation_requires_lro([object_id], 1024 * 1024 + 1) is True


def test_user_object_participates_in_collection_uniqueness(user_type_repository):
    engine, tmp_path = user_type_repository
    item = repository.create_user_type(type_input(tmp_path))
    object_id = add_object(engine, item['id'])
    child = repository.create_collection({'name': 'Child', 'user_objects': [object_id]})

    with pytest.raises(ArcException) as exc_info:
        repository.create_collection({'name': 'Parent', 'user_objects': [object_id],
                                      'children': [child['id']]})

    assert exc_info.value.code is ArcException.Code.DUPLICATE_COLLECTION_MEMBER


def test_delete_type_removes_database_objects_and_empty_collections_only(
        user_type_repository):
    engine, tmp_path = user_type_repository
    item = repository.create_user_type(type_input(tmp_path))
    object_id = add_object(engine, item['id'])
    collection = repository.create_collection({'name': 'Only UDP',
                                               'user_objects': [object_id]})
    filesystem_file = Path(item['working_dir']) / 'nested' / 'readme.txt'
    filesystem_file.parent.mkdir()
    filesystem_file.write_text('preserved', encoding='utf-8')

    preview = repository.preview_user_type_deletion(item['id'])
    result = repository.delete_user_type(item['id'], preview['confirmation_id'])

    assert result['filesystem_changes'] == 0
    assert result['collections_deleted'] == 1
    assert filesystem_file.read_text(encoding='utf-8') == 'preserved'
    with Session(engine) as session:
        assert session.get(UserDefinedType, item['id']) is None
        assert session.get(UserDefinedObject, object_id) is None
        assert session.get(Collection, collection['id']) is None


def test_synchronize_file_object_simulates_then_copies(user_type_repository):
    engine, tmp_path = user_type_repository
    item = repository.create_user_type(type_input(tmp_path))
    object_id = add_object(engine, item['id'])
    source = Path(item['working_dir']) / 'nested' / 'readme.txt'
    source.parent.mkdir(parents=True)
    source.write_text('source contents', encoding='utf-8')

    simulation = repository.synchronize_user_object(object_id)
    result = repository.synchronize_user_object(object_id, False)

    destination = Path(item['archive_dir']) / 'nested' / 'readme.txt'
    assert simulation['allowed'] is True
    assert simulation['performed'] is False
    assert simulation['transfer_bytes'] == len(b'source contents')
    assert destination.read_text(encoding='utf-8') == 'source contents'
    assert result['performed'] is True
    assert repository.get_user_object(object_id)['deployment'] == 'synced'


def test_move_synced_file_removes_only_the_other_side(user_type_repository):
    engine, tmp_path = user_type_repository
    item = repository.create_user_type(type_input(tmp_path))
    object_id = add_object(engine, item['id'])
    working = Path(item['working_dir']) / 'nested' / 'readme.txt'
    archive = Path(item['archive_dir']) / 'nested' / 'readme.txt'
    working.parent.mkdir(parents=True)
    archive.parent.mkdir(parents=True)
    working.write_bytes(b'same')
    archive.write_bytes(b'same')
    archive.touch()

    result = repository.move_user_object(
        object_id, DeploymentStatus.ARCHIVE, False)

    assert result['performed'] is True
    assert not working.exists()
    assert archive.read_bytes() == b'same'
    assert repository.get_user_object(object_id)['deployment'] == 'archive'


def test_folder_sync_is_an_exact_recursive_mirror(user_type_repository):
    engine, tmp_path = user_type_repository
    item = repository.create_user_type(type_input(
        tmp_path, object_class='folder', extensions=[]))
    object_id = add_object(engine, item['id'], relative_path='dataset')
    working = Path(item['working_dir']) / 'dataset'
    archive = Path(item['archive_dir']) / 'dataset'
    (working / 'empty').mkdir(parents=True)
    (working / 'nested').mkdir()
    (working / 'nested' / 'current.bin').write_bytes(b'new')
    archive.mkdir(parents=True)
    (archive / 'obsolete.bin').write_bytes(b'old')

    result = repository.synchronize_user_object(object_id, False)

    assert result['performed'] is True
    assert (archive / 'empty').is_dir()
    assert (archive / 'nested' / 'current.bin').read_bytes() == b'new'
    assert not (archive / 'obsolete.bin').exists()


def test_operation_rechecks_hard_size_limit(user_type_repository):
    engine, tmp_path = user_type_repository
    item = repository.create_user_type(type_input(tmp_path, size_limit=3))
    object_id = add_object(engine, item['id'])
    source = Path(item['working_dir']) / 'nested' / 'readme.txt'
    source.parent.mkdir(parents=True)
    source.write_bytes(b'1234')

    result = repository.synchronize_user_object(object_id)

    assert result['allowed'] is False
    assert result['errors'][0]['code'] == 'over_size_limit'


def test_failed_move_does_not_delete_source(
        user_type_repository, monkeypatch: pytest.MonkeyPatch):
    engine, tmp_path = user_type_repository
    item = repository.create_user_type(type_input(tmp_path))
    object_id = add_object(engine, item['id'])
    source = Path(item['working_dir']) / 'nested' / 'readme.txt'
    source.parent.mkdir(parents=True)
    source.write_bytes(b'keep me')
    monkeypatch.setattr(repository, 'execute_file_action',
                        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError('disk error')))

    result = repository.move_user_object(
        object_id, DeploymentStatus.ARCHIVE, False)

    assert result['allowed'] is True
    assert result['performed'] is False
    assert result['warnings'][0]['code'] == 'filesystem_error'
    assert source.read_bytes() == b'keep me'
