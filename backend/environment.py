# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: environment.py
# purpose: Standalone and ComfyUI filesystem discovery providers
# ---------------------------------------------------------------------------

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


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
        discovered = []
        registry = getattr(self.folder_paths, 'folder_names_and_paths', {})
        for model_type, definition in registry.items():
            if not isinstance(definition, tuple) or len(definition) < 2:
                continue
            paths, extensions = definition[0], definition[1]
            if isinstance(paths, (str, Path)):
                paths = [paths]
            normalized_extensions = tuple(sorted({
                str(extension).lower()
                if str(extension).startswith('.') else f'.{str(extension).lower()}'
                for extension in extensions
            }))
            for path in paths:
                discovered.append(DiscoveredModelLocation(
                    str(model_type), Path(path).absolute(), normalized_extensions))
        return discovered

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
