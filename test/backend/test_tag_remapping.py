# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: test_tag_remapping.py
# purpose: Tag normalization, merge semantics, and filesystem recovery regressions
# ---------------------------------------------------------------------------

import json
import asyncio
import logging
import shutil
import subprocess
from types import SimpleNamespace

import pytest
from sqlmodel import Session, create_engine, select

from backend.exception import ArcException
from backend.repository.migrations import update_database_schema
from backend.repository.tables import (Tag, Model, Workflow, Collection, UserDefinedType,
                                       UserDefinedObject, Component, ComponentSet, ComponentType)
from backend.repository import tag_operations as operations
from backend.repository import repository
from backend.tags import normalize_tag, edited_tags, browser_tag_rules


@pytest.fixture
def tagged_repository(tmp_path, monkeypatch):
    engine = create_engine(f'sqlite:///{tmp_path / "tags.db"}')
    update_database_schema(engine)
    monkeypatch.setattr(repository, '_engine', engine)
    monkeypatch.setattr(repository, '_logger', logging.getLogger('test.tags'))
    monkeypatch.setattr(repository, '_config', SimpleNamespace(read_only=False, model_types={}))

    def components(side, workflow=False):
        root = tmp_path / side
        root.mkdir(exist_ok=True)
        name = 'flow.json' if workflow else 'model.archivist.json'
        path = root / name
        data = {'config': {'tags': ['B'], 'purpose': 'keep'}} if workflow else {'tags': ['A', 'B'], 'sha256': 'keep'}
        path.write_text(json.dumps(data), encoding='utf-8')
        stat = path.stat()
        component = Component(file_name=name, relative_path='', touched='timestamp',
                              size=stat.st_size, modified_at_ns=stat.st_mtime_ns,
                              component_type=ComponentType.WORKFLOW if workflow else ComponentType.METADATA)
        result = ComponentSet(where=side, primary_dir=str(root), components=[component])
        if not workflow:
            for suffix in ('.metadata.json', '.rgthree.json'):
                foreign = root / ('model' + suffix)
                foreign.write_text('{"tags":["A"],"foreign":true}', encoding='utf-8')
                result.components.append(Component(file_name=foreign.name, relative_path='',
                    touched='timestamp', size=foreign.stat().st_size, modified_at_ns=foreign.stat().st_mtime_ns,
                    component_type=ComponentType.METADATA))
        return result

    with Session(engine) as session:
        a, b = Tag(tag='A'), Tag(tag='B')
        model = Model(id='a' * 64, file_name='model', internal_name='Model', type='checkpoints',
                      relative_path='', touched='timestamp', deployment='synced', tags=[a, b],
                      component_sets=[components('w'), components('a')])
        workflow = Workflow(id='flow', file_name='flow', internal_name='Flow', purpose='',
                            relative_path='', touched='timestamp', deployment='synced', tags=[b],
                            component_sets=[components('w', True), components('a', True)])
        kind = UserDefinedType(id='docs', name='Documents', short_name='Docs', object_class='file',
                               working_dir='/docs-w', archive_dir='/docs-a', icon='document')
        obj = UserDefinedObject(id='doc', type=kind, relative_path='doc.txt', display_name='Doc',
                                 deployment='working', touched='timestamp', tags=[a])
        collection = Collection(id='collection', name='Collection', purpose='', models=[model], tags=[a, b])
        session.add_all([model, workflow, obj, collection])
        session.commit()
    yield engine, tmp_path
    engine.dispose()


def assignments(engine):
    with Session(engine) as session:
        return {kind.__name__: {tag.tag for tag in session.exec(select(kind)).first().tags}
                for kind in (Model, Workflow, UserDefinedObject, Collection)}


@pytest.mark.parametrize('value,expected', [
    ('Landscape', 'Landscape'), ('landscape', 'landscape'), ('class', 'class'),
    ('_model  2 ', '_model  2'), ('蛇', '蛇'), ('école', 'école'), ('ﬁnal', 'final'),
    ('1model', '1model'), (' model', None), ('model\t2', None), ('model\n', None),
    ('model-name', 'model-name'), ('🐍', None), ('', None), ('   ', None), ('__proto__', '__proto__'),
    ('123', '123'), ('1', '1'), ('2:model-v1', '2:model-v1'), ('a--::b', 'a--::b'),
    ('a: b ', 'a: b'), (':tag', None), ('-tag', None), ('tag:', None), ('tag-', None),
    ('tag: ', None), ('tag- ', None), ('a：b', None), ('a﹕b', None),
    ('a－b', None), ('a–b', None), ('a—b', None), ('a−b', None), ('１tag', None)])
def test_tag_validation(value, expected):
    assert normalize_tag(value) == expected


def test_legacy_tags_survive_unrelated_edits():
    assert edited_tags(['old/invalid', 'valid'], ['old/invalid']) == ['old/invalid', 'valid']
    with pytest.raises(ArcException) as error:
        edited_tags(['new/invalid'])
    assert error.value.code == ArcException.Code.INVALID_TAG
    assert browser_tag_rules()['unicode_version']


def test_usage_counts_direct_objects_in_all_categories(tagged_repository):
    engine, _ = tagged_repository
    assert operations.tag_usage(engine) == [
        {'tag': 'A', 'models': 1, 'workflows': 0, 'user_objects': 1, 'collections': 1},
        {'tag': 'B', 'models': 1, 'workflows': 1, 'user_objects': 0, 'collections': 1}]


def test_remap_is_simultaneous_and_updates_only_owned_metadata(tagged_repository):
    engine, root = tagged_repository
    result = operations.remap_tags(engine, {'A': 'B', 'B': 'C'}, False)
    assert result['errors'] == []
    assert result['applied'] == ['A', 'B']
    assert assignments(engine) == {'Model': {'B', 'C'}, 'Workflow': {'C'},
                                    'UserDefinedObject': {'B'}, 'Collection': {'B', 'C'}}
    for side in ('w', 'a'):
        data = json.loads((root / side / 'model.archivist.json').read_text())
        assert data == {'tags': ['B', 'C'], 'sha256': 'keep'}
        flow = json.loads((root / side / 'flow.json').read_text())
        assert flow == {'config': {'tags': ['C'], 'purpose': 'keep'}}
        for suffix in ('.metadata.json', '.rgthree.json'):
            assert (root / side / ('model' + suffix)).read_text() == '{"tags":["A"],"foreign":true}'
    assert {row['tag'] for row in operations.tag_usage(engine)} == {'B', 'C'}


def test_merging_deduplicates_assignments_and_skips_invalid_targets(tagged_repository):
    engine, _ = tagged_repository
    result = operations.remap_tags(engine, {'A': 'B', 'B': 'invalid/target'}, False)
    assert result['applied'] == ['A']
    assert result['skipped'][0]['code'] == 'invalid_tag'
    assert all(tags == {'B'} for tags in assignments(engine).values())
    assert operations.tag_usage(engine) == [
        {'tag': 'B', 'models': 1, 'workflows': 1, 'user_objects': 1, 'collections': 1}]


def test_swap_and_case_sensitive_targets(tagged_repository):
    engine, _ = tagged_repository
    result = operations.remap_tags(engine, {'A': 'B', 'B': 'A'}, False)
    assert not result['errors']
    assert assignments(engine)['Workflow'] == {'A'}
    assert assignments(engine)['UserDefinedObject'] == {'B'}
    result = operations.remap_tags(engine, {'A': 'a'}, False)
    assert not result['errors']
    assert assignments(engine)['Model'] == {'a', 'B'}


def test_read_only_and_preflight_failures_change_nothing(tagged_repository):
    engine, root = tagged_repository
    before = assignments(engine)
    assert operations.remap_tags(engine, {'A': 'new'}, True)['errors'][0]['code'] == 'read_only'
    path = root / 'a' / 'flow.json'
    path.write_text('invalid JSON', encoding='utf-8')
    originals = {path: path.read_bytes() for path in root.glob('*/*.json')}
    assert operations.remap_tags(engine, {'A': 'new', 'B': 'new'}, False)['errors']
    assert assignments(engine) == before
    assert all(path.read_bytes() == data for path, data in originals.items())


def test_mid_operation_write_failure_restores_files_and_database(tagged_repository, monkeypatch):
    engine, root = tagged_repository
    originals = {path: path.read_bytes() for path in root.glob('*/*.json')}
    before = assignments(engine)
    original_replace = operations._replace_bytes
    calls = 0

    def fail_second_write(path, contents, mode):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError('simulated disk failure')
        original_replace(path, contents, mode)

    monkeypatch.setattr(operations, '_replace_bytes', fail_second_write)
    result = operations.remap_tags(engine, {'A': 'B'}, False)
    assert result['applied'] == []
    assert [error['code'] for error in result['errors']] == ['remap_failed']
    assert assignments(engine) == before
    assert all(path.read_bytes() == data for path, data in originals.items())


def test_read_only_member_blocks_entire_batch(tagged_repository):
    engine, _ = tagged_repository
    with Session(engine) as session:
        model = session.get(Model, 'a' * 64)
        model.errors = ['duplicate_working']
        session.add(model)
        session.commit()
    before = assignments(engine)
    result = operations.remap_tags(engine, {'A': 'new'}, False)
    assert result['errors'][0]['code'] == 'object_read_only'
    assert result['applied'] == []
    assert assignments(engine) == before


def test_browser_and_python_validation_agree():
    node = shutil.which('node')
    if node is None:
        pytest.skip('Node is needed to verify browser validation parity')
    values = ['class', '_name', 'ﬁnal', 'a  2 ', ' a', 'a\n', 'a\t', '🐍', '蛇',
              'école', 'a\u0301', '\u0301a', 'a-b', '1a', 'a\u00a0b', '__proto__', '', '   ',
              '1', '123', '2:model-v1', ':tag', '-tag', 'tag:', 'tag-', 'tag: ', 'tag- ',
              'a--::b', 'a: b ', 'a：b', 'a﹕b', 'a－b', 'a–b', 'a—b', 'a−b', '１tag']
    script = '''
        let input = '';
        process.stdin.on('data', chunk => input += chunk);
        process.stdin.on('end', () => {
            const data = JSON.parse(input);
            const pattern = new RegExp(data.pattern, 'u');
            process.stdout.write(JSON.stringify(data.values.map(value => {
                const trimmed = value.replace(/ +$/, '');
                return pattern.test(trimmed) ? trimmed.normalize('NFKC') : null;
            })));
        });
    '''
    completed = subprocess.run([node, '-e', script], input=json.dumps({
        'pattern': browser_tag_rules()['pattern'], 'values': values}),
        capture_output=True, text=True, encoding='utf-8', check=True)
    assert json.loads(completed.stdout) == [normalize_tag(value) for value in values]


def test_many_sources_merge_to_one_normalized_target(tagged_repository):
    engine, _ = tagged_repository
    result = operations.remap_tags(engine, {'A': 'ﬁnal ', 'B': 'final'}, False)
    assert not result['errors']
    assert all(tags == {'final'} for tags in assignments(engine).values())


def test_all_tag_query_includes_udt_only_tags_and_unused_tags(tagged_repository):
    engine, _ = tagged_repository
    with Session(engine) as session:
        obj = session.get(UserDefinedObject, 'doc')
        obj.tags.append(Tag(tag='UDT_only'))
        session.add(Tag(tag='unused'))
        session.add(obj)
        session.commit()
    assert set(repository.list_tags(None, 0, 0)) == {'A', 'B', 'UDT_only', 'unused'}


def test_invalid_model_edit_is_rejected_before_writing(tagged_repository):
    engine, root = tagged_repository
    path = root / 'w' / 'model.archivist.json'
    original = path.read_bytes()
    with pytest.raises(ArcException) as error:
        repository.update_model({'id': 'a' * 64, 'file_name': 'model',
                                 'internal_name': 'Model', 'tags': ['invalid/tag']})
    assert error.value.code is ArcException.Code.INVALID_TAG
    assert path.read_bytes() == original
    assert assignments(engine)['Model'] == {'A', 'B'}


def test_tag_api_lists_all_categories_and_dispatches_remapping(tagged_repository, monkeypatch):
    from backend.server.routers import tags

    dispatched = []

    def submit(kind, target):
        dispatched.append(kind)
        return {'id': 'test', 'state': 'succeeded', 'result': target(lambda progress: None)}

    monkeypatch.setattr(tags.dispatcher, 'submit', submit)
    assert asyncio.run(tags.get_tags()) == ['A', 'B']
    assert asyncio.run(tags.usage())[0]['user_objects'] == 1
    assert 'pattern' in asyncio.run(tags.tag_rules())
    response = asyncio.run(tags.remap(tags.TagRemapRequest(mappings={'A': 'B'})))
    assert response['result']['applied'] == ['A']
    assert dispatched == ['tag_remap']


def test_blank_unknown_and_unchanged_targets_do_not_modify_objects(tagged_repository):
    engine, _ = tagged_repository
    before = assignments(engine)
    result = operations.remap_tags(engine, {'A': '', 'B': 'B ', 'unknown': 'target'}, False)
    assert result['applied'] == []
    assert {entry['code'] for entry in result['skipped']} == {'blank_target', 'unchanged', 'unknown_tag'}
    assert assignments(engine) == before
