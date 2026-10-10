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
_COMFY_NON_MODEL_TYPES = {'configs', 'custom_nodes', 'datasets'}


def _contains(root: Path, path: Path) -> bool:
    try:
        return os.path.commonpath((os.path.normcase(root), os.path.normcase(path))) == os.path.normcase(root)
    except ValueError:
        return False


@dataclass(frozen=True)
class DiscoveredModelLocation:
    model_type: str
    working_dir: Path
    extensions: tuple[str, ...]


class EnvironmentProvider(Protocol):
    mode: str

    def model_locations(self) -> list[DiscoveredModelLocation]: ...
    def workflow_locations(self, profile: str = 'default') -> list[Path]: ...
    def runtime_data_directory(self) -> Path | None: ...
    def default_working_roots(self) -> list[Path]: ...


class StandaloneEnvironmentProvider:
    mode = 'standalone'

    def default_working_roots(self) -> list[Path]:
        return [Path.home().absolute()]

    def model_locations(self) -> list[DiscoveredModelLocation]:
        return []

    def workflow_locations(self, profile: str = 'default') -> list[Path]:
        return []

    def runtime_data_directory(self) -> Path | None:
        return None


class ComfyEnvironmentProvider:
    """Read working locations from the live ComfyUI folder registry."""
    mode = 'comfyui'

    def __init__(self, folder_paths: Any):
        self.folder_paths = folder_paths

    def default_working_roots(self) -> list[Path]:
        roots = [Path(self.folder_paths.models_dir).absolute()]
        extra_paths = [location.working_dir for location in self.model_locations()
                       if not _contains(roots[0], location.working_dir)]
        siblings: dict[str, set[str]] = {}
        for path in extra_paths:
            parent_key = os.path.normcase(str(path.parent))
            siblings.setdefault(parent_key, set()).add(os.path.normcase(str(path)))

        # Group only the original locations; never promote consolidated parents again.
        for path in extra_paths:
            if len(siblings[os.path.normcase(str(path.parent))]) >= 2:
                path = path.parent
            if any(_contains(root, path) for root in roots):
                continue
            roots = [root for root in roots if not _contains(path, root)]
            roots.append(path)
        return roots

    def model_locations(self) -> list[DiscoveredModelLocation]:
        discovered: dict[str, DiscoveredModelLocation] = {}
        registry = getattr(self.folder_paths, 'folder_names_and_paths', {})
        get_output_directory = getattr(self.folder_paths, 'get_output_directory', None)
        output_root = (Path(get_output_directory()).absolute()
                       if callable(get_output_directory) else None)
        for model_type, definition in registry.items():
            if (str(model_type) in _COMFY_NON_MODEL_TYPES
                    or not isinstance(definition, tuple) or len(definition) < 2):
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
                # Retain links lexically so policy validation can reject them.
                working_dir = Path(path).absolute()
                if output_root is not None and _contains(output_root, working_dir):
                    continue
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

    def workflow_locations(self, profile: str = 'default') -> list[Path]:
        get_user_directory = getattr(self.folder_paths, 'get_user_directory', None)
        if not callable(get_user_directory):
            return []
        if not profile or profile.startswith('__') or profile in {'.', '..'} or any(
                character in profile for character in '/\\:'):
            raise ValueError('Invalid ComfyUI profile directory.')
        get_profile_directory = getattr(self.folder_paths, 'get_public_user_directory', None)
        directory = (get_profile_directory(profile) if callable(get_profile_directory)
                     else Path(get_user_directory()) / profile)
        if directory is None:
            return []
        return [(Path(directory) / 'workflows').absolute()]

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
