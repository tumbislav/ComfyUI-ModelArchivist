# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: test_scan_persistence.py
# purpose: Regression tests for replacing persisted scan snapshots
# ---------------------------------------------------------------------------

import logging

import pytest
from sqlmodel import Session, create_engine, select

import backend.repository.repository as repo
from backend.repository.migrations import update_database_schema
from backend.repository.tables import (Model, ModelError, Workflow, ComponentSet, Component,
                                       UserDefinedType, UserDefinedObject,
                                       UserObjectSet, UserObjectEntry)


@pytest.fixture
def database(tmp_path, monkeypatch):
    engine = create_engine(f'sqlite:///{tmp_path / "rescan.db"}')
    update_database_schema(engine)
    monkeypatch.setattr(repo, '_engine', engine)
    monkeypatch.setattr(repo, '_logger', logging.getLogger('test.rescan'))
    yield engine
    engine.dispose()


@pytest.mark.parametrize('entity,save', [
    (Model, repo.save_scanned_model), (Workflow, repo.save_scanned_workflow)])
def test_rescan_replaces_component_sets(database, entity, save):
    for revision in range(3):
        item = entity(id='object-id', file_name='object.bin', internal_name='Object',
                      type='checkpoints', purpose='', relative_path='',
                      deployment='working', touched=str(revision), component_sets=[
            ComponentSet(where='w', primary_dir='working', examples_dir=None,
                         components=[Component(file_name='object.bin', size=revision,
                                               component_type='model', touched=str(revision))])])
        save(item, ['tag'])
        with Session(database) as session:
            stored = session.get(entity, 'object-id')
            assert stored.touched == str(revision)
            assert [tag.tag for tag in stored.tags] == ['tag']
            assert len(session.exec(select(ComponentSet)).all()) == 1
            components = session.exec(select(Component)).all()
            assert len(components) == 1
            assert components[0].size == revision


def test_rescan_replaces_user_object_sets_and_preserves_metadata(database):
    with Session(database) as session:
        session.add(UserDefinedType(id='type-id', name='Documents', short_name='Docs',
                                   object_class='file', working_dir='working',
                                   archive_dir='archive', icon='file'))
        session.commit()
    object_id = None
    for revision in range(3):
        item = UserDefinedObject(type_id='type-id', relative_path='object.txt',
                                 display_name='Original' if revision == 0 else 'Scanned',
                                 purpose='Keep me' if revision == 0 else '',
                                 deployment='working', touched=str(revision), size=revision,
                                 sets=[UserObjectSet(where='w', entries=[
                                     UserObjectEntry(relative_path='object.txt',
                                                     entry_type='file', size=revision)])])
        repo.save_scanned_user_object(item)
        with Session(database) as session:
            stored = session.exec(select(UserDefinedObject)).one()
            object_id = object_id or stored.id
            assert stored.id == object_id
            assert stored.display_name == 'Original'
            assert stored.purpose == 'Keep me'
            assert stored.touched == str(revision)
            assert len(session.exec(select(UserObjectSet)).all()) == 1
            entries = session.exec(select(UserObjectEntry)).all()
            assert len(entries) == 1
            assert entries[0].size == revision


def test_same_scan_merges_duplicate_model_without_inserting_parent(database):
    def scanned(file_name: str) -> Model:
        return Model(
            id='shared-hash', file_name=file_name, internal_name=file_name,
            type='vae', file_format='safetensors', relative_path='.',
            deployment='working', touched='same-scan', component_sets=[
                ComponentSet(
                    where='w', primary_dir='working', examples_dir=None,
                    components=[Component(
                        file_name=f'{file_name}.safetensors', component_type='model',
                        touched='same-scan')])])

    repo.save_scanned_model(scanned('first'), [])
    repo.save_scanned_model(scanned('second'), [])

    with Session(database) as session:
        models = session.exec(select(Model)).all()
        assert len(models) == 1
        assert ModelError.DUPLICATE_WORKING.value in models[0].errors
        assert len(session.exec(select(ComponentSet)).all()) == 1
        assert len(session.exec(select(Component)).all()) == 2


def test_later_model_rescan_clears_resolved_duplicate_error(database):
    def scanned(touched: str, errors: list[str]) -> Model:
        return Model(
            id='shared-hash', file_name='model', internal_name='Model',
            type='checkpoints', file_format='safetensors', relative_path='nested',
            deployment='working', touched=touched, errors=errors,
            component_sets=[ComponentSet(
                where='w', primary_dir='working', examples_dir=None,
                components=[Component(
                    file_name='model.safetensors', relative_path='nested',
                    component_type='model', touched=touched)])])

    repo.save_scanned_model(
        scanned('first-scan', [ModelError.DUPLICATE_WORKING.value]), [])
    repo.save_scanned_model(scanned('second-scan', []), [])

    with Session(database) as session:
        stored = session.get(Model, 'shared-hash')
        assert stored.errors == []
        assert stored.touched == 'second-scan'
