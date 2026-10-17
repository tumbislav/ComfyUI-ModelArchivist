# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: test_model_type_settings.py
# purpose: Grouped model mapping creation, deletion, and confirmation regressions
# ---------------------------------------------------------------------------

import asyncio
import logging
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlmodel import Session, SQLModel, create_engine, select

from backend.config import Configuration, DatabaseConfig, WebConfig, LoggingConfig
from backend.environment import ComfyEnvironmentProvider, StandaloneEnvironmentProvider
import backend.filesystem_policy as filesystem
import backend.repository.repository as repo
from backend.repository.tables import (Collection, Component, ComponentSet, Model,
                                       ModelLocationSetting, ModelTypeSetting, Tag,
                                       ModelCollectionLink, TagModelLink)
from backend.server.routers import configuration


@pytest.fixture
def model_settings(tmp_path, monkeypatch):
    working = tmp_path / 'models'
    archive = tmp_path / 'archive'
    for name in ('unet', 'diffusion_models', 'loras'):
        (working / name).mkdir(parents=True)
        (archive / name).mkdir(parents=True)
    provider = ComfyEnvironmentProvider(SimpleNamespace(
        models_dir=str(working),
        folder_names_and_paths={
            'diffusion_models': ([str(working / 'unet'), str(working / 'diffusion_models')],
                                 {'.gguf', '.safetensors'}),
            'loras': ([str(working / 'loras')], {'.safetensors'}),
        },
    ))
    config = Configuration(
        database=DatabaseConfig(database_file=str(tmp_path / 'database.db')),
        web=WebConfig(host='127.0.0.1', port=5173, static_html=str(tmp_path / 'html')),
        logging=LoggingConfig(level='INFO', sql_level='WARNING', file=str(tmp_path / 'log')))
    config.initialize(tmp_path, tmp_path / 'config.toml')
    config.filesystem = filesystem.FilesystemPolicy((working,), (archive,), ())
    monkeypatch.setattr(filesystem, '_policy', config.filesystem)
    engine = create_engine('sqlite://')
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(repo, '_engine', engine)
    monkeypatch.setattr(repo, '_config', config)
    monkeypatch.setattr(repo, '_logger', logging.getLogger('archivist.database'))
    monkeypatch.setattr(repo, 'get_environment_provider', lambda: provider)
    monkeypatch.setattr(repo, 'get_config', lambda: config)
    repo.load_repository_configuration(config)
    yield working, archive, provider, config
    engine.dispose()


def save_discovered(working, archive):
    candidates = repo.propose_model_mappings(str(working), str(archive), ['.gguf'])
    return repo.update_model_configuration({'model_types': candidates})


def add_model():
    with Session(repo._engine) as session:
        model = Model(id='hash', file_name='model', internal_name='Model', type='diffusion_models',
                      relative_path='', deployment='working', touched='scan',
                      component_sets=[ComponentSet(where='w', primary_dir='models/unet',
                                                   components=[Component(file_name='model.gguf',
                                                                         component_type='model',
                                                                         touched='scan')])])
        model.tags = [Tag(tag='test')]
        model.collections = [Collection(name='Keep collection', purpose='')]
        session.add(model)
        session.commit()


@pytest.mark.parametrize('reported_extensions', [set(), {'.safetensors'}, {'.ckpt', '.pkl'}])
def test_comfy_single_type_choices_include_all_registered_directories(model_settings, reported_extensions):
    working, archive, provider, _ = model_settings
    paths, _ = provider.folder_paths.folder_names_and_paths['diffusion_models']
    provider.folder_paths.folder_names_and_paths['diffusion_models'] = (paths, reported_extensions)
    choices = repo.get_repository_configuration()['available_model_types']
    diffusion = next(item for item in choices if item['name'] == 'diffusion_models')
    assert {item['working_dir'] for item in diffusion['locations']} == {
        str(working / 'unet'), str(working / 'diffusion_models')}
    assert diffusion['extensions'] == sorted(
        reported_extensions | {'.sft', '.safetensors', '.pt', '.pth', '.gguf'})
    assert all(item['archive_dir'] is None for item in diffusion['locations'])
    assert repo.get_repository_configuration()['model_types'] == []


def test_remove_type_deletes_all_pairs_models_components_and_links(model_settings):
    working, archive, _, config = model_settings
    save_discovered(working, archive)
    add_model()
    before = repo.get_repository_configuration()
    assert next(item for item in before['model_types'] if item['name'] == 'diffusion_models')['model_count'] == 1
    result = repo.delete_model_type('diffusion_models', 1)
    assert [item['name'] for item in result['model_types']] == ['loras']
    with Session(repo._engine) as session:
        for table in (Model, ComponentSet, Component, ModelCollectionLink, TagModelLink):
            assert session.exec(select(table)).all() == []
        assert session.exec(select(Collection)).one().name == 'Keep collection'
        assert session.exec(select(Tag)).one().tag == 'test'
        assert {item.model_type for item in session.exec(select(ModelLocationSetting)).all()} == {'loras'}
    repo.load_repository_configuration(config)
    assert 'diffusion_models' not in config.model_folders
    assert (working / 'unet').is_dir() and (archive / 'unet').is_dir()
    # Explicitly re-adding the type is possible; startup never recreates it.
    choices = repo.get_repository_configuration()['available_model_types']
    assert any(item['name'] == 'diffusion_models' for item in choices)
    save_discovered(working, archive)
    assert 'diffusion_models' in config.model_folders


def test_remove_type_rejects_stale_count_without_deleting_anything(model_settings):
    working, archive, _, _ = model_settings
    save_discovered(working, archive)
    add_model()
    with pytest.raises(ValueError, match='model_type_count_changed'):
        repo.delete_model_type('diffusion_models', 0)
    with Session(repo._engine) as session:
        assert session.get(Model, 'hash') is not None
        assert session.get(ModelTypeSetting, 'diffusion_models') is not None
        assert len(session.exec(select(ModelLocationSetting).where(
            ModelLocationSetting.model_type == 'diffusion_models')).all()) == 2


@pytest.mark.parametrize('mode', ['comfyui', 'standalone'])
def test_omitting_type_from_save_removes_catalogue_group(model_settings, monkeypatch, mode):
    working, archive, _, config = model_settings
    if mode == 'standalone':
        monkeypatch.setattr(repo, 'get_environment_provider', lambda: StandaloneEnvironmentProvider())
        repo.load_repository_configuration(config)
        repo.update_model_configuration({'model_types': [{
            'name': 'diffusion_models', 'display_name': 'Diffusion', 'extensions': ['.gguf'],
            'locations': [{'working_dir': str(working / 'unet'), 'archive_dir': str(archive / 'unet')}],
        }]})
    else:
        save_discovered(working, archive)
    add_model()
    result = repo.update_model_configuration({'model_types': []})
    assert result['model_types'] == []
    with Session(repo._engine) as session:
        assert session.exec(select(Model)).all() == []
        assert session.exec(select(ModelLocationSetting)).all() == []


def test_new_embedded_type_cannot_use_unregistered_working_path(model_settings):
    working, archive, _, _ = model_settings
    with pytest.raises(ValueError, match='not supplied by ComfyUI'):
        repo.update_model_configuration({'model_types': [{
            'name': 'diffusion_models', 'display_name': 'Diffusion', 'extensions': ['.gguf'],
            'locations': [{'working_dir': str(working / 'loras'), 'archive_dir': str(archive / 'unet')}],
        }]})
    assert repo.get_repository_configuration()['model_types'] == []


def test_delete_endpoint_returns_semantic_stale_count_error(monkeypatch):
    from contextlib import nullcontext
    monkeypatch.setattr(configuration, 'dispatcher', SimpleNamespace(configuration_change=nullcontext))
    def stale(*args):
        raise ValueError('model_type_count_changed')
    monkeypatch.setattr(configuration.repo, 'delete_model_type', stale)
    with pytest.raises(HTTPException) as error:
        asyncio.run(configuration.delete_model_type('diffusion_models', 0))
    assert error.value.status_code == 409
    assert error.value.detail['code'] == 'model_type_count_changed'



def test_standalone_single_add_derives_key_from_working_folder(monkeypatch, tmp_path):
    from contextlib import nullcontext
    monkeypatch.setattr(configuration, 'dispatcher', SimpleNamespace(configuration_change=nullcontext))
    monkeypatch.setattr(configuration.repo, 'get_repository_configuration',
                        lambda: {'mode': 'standalone', 'model_types': []})
    captured = []
    monkeypatch.setattr(configuration.repo, 'update_model_configuration',
                        lambda data: captured.append(data) or data)
    data = configuration.ModelTypeInput(
        name='ignored-manual-key', display_name='My models', extensions=['.gguf'],
        locations=[configuration.LocationInput(working_dir=str(tmp_path / 'unet'),
                                                archive_dir=str(tmp_path / 'archive'))])
    asyncio.run(configuration.update_single_model_type(data))
    assert captured[0]['model_types'][0]['name'] == 'unet'


def test_single_add_rejects_already_mapped_comfy_type(monkeypatch):
    from contextlib import nullcontext
    monkeypatch.setattr(configuration, 'dispatcher', SimpleNamespace(configuration_change=nullcontext))
    monkeypatch.setattr(configuration.repo, 'get_repository_configuration', lambda: {
        'mode': 'comfyui', 'model_types': [{'name': 'diffusion_models'}]})
    monkeypatch.setattr(configuration.repo, 'update_model_configuration',
                        lambda _: pytest.fail('duplicate type must not be saved'))
    data = configuration.ModelTypeInput(name='diffusion_models', display_name='Diffusion',
                                        extensions=['.gguf'])
    with pytest.raises(HTTPException) as error:
        asyncio.run(configuration.update_single_model_type(data))
    assert error.value.status_code == 400
    assert error.value.detail['code'] == 'invalid_model_type'


def test_type_removal_blocked_during_scan(monkeypatch):
    import backend.dispatcher as dispatch
    worker = dispatch.OperationDispatcher()
    monkeypatch.setattr(dispatch, '_get_scanner', lambda: SimpleNamespace(started=True, finished=False))
    monkeypatch.setattr(configuration, 'dispatcher', worker)
    monkeypatch.setattr(configuration.repo, 'delete_model_type',
                        lambda *args: pytest.fail('must not delete during a scan'))
    with pytest.raises(HTTPException) as error:
        asyncio.run(configuration.delete_model_type('diffusion_models', 0))
    assert error.value.status_code == 409
    assert error.value.detail['code'] == 'operation_busy'
