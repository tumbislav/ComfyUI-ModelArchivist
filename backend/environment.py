# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: environment.py
# purpose: Standalone and ComfyUI filesystem discovery providers
# ---------------------------------------------------------------------------

from dataclasses import dataclass
import logging
import os
from pathlib import Path
from typing import Any, Protocol


_logger = logging.getLogger('archivist.root')
_COMFY_MODEL_TYPE_ALIASES = {'unet': 'diffusion_models', 'clip': 'text_encoders'}


@dataclass(frozen=True)
class DiscoveredModelLocation:
    model_type: str
    working_dir: Path
    extensions: tuple[str, ...]


class EnvironmentProvider(Protocol):
    mode: str

    def model_locations(self) -> list[DiscoveredModelLocation]: ...
    def workflow_locations(self) -> list[Path]: ...
    def runtime_data_directory(self) -> Path | None: ...


class StandaloneEnvironmentProvider:
    mode = 'standalone'

    def model_locations(self) -> list[DiscoveredModelLocation]:
        return []

    def workflow_locations(self) -> list[Path]:
        return []

    def runtime_data_directory(self) -> Path | None:
        return None


class ComfyEnvironmentProvider:
    """Read working locations from the live ComfyUI folder registry."""
    mode = 'comfyui'

    def __init__(self, folder_paths: Any):
        self.folder_paths = folder_paths

    def model_locations(self) -> list[DiscoveredModelLocation]:
        discovered: dict[str, DiscoveredModelLocation] = {}
        registry = getattr(self.folder_paths, 'folder_names_and_paths', {})
        for model_type, definition in registry.items():
            if not isinstance(definition, tuple) or len(definition) < 2:
                continue
            paths, extensions = definition[0], definition[1]
            if isinstance(paths, (str, Path)):
                paths = [paths]
            canonical_type = _COMFY_MODEL_TYPE_ALIASES.get(
                str(model_type), str(model_type))
            normalized_extensions = {
                str(extension).lower()
                if str(extension).startswith('.') else f'.{str(extension).lower()}'
                for extension in extensions
            }
            for path in paths:
                working_dir = Path(path).resolve(strict=False)
                path_key = os.path.normcase(str(working_dir))
                existing = discovered.get(path_key)
                if existing is None:
                    discovered[path_key] = DiscoveredModelLocation(
                        canonical_type, working_dir, tuple(sorted(normalized_extensions)))
                elif existing.model_type == canonical_type:
                    discovered[path_key] = DiscoveredModelLocation(
                        canonical_type, working_dir,
                        tuple(sorted(set(existing.extensions) | normalized_extensions)))
                else:
                    _logger.warning(
                        'Ignoring duplicate ComfyUI model location %s registered as %s; '
                        'it is already registered as %s',
                        working_dir, canonical_type, existing.model_type)
        return list(discovered.values())

    def workflow_locations(self) -> list[Path]:
        get_user_directory = getattr(self.folder_paths, 'get_user_directory', None)
        if not callable(get_user_directory):
            return []
        return [(Path(get_user_directory()) / 'workflows').absolute()]

    def runtime_data_directory(self) -> Path | None:
        get_user_directory = getattr(self.folder_paths, 'get_user_directory', None)
        if not callable(get_user_directory):
            return None
        return (Path(get_user_directory()) / '_archivist').absolute()


_provider: EnvironmentProvider = StandaloneEnvironmentProvider()


def set_environment_provider(provider: EnvironmentProvider) -> None:
    global _provider
    _provider = provider


def get_environment_provider() -> EnvironmentProvider:
    return _provider
