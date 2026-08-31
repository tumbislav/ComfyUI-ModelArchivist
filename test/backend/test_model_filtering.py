# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: test_model_filtering.py
# purpose: Tests for model search criteria and configuration values
# ---------------------------------------------------------------------------

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlmodel import Session, create_engine

import backend.repository.repository as repository
import backend.server.routers.configuration as configuration_router
from backend.repository.migrations import update_database_schema
from backend.repository.tables import Model, Tag


@pytest.fixture
def model_repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    engine = create_engine(f'sqlite:///{tmp_path / "filters.db"}')
    update_database_schema(engine)
    monkeypatch.setattr(repository, '_engine', engine)
    monkeypatch.setattr(repository, '_config', SimpleNamespace(model_types={
        'checkpoints': 'Checkpoints', 'loras': 'LoRAs'}))
    common = Tag(tag='common')
    red = Tag(tag='red')
    blue = Tag(tag='blue')
    banned = Tag(tag='banned')
    with Session(engine) as session:
        session.add_all([
            Model(id='a', file_name='alpha', internal_name='Alpha Model',
                  type='checkpoints', file_format='safetensors', relative_path='',
                  deployment='working', touched='timestamp', tags=[common, red]),
            Model(id='b', file_name='alpine', internal_name='Alpine Model',
                  type='loras', file_format='gguf', relative_path='',
                  deployment='archive', touched='timestamp', tags=[common, banned]),
            Model(id='c', file_name='beta', internal_name='Beta Model',
                  type='checkpoints', file_format='ckpt', relative_path='',
                  deployment='synced', touched='timestamp', tags=[red, blue]),
            Model(id='d', file_name='literal', internal_name='Literal_100% Model',
                  type='checkpoints', file_format='safetensors', relative_path='',
                  deployment='working', touched='timestamp'),
        ])
        session.commit()
    yield engine
    engine.dispose()


def result_ids(criteria: dict) -> list[str]:
    return [model['id'] for model in repository.list_models(True, criteria)]


def test_model_search_combines_type_format_tag_and_prefix_filters(model_repository):
    assert result_ids({
        'types': ['checkpoints'],
        'file_formats': ['.SAFETENSORS'],
        'required_tags': ['common'],
        'forbidden_tags': [],
        'name_prefix': 'alpha',
    }) == ['a']


def test_model_search_requires_every_required_tag(model_repository):
    assert result_ids({'required_tags': ['red', 'blue']}) == ['c']


def test_model_search_excludes_any_forbidden_tag(model_repository):
    assert result_ids({'forbidden_tags': ['banned']}) == ['a', 'c', 'd']


def test_model_name_prefix_escapes_like_wildcards(model_repository):
    assert result_ids({'name_prefix': 'Literal_100%'}) == ['d']


def test_file_format_config_is_normalized_and_deduplicated(
        monkeypatch: pytest.MonkeyPatch):
    config = SimpleNamespace(model_extensions=[
        '.safetensors', '.GGUF', 'gguf', '.ckpt'])
    monkeypatch.setattr(configuration_router, 'get_config', lambda: config)

    result = asyncio.run(configuration_router.get_file_formats())

    assert result == ['safetensors', 'gguf', 'ckpt']


def test_model_type_config_preserves_raw_values_and_labels(
        monkeypatch: pytest.MonkeyPatch):
    config = SimpleNamespace(model_types={
        'checkpoints': 'Checkpoints', 'loras': 'LoRAs'})
    monkeypatch.setattr(configuration_router, 'get_config', lambda: config)

    result = asyncio.run(configuration_router.get_model_types())

    assert result == [
        {'value': 'checkpoints', 'label': 'Checkpoints'},
        {'value': 'loras', 'label': 'LoRAs'},
    ]
