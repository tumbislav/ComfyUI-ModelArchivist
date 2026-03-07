# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: config.py
# purpose: Application config
# ---------------------------------------------------------------------------

from pathlib import Path
import logging
import yaml
from fancy_dataclass import TOMLDataclass
from dataclasses import dataclass, field
from .model.object_types import ArchivistException, ArchivistError

logger = logging.getLogger('model_archivist')

@dataclass
class ModelOptions(TOMLDataclass):
    extensions: list[str]
    types: dict[str, str]

@dataclass
class ExtraModels(TOMLDataclass):
    yaml: str
    archive: str

@dataclass
class WorkflowFolders(TOMLDataclass):
    active: str
    archive: str

@dataclass
class ConfigFolders(TOMLDataclass):
    comfy: str
    archive: str
    database: str
    extra_models: list[ExtraModels]
    workflows: list[WorkflowFolders]
    ignore: list[str] = field(default_factory=list)

@dataclass
class WebConfig(TOMLDataclass):
    base_url: str
    port: int

@dataclass
class ConfigOptions(TOMLDataclass):
    update_json_metadata: bool = True

@dataclass
class Configuration(TOMLDataclass, comment=
"""---------------------------------------------------------------------------
system: ModelArchivist
file: config.toml
purpose: Application config
---------------------------------------------------------------------------"""):
    """
    Config defines the folders where models are stored and the location of the database
    which we use to track them. Changing the config file lets you work with different
    instances of Comfy.
    """
    folders: ConfigFolders
    models: ModelOptions
    web: WebConfig
    options: ConfigOptions
    model_folders: dict[str, set[tuple[Path, Path]]] = field(default_factory=dict, metadata={'suppress': True})
    workflow_folders: set[tuple[Path, Path]] = field(default_factory=set, metadata={'suppress': True})

    app_root: Path | None = field(default=None, metadata={'suppress': True})
    user_root: Path | None = field(default=None, metadata={'suppress': True})
    comfy_root: Path | None = field(default=None, metadata={'suppress': True})
    cfg_file: Path | None = field(default=None, metadata={'suppress': True})
    archive_root: Path | None = field(default=None, metadata={'suppress': True})

    def save_changes(self):
        the_dict = self.to_toml_string()
        self.cfg_file.write_text(the_dict, encoding='utf-8')

    def add_model_folders(self, model_type, model_dir, archive_dir):
        if model_type in self.folders.ignore:
            return
        model_dir.mkdir(exist_ok=True, parents=True)
        archive_dir.mkdir(exist_ok=True, parents=True)
        if model_type not in self.model_folders:
            self.model_folders[model_type] = {model_dir, archive_dir}
        else:
            self.model_folders[model_type].add((model_dir, archive_dir))

    def path_from_string(self, path_str: str) -> Path:
        if '{$user}' in path_str:
            return (self.user_root / path_str.replace('{$user}', '')).resolve()
        elif '{$app}' in path_str:
            return (self.app_root / path_str.replace('{$app}', '')).resolve()
        elif '{$comfy}' in path_str:
            return (self.comfy_root / path_str.replace('{$comfy}', '')).resolve()
        elif '{$archive}' in path_str:
            return (self.archive_root / path_str.replace('{$archive}', '')).resolve()
        else:
            return Path(path_str).resolve()

    def resolve_paths(self, app_root: Path, user_root: Path, cfg_file: Path) -> None:
        self.app_root = app_root
        self.user_root = user_root
        self.cfg_file = cfg_file
        self.comfy_root = self.path_from_string(self.folders.comfy)
        self.archive_root = self.path_from_string(self.folders.archive)

        model_root = self.path_from_string('{$comfy}/models')
        archive_root = Path(self.folders.archive)

        # Start from the active models folder and update the archive models
        for model_type in (d.stem for d in model_root.iterdir() if d.is_dir()):
            self.add_model_folders(model_type, model_root / model_type, archive_root / model_type)
        # Now do the inverse
        for model_type in (d.stem for d in archive_root.iterdir() if d.is_dir()):
            self.add_model_folders(model_type, model_root / model_type, archive_root / model_type)
        archive_locations = {archive_root}
        for yaml_file, extra_archive_root in self.folders.extra_models:
            if extra_archive_root in archive_locations:
                raise ArchivistException(ArchivistError.DUPLICATE_ARCHIVE, extra_archive_root)
            self.locate_extra_paths(yaml_file, extra_archive_root)
        for wf in self.folders.workflows:
            self.workflow_folders.add((self.path_from_string(wf.active), self.path_from_string(wf.archive)))

    def locate_extra_paths(self, yaml_file: Path, archive_path: Path) -> None:
        extra_config = yaml.safe_load(yaml_file.read_text(encoding='utf-8'))
        config_set = extra_config.get('comfyui', {})

        if 'base_path' in config_set:
            base_path = Path(config_set.pop('base_path'))
            if not base_path.is_absolute():
                base_path = yaml_file.parent / base_path
        else:
            base_path = yaml_file.parent

        for model_type, extras in config_set.items():
            if not isinstance(extras, str):
                continue
            paths = extras.split('\n')
            if len(paths) > 1:
                raise ArchivistException(ArchivistError.MULTIPLE_PATHS_PER_TYPE, model_type)
            extra_path = Path(paths[0])
            if not extra_path.is_absolute():
                extra_path = base_path / extra_path
            self.add_model_folders(model_type, extra_path, archive_path / model_type)

_config: Configuration | None = None

def load_config(cfg_file: Path | None = None, user_root: Path | None = None) -> Configuration:
    global _config
    app_root = Path(__file__).resolve().parent.parent.parent
    if cfg_file is None:
        cfg_file = app_root / 'config.toml'
    else:
        cfg_file = Path(cfg_file)

    toml_string = cfg_file.read_text(encoding='utf-8')
    _config = Configuration.from_toml_string(toml_string)
    _config.resolve_paths(app_root, user_root, cfg_file)
    return _config

def get_config() -> Configuration | None:
    return _config
