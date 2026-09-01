# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: test_environment.py
# purpose: Tests for standalone and ComfyUI environment discovery
# ---------------------------------------------------------------------------

from pathlib import Path

from backend.environment import ComfyEnvironmentProvider, StandaloneEnvironmentProvider


class FolderPathsStub:
    folder_names_and_paths = {
        'checkpoints': (['models/checkpoints', Path('extra/checkpoints')],
                        {'.safetensors', 'CKPT'}),
        'invalid': ('ignored',),
    }

    @staticmethod
    def get_user_directory():
        return 'comfy-user'


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
    assert provider.workflow_locations() == [
        (Path('comfy-user') / 'workflows').absolute()]
    assert provider.runtime_data_directory() == (
        Path('comfy-user') / '_archivist').absolute()


def test_comfy_environment_collapses_duplicate_model_locations(caplog):
    provider = ComfyEnvironmentProvider(DuplicateFolderPathsStub())

    with caplog.at_level('WARNING', logger='archivist.root'):
        models = provider.model_locations()

    assert len(models) == 2
    by_type = {item.model_type: item for item in models}
    assert by_type['diffusion_models'].extensions == ('.gguf', '.safetensors')
    assert by_type['checkpoints'].working_dir == Path('models/shared').resolve(strict=False)
    assert 'Ignoring duplicate ComfyUI model location' in caplog.text
