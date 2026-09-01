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
