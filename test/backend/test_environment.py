# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: test_environment.py
# purpose: Tests for standalone and ComfyUI environment discovery
# ---------------------------------------------------------------------------

from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.environment import ComfyEnvironmentProvider, StandaloneEnvironmentProvider


class FolderPathsStub:
    models_dir = 'models'
    folder_names_and_paths = {
        'checkpoints': (['models/checkpoints', Path('extra/checkpoints'),
                         'output/checkpoints'],
                        {'.safetensors', 'CKPT'}),
        'configs': (['models/configs'], {'.yaml'}),
        'custom_nodes': (['custom_nodes'], set()),
        'invalid': ('ignored',),
    }

    @staticmethod
    def get_user_directory():
        return 'comfy-user'

    @staticmethod
    def get_output_directory():
        return 'output'


class DuplicateFolderPathsStub:
    folder_names_and_paths = {
        'diffusion_models': (['models/diffusion'], {'.safetensors'}),
        'unet': (['models/diffusion'], {'.gguf'}),
        'checkpoints': (['models/shared'], {'.ckpt'}),
        'loras': (['models/shared'], {'.safetensors'}),
    }


def test_standalone_environment_has_no_discovered_locations():
    provider = StandaloneEnvironmentProvider()
    assert provider.mode == 'standalone'
    assert provider.model_locations() == []
    assert provider.workflow_locations() == []
    assert provider.runtime_data_directory() is None


def test_comfy_environment_reads_registered_model_and_workflow_locations():
    provider = ComfyEnvironmentProvider(FolderPathsStub())
    models = provider.model_locations()

    assert provider.mode == 'comfyui'
    assert len(models) == 2
    assert {item.model_type for item in models} == {'checkpoints'}
    assert all(item.extensions == ('.ckpt', '.safetensors') for item in models)
    assert provider.default_working_roots() == [
        Path('models').absolute(), Path('extra/checkpoints').absolute()]
    assert provider.workflow_locations() == [
        (Path('comfy-user') / 'default' / 'workflows').absolute()]
    assert provider.runtime_data_directory() == (
        Path('comfy-user') / '_archivist').absolute()


def test_comfy_workflows_use_selected_public_profile():
    calls = []
    folders = FolderPathsStub()
    folders.get_public_user_directory = lambda profile: (
        calls.append(profile) or str(Path('comfy-user') / profile))
    provider = ComfyEnvironmentProvider(folders)
    assert provider.workflow_locations('alice') == [
        (Path('comfy-user') / 'alice' / 'workflows').absolute()]
    assert calls == ['alice']
    for invalid in ('../alice', '__system', 'C:\\alice', ''):
        with pytest.raises(ValueError):
            provider.workflow_locations(invalid)


def test_comfy_environment_collapses_duplicate_model_locations(caplog):
    provider = ComfyEnvironmentProvider(DuplicateFolderPathsStub())

    with caplog.at_level('WARNING', logger='archivist.root'):
        models = provider.model_locations()

    assert len(models) == 2
    by_type = {item.model_type: item for item in models}
    assert by_type['diffusion_models'].extensions == ('.gguf', '.safetensors')
    assert by_type['checkpoints'].working_dir == Path('models/shared').resolve(strict=False)
    assert 'Ignoring duplicate ComfyUI model location' in caplog.text


@pytest.mark.parametrize(('paths', 'expected'), [
    (['extra/checkpoints', 'extra/loras'], ['extra']),
    (['extra/checkpoints', 'other/loras'], ['extra/checkpoints', 'other/loras']),
    (['extra/checkpoints', 'extra/checkpoints'], ['extra/checkpoints']),
    (['extra/one/checkpoints', 'extra/one/loras',
      'extra/two/checkpoints', 'extra/two/loras'], ['extra/one', 'extra/two']),
    (['extra/one/checkpoints', 'extra/two/loras'],
     ['extra/one/checkpoints', 'extra/two/loras']),
    (['models/checkpoints', 'models/loras', 'extra/checkpoints'], ['extra/checkpoints']),
    (['extra/checkpoints', 'extra/loras', 'extra/checkpoints/nested'], ['extra']),
])
def test_comfy_default_roots_consolidate_only_immediate_siblings(paths, expected):
    provider = ComfyEnvironmentProvider(SimpleNamespace(
        models_dir='models',
        folder_names_and_paths={'checkpoints': (paths, {'.safetensors'})},
    ))

    assert provider.default_working_roots() == [
        Path(path).absolute() for path in ['models', *expected]]
    assert {location.working_dir for location in provider.model_locations()} == {
        Path(path).absolute() for path in paths}
