# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: test_filesystem_policy.py
# purpose: Filesystem boundary, link, initialization and enforcement regressions
# ---------------------------------------------------------------------------

import datetime
import os
from pathlib import Path
from threading import Barrier
from types import SimpleNamespace
import tomllib

import pytest

from backend import filesystem_policy as fs
from backend.config import load_config, ConfigException
from backend.environment import DiscoveredModelLocation
from backend.files.metadata import scan_model_metadata
from backend.files.operations import FileAction, FileSnapshot, execute_file_action
from backend.files.scanner import Scanner
from backend.repository import repository
from backend.server.public_routes import api_routes


@pytest.fixture
def policy(tmp_path, monkeypatch):
    working, archive = tmp_path / 'working', tmp_path / 'archive'
    working.mkdir()
    archive.mkdir()
    policy = fs.FilesystemPolicy((working,), (archive,), (working / 'private',))
    monkeypatch.setattr(fs, '_policy', policy)
    return policy


def test_role_boundaries_missing_targets_and_prefix_siblings(policy):
    working, archive = policy.working_roots[0], policy.archive_roots[0]
    assert policy.check(working / 'new' / 'model.bin', 'working') == working / 'new' / 'model.bin'
    for path, role in ((working, 'archive'), (archive, 'working'),
                       (working.with_name('working-other'), 'working')):
        with pytest.raises(fs.FilesystemPolicyError, match='outside'):
            policy.check(path, role)


@pytest.mark.parametrize('outside_first', [False, True])
def test_comfy_mapping_preview_ignores_unpermitted_folders_outside_selected_root(
        policy, monkeypatch, outside_first):
    working, archive = policy.working_roots[0], policy.archive_roots[0]
    (working / 'checkpoints').mkdir()
    locations = [
        DiscoveredModelLocation('checkpoints', working / 'checkpoints', ('.safetensors',)),
        DiscoveredModelLocation('luts', working.parent / 'custom_nodes' / 'luts', ('.cube',)),
        DiscoveredModelLocation('loras', working.with_name('working-other') / 'loras',
                                ('.safetensors',)),
    ]
    if outside_first:
        locations.reverse()
    monkeypatch.setattr(repository, '_config', SimpleNamespace(mode='comfyui'))
    monkeypatch.setattr(repository, 'get_environment_provider',
                        lambda: SimpleNamespace(model_locations=lambda: locations))
    monkeypatch.setattr(repository, 'get_repository_configuration', lambda: {'model_types': []})

    assert repository.propose_model_mappings(str(working), str(archive), ['.safetensors']) == [{
        'name': 'checkpoints', 'display_name': 'checkpoints', 'extensions': ['.safetensors'],
        'locations': [{'working_dir': str(working / 'checkpoints'),
                       'archive_dir': str(archive / 'checkpoints')}],
    }]


def test_comfy_mapping_preview_reports_excluded_folder_inside_selected_root(policy, monkeypatch):
    working, archive = policy.working_roots[0], policy.archive_roots[0]
    location = DiscoveredModelLocation('checkpoints', working / 'private' / 'checkpoints',
                                       ('.safetensors',))
    monkeypatch.setattr(repository, '_config', SimpleNamespace(mode='comfyui'))
    monkeypatch.setattr(repository, 'get_environment_provider',
                        lambda: SimpleNamespace(model_locations=lambda: [location]))
    monkeypatch.setattr(repository, 'get_repository_configuration', lambda: {'model_types': []})

    with pytest.raises(fs.FilesystemPolicyError) as error:
        repository.propose_model_mappings(str(working), str(archive), ['.safetensors'])
    assert error.value.code == 'filesystem_excluded'


def test_comfy_mapping_preview_merges_initial_extensions_for_shared_type(policy, monkeypatch):
    working, archive = policy.working_roots[0], policy.archive_roots[0]
    (working / 'LLM').mkdir()
    (working / 'other-LLM').mkdir()
    locations = [
        DiscoveredModelLocation('LLM', working / 'LLM', ()),
        DiscoveredModelLocation('LLM', working / 'other-LLM', ('.gguf',)),
    ]
    monkeypatch.setattr(repository, '_config', SimpleNamespace(mode='comfyui'))
    monkeypatch.setattr(repository, 'get_environment_provider',
                        lambda: SimpleNamespace(model_locations=lambda: locations))
    monkeypatch.setattr(repository, 'get_repository_configuration', lambda: {'model_types': []})

    candidates = repository.propose_model_mappings(str(working), str(archive), ['.safetensors'])
    assert len(candidates) == 1
    assert candidates[0]['extensions'] == ['.gguf']
    assert len(candidates[0]['locations']) == 2


def test_comfy_mapping_preview_skips_missing_folders_and_files(policy, monkeypatch):
    working, archive = policy.working_roots[0], policy.archive_roots[0]
    (working / 'existing').mkdir()
    (working / 'file').write_bytes(b'not a directory')
    locations = [DiscoveredModelLocation(name, working / name, ('.gguf',))
                 for name in ('existing', 'missing', 'file')]
    monkeypatch.setattr(repository, '_config', SimpleNamespace(mode='comfyui'))
    monkeypatch.setattr(repository, 'get_environment_provider',
                        lambda: SimpleNamespace(model_locations=lambda: locations))
    monkeypatch.setattr(repository, 'get_repository_configuration', lambda: {'model_types': []})

    candidates = repository.propose_model_mappings(str(working), str(archive), ['.gguf'])
    assert [item['name'] for item in candidates] == ['existing']


@pytest.mark.parametrize('value', ['relative/path', '~', '../escape'])
def test_only_literal_absolute_paths(policy, value):
    with pytest.raises(fs.FilesystemPolicyError) as error:
        policy.check(value)
    assert error.value.code == 'filesystem_absolute_required'


def test_parent_traversal_is_not_normalized_away(policy):
    with pytest.raises(fs.FilesystemPolicyError) as error:
        policy.check(policy.working_roots[0] / 'sub' / '..' / 'file')
    assert error.value.code == 'filesystem_absolute_required'


def test_exclusion_wins_over_nested_allowlist(policy):
    private = policy.exclusions[0]
    policy = fs.FilesystemPolicy((policy.working_roots[0], private / 'allowed'), (), (private,))
    with pytest.raises(fs.FilesystemPolicyError) as error:
        policy.check(private / 'allowed' / 'deep' / 'model.bin', 'working')
    assert error.value.code == 'filesystem_excluded'


def test_hardlinks_rejected_from_both_names(policy):
    first = policy.working_roots[0] / 'model.bin'
    second = policy.archive_roots[0] / 'alias.bin'
    first.write_bytes(b'model')
    os.link(first, second)
    for path in (first, second):
        with pytest.raises(fs.FilesystemPolicyError) as error:
            policy.check(path)
        assert error.value.code == 'filesystem_hardlink_forbidden'


def test_symlink_ancestor_even_when_target_is_allowed(policy):
    root = policy.working_roots[0]
    (root / 'real').mkdir()
    link = root / 'alias'
    try:
        link.symlink_to(root / 'real', target_is_directory=True)
    except OSError as error:
        pytest.skip(f'Symlink creation is unavailable: {error}')
    with pytest.raises(fs.FilesystemPolicyError) as error:
        policy.check(link / 'new-file')
    assert error.value.code == 'filesystem_link_forbidden'


def test_reparse_ancestor_rejected_before_enumeration(policy, monkeypatch):
    root = policy.working_roots[0]
    junction = root / 'junction'
    original = Path.lstat

    def lstat(path, **kwargs):
        if path == junction:
            return SimpleNamespace(st_mode=0o040755, st_file_attributes=0x400)
        return original(path, **kwargs)

    monkeypatch.setattr(Path, 'lstat', lstat)
    monkeypatch.setattr(os, 'readlink', lambda path: r'\??\C:\elsewhere')
    with pytest.raises(fs.FilesystemPolicyError) as error:
        policy.check(junction / 'new-file')
    assert error.value.code == 'filesystem_link_forbidden'


def test_mount_must_be_explicit(policy, monkeypatch):
    mount = policy.working_roots[0] / 'volume'
    mount.mkdir()
    monkeypatch.setattr(os.path, 'ismount', lambda path: Path(path) == mount)
    with pytest.raises(fs.FilesystemPolicyError) as error:
        policy.check(mount / 'file')
    assert error.value.code == 'filesystem_mount_forbidden'
    explicit = fs.FilesystemPolicy((mount,), ())
    assert explicit.check(mount / 'file') == mount / 'file'


@pytest.mark.skipif(os.name != 'nt', reason='Windows reparse point behavior')
@pytest.mark.parametrize('target,tag,allowed', [
    ('\\\\?\\Volume{12345678-1234-1234-1234-123456789012}\\', 0xA0000003, True),
    ('\\\\?\\Volume{12345678-1234-1234-1234-123456789012}\\subfolder', 0xA0000003, False),
    ('\\\\?\\Volume{12345678-1234-1234-1234-123456789012}\\', 0xA000000C, False),
])
def test_volume_mount_exception_does_not_admit_junctions_or_symlinks(
        tmp_path, monkeypatch, target, tag, allowed):
    mount = tmp_path / 'volume'
    mount.mkdir()
    policy = fs.FilesystemPolicy((mount,), ())
    original = Path.lstat
    monkeypatch.setattr(Path, 'lstat', lambda path, **kw: SimpleNamespace(
        st_mode=0o040755, st_file_attributes=0x400, st_reparse_tag=tag)
        if path == mount else original(path, **kw))
    monkeypatch.setattr(os, 'readlink', lambda path: target)
    if allowed:
        assert policy.check(mount / 'file') == mount / 'file'
    else:
        with pytest.raises(fs.FilesystemPolicyError) as error:
            policy.check(mount / 'file')
        assert error.value.code == 'filesystem_link_forbidden'


def test_unknown_link_count_fails_closed(policy, monkeypatch):
    file = policy.working_roots[0] / 'model.bin'
    original = Path.lstat
    monkeypatch.setattr(Path, 'lstat', lambda path, **kw:
                        SimpleNamespace(st_mode=0o100644) if path == file else original(path, **kw))
    with pytest.raises(fs.FilesystemPolicyError) as error:
        policy.check(file)
    assert error.value.code == 'filesystem_unverifiable'


def test_walking_never_enumerates_excluded_subtree(policy, monkeypatch):
    private = policy.exclusions[0]
    private.mkdir()
    (private / 'secret.bin').touch()
    original = Path.iterdir

    def iterdir(path):
        assert path != private
        return original(path)

    monkeypatch.setattr(Path, 'iterdir', iterdir)
    blocked = []
    assert list(fs.safe_tree(policy.working_roots[0], 'working', blocked.append)) == []
    assert blocked[0].code == 'filesystem_excluded'


def test_metadata_cannot_overwrite_hardlinked_sidecar(policy):
    model = policy.working_roots[0] / 'model.bin'
    model.write_bytes(b'weights')
    sidecar = model.with_suffix('.archivist.json')
    sidecar.write_text('{}')
    os.link(sidecar, policy.archive_roots[0] / 'alias.json')
    with pytest.raises(fs.FilesystemPolicyError):
        scan_model_metadata(model)
    assert sidecar.read_text() == '{}'


def test_saved_action_rechecks_destination_after_planning(policy):
    source = policy.working_roots[0] / 'model.bin'
    destination = policy.archive_roots[0] / 'model.bin'
    source.write_bytes(b'model')
    action = FileAction('copy', str(source), str(destination), FileSnapshot.capture(source), FileSnapshot(False))
    external = policy.archive_roots[0] / 'other.bin'
    external.write_bytes(b'untouched')
    os.link(external, destination)
    with pytest.raises(fs.FilesystemPolicyError):
        execute_file_action(action)
    assert external.read_bytes() == b'untouched'


def test_directory_transfer_preflights_every_descendant(policy):
    source = policy.working_roots[0] / 'folder'
    source.mkdir()
    child = source / 'linked.bin'
    child.write_bytes(b'data')
    os.link(child, policy.archive_roots[0] / 'alias.bin')
    with pytest.raises(fs.FilesystemPolicyError):
        fs.check_transfer_tree(source, policy.archive_roots[0] / 'folder')
    assert source.exists()


def test_preview_denies_before_listing_caller_root(policy, monkeypatch):
    monkeypatch.setattr(Path, 'iterdir', lambda path: pytest.fail('denied root was enumerated'))
    with pytest.raises(fs.FilesystemPolicyError):
        repository.propose_model_mappings(str(policy.working_roots[0].parent),
                                          str(policy.archive_roots[0]), ['bin'])


def test_native_picker_has_no_public_route():
    assert not any('pick-directory' in path for method, path in api_routes())


def test_config_rejects_wrong_role_before_saving(policy, monkeypatch):
    monkeypatch.setattr(repository, '_config', SimpleNamespace(mode='standalone'))
    with pytest.raises(fs.FilesystemPolicyError):
        repository.update_repository_configuration({'model_types': [{
            'name': 'models', 'display_name': 'Models', 'extensions': ['bin'],
            'locations': [{'working_dir': str(policy.working_roots[0]),
                           'archive_dir': str(policy.working_roots[0] / 'not-an-archive')}],
        }]})


def test_existing_blocked_mapping_is_preserved_read_only(tmp_path, policy, monkeypatch):
    from sqlmodel import Session, create_engine, select
    from backend.config import Configuration, DatabaseConfig, WebConfig, LoggingConfig
    from backend.environment import StandaloneEnvironmentProvider
    from backend.repository.migrations import update_database_schema
    from backend.repository.tables import ModelTypeSetting, ModelLocationSetting

    engine = create_engine(f'sqlite:///{tmp_path / "index.db"}')
    update_database_schema(engine)
    monkeypatch.setattr(repository, '_engine', engine)
    monkeypatch.setattr(repository, 'get_environment_provider', StandaloneEnvironmentProvider)
    blocked = policy.exclusions[0]
    try:
        with Session(engine) as session:
            session.add(ModelTypeSetting(name='models', display_name='Models', extensions=['.bin']))
            session.add(ModelLocationSetting(model_type='models', source='standalone',
                                             working_dir=str(blocked),
                                             archive_dir=str(policy.archive_roots[0])))
            session.commit()
        config = Configuration(DatabaseConfig('db'), WebConfig('127.0.0.1', 8188, 'html'),
                               LoggingConfig('INFO', 'WARNING', 'log'), filesystem=policy)
        repository.load_repository_configuration(config)
        assert config.read_only
        assert config.filesystem_issues[0]['code'] == 'filesystem_excluded'
        assert not blocked.exists()
        with Session(engine) as session:
            assert session.exec(select(ModelLocationSetting)).one().working_dir == str(blocked)
    finally:
        engine.dispose()


def bootstrap_file(tmp_path):
    path = tmp_path / 'config.toml'
    path.write_text('''# Keep this comment.
[database]
database_file = "database.db"
[web]
host = "127.0.0.1"
port = 8188
static_html = "frontend/build"
[logging]
level = "INFO"
sql_level = "WARNING"
file = "archivist.log"
''', encoding='utf-8')
    return path


def test_shipped_config_defers_filesystem_defaults_until_first_start():
    path = Path(__file__).parents[2] / 'config.toml'

    assert 'filesystem' not in tomllib.loads(path.read_text(encoding='utf-8'))


@pytest.mark.parametrize('mode', ['standalone', 'comfyui'])
def test_initialization_written_once_with_mode_defaults(tmp_path, monkeypatch, mode):
    import backend.environment as environment
    home = tmp_path / 'home'
    models = tmp_path / 'ComfyUI' / 'models'
    extra = tmp_path / 'shared-models'
    monkeypatch.setattr(Path, 'home', lambda: home)
    monkeypatch.setattr(environment, 'get_environment_provider', lambda:
                        SimpleNamespace(default_working_roots=lambda: [models, extra]))
    path = bootstrap_file(tmp_path)
    config = load_config(path, mode)
    assert config.filesystem.working_roots == ((home,) if mode == 'standalone'
                                               else (models, extra))
    assert config.filesystem.archive_roots == ()
    contents = path.read_text(encoding='utf-8')
    assert contents.startswith('# Keep this comment.')
    assert tomllib.loads(contents)['filesystem'] == config.filesystem.to_dict()
    load_config(path, mode)
    assert path.read_text(encoding='utf-8') == contents
    # Explicitly empty lists remain empty even after changing operating mode.
    original = contents[:contents.index('[filesystem]')]
    path.write_text(original + '[filesystem]\nworking_roots=[]\narchive_roots=[]\nexclusions=[]\n', encoding='utf-8')
    load_config(path, 'standalone')
    assert fs.get_policy().working_roots == ()
    with pytest.raises(fs.FilesystemPolicyError):
        fs.checked_path(home / 'file')


def test_invalid_policy_never_replaced_with_defaults(tmp_path):
    path = bootstrap_file(tmp_path)
    with path.open('a') as stream:
        stream.write('\n[filesystem]\nworking_roots=["relative"]\narchive_roots=[]\nexclusions=[]\n')
    before = path.read_bytes()
    with pytest.raises(ConfigException):
        load_config(path)
    assert path.read_bytes() == before


def test_blocked_worker_completes_and_preserves_index(policy, monkeypatch):
    scanner = Scanner(started=True, start_time=datetime.datetime.now(datetime.timezone.utc), barrier=Barrier(1))
    monkeypatch.setattr(repository, 'scan_cleanup', lambda *args: pytest.fail('incomplete scan deleted records'))
    scanner.find_workflows([(policy.working_roots[0].parent, policy.archive_roots[0])])
    scanner.cleanup()
    assert scanner.finished
    assert scanner.progress()['errors']
