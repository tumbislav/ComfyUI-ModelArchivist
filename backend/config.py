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
from enum import StrEnum

logger = logging.getLogger('model_archivist')


class ConfigError(StrEnum):
    INVALID_APP_ROOT = 'Application root not accessible'
    DUPLICATE_FOLDER = 'Duplicate path'
    FOLDER_NOT_FOUND = 'No such folder'
    MULTIPLE_PATHS_PER_TYPE = 'Multiple extra paths per type are not supported'


class ConfigException(Exception):
    def __init__(self, code: ConfigError, message: str):
        super().__init__()
        self.message = message
        self.code = code

    def __str__(self):
        return f'{self.code}: {self.message}'

@dataclass
class OptionsConfig(TOMLDataclass):
    update_json_metadata: bool = True

@dataclass
class WebConfig(TOMLDataclass):
    host: str
    port: int
    static_html: str

@dataclass
class DatabaseConfig(TOMLDataclass):
    database_file: str
    dbms: str

@dataclass
class WorkflowFolders(TOMLDataclass):
    active: str
    archive: str

@dataclass
class WorkflowConfig(TOMLDataclass):
    folders: list[WorkflowFolders]

@dataclass
class ExtraModels(TOMLDataclass):
    yaml: str
    archive: str

@dataclass
class ModelsConfig(TOMLDataclass):
    active: str
    archive: str
    extras: list[ExtraModels]
    types: dict[str, str]
    extensions: list[str]
    ignore: list[str] = field(default_factory=list)

@dataclass
class PathsConfig(TOMLDataclass):
    comfy: str
    archive: str
    user: str
    database: str
    html: str

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
    paths: PathsConfig
    database: DatabaseConfig
    models: ModelsConfig
    workflows: WorkflowConfig
    web: WebConfig
    options: OptionsConfig

    model_folders: dict[str, set[tuple[Path, Path]]] = field(default_factory=dict, metadata={'suppress': True})
    workflow_folders: list[tuple[Path, Path]] = field(default_factory=list, metadata={'suppress': True})
    all_archives: set[Path] = field(default_factory=set, metadata={'suppress': True})
    all_actives: set[Path] = field(default_factory=set, metadata={'suppress': True})

    app_root: Path | None = field(default=None, metadata={'suppress': True})
    user_root: Path | None = field(default=None, metadata={'suppress': True})
    comfy_root: Path | None = field(default=None, metadata={'suppress': True})
    cfg_file: Path | None = field(default=None, metadata={'suppress': True})
    archive_root: Path | None = field(default=None, metadata={'suppress': True})

    def save_changes(self):
        the_dict = self.to_toml_string()
        self.cfg_file.write_text(the_dict, encoding='utf-8')

    def path_from_string(self, path_str: str) -> Path:
        """
        TOML attributes are stored as strings that can be relative to one of the four roots.
        Convert the string to absolute Path, resolving the relative path if any.
        """
        if path_str.startswith('{$user}'):
            return (self.user_root / path_str[len('{$user}'):].lstrip('/')).resolve()
        elif path_str.startswith('{$app}'):
            return (self.app_root / path_str[len('{$app}'):].lstrip('/')).resolve()
        elif path_str.startswith('{$comfy}'):
            return (self.comfy_root / path_str[len('{$comfy}'):].lstrip('/')).resolve()
        elif path_str.startswith('{$archive}'):
            return (self.archive_root / path_str[len('{$archive}'):].lstrip('/')).resolve()
        else:
            return Path(path_str).resolve()

    def resolve_paths(self, app_root: Path, cfg_file: Path) -> None:
        """
        Find all the folders that the TOML refers to, check that they exist, create missing ones,
        check that there is no overlap.
        """
        self.app_root = app_root
        if not app_root.is_dir():
            raise ConfigException(ConfigError.INVALID_APP_ROOT, str(self.app_root))
        self.cfg_file = cfg_file
        # user_root, comfy_root and archive_root can be relative to app_root
        self.user_root = self.path_from_string(self.paths.user)
        self.comfy_root = self.path_from_string(self.paths.comfy)
        self.archive_root = self.path_from_string(self.paths.archive)

        self.resolve_model_paths()
        self.resolve_workflow_paths()

    def add_model_locations(self, model_type: str, active: Path, archive: Path, prevent_dupes: bool = True) -> None:
        """
        Store a resolved pair of active and archive dir for later use. Ensure they exist and
        check for duplicates.
        """
        if model_type in self.models.ignore:
            return
        if active in self.all_actives and prevent_dupes:
            raise ConfigException(ConfigError.DUPLICATE_FOLDER, str(active))
        if archive in self.all_archives and prevent_dupes:
            raise ConfigException(ConfigError.DUPLICATE_FOLDER, str(archive))
        self.all_actives.add(active)
        self.all_archives.add(archive)
        active.mkdir(exist_ok=True, parents=True)
        archive.mkdir(exist_ok=True, parents=True)
        if model_type not in self.model_folders:
            self.model_folders[model_type] = {(active, archive)}
        else:
            self.model_folders[model_type].add((active, archive))

    def resolve_model_paths(self) -> None:
        """
        Resolve model directories by model type.
        """
        model_root = self.path_from_string(self.models.active)
        archive_root = self.path_from_string(self.models.archive)

        # Start from the active models folder and update the archive models
        for model_type in (d.stem for d in model_root.iterdir() if d.is_dir()):
            self.add_model_locations(model_type, model_root / model_type, archive_root / model_type)
        # Then do the inverse
        for model_type in (d.stem for d in archive_root.iterdir() if d.is_dir()):
            self.add_model_locations(model_type, model_root / model_type, archive_root / model_type, False)
        # Then take care of the paths defined in extra_model.yaml files
        for extra in self.models.extras:
            self.locate_extra_paths(extra)

    def locate_extra_paths(self, extra: ExtraModels) -> None:
        """
        We have to match Comfy logic for reading the yaml file.
        """
        archive_dir = self.path_from_string(extra.archive)
        yaml_file = self.path_from_string(extra.yaml)
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
                raise ConfigException(ConfigError.MULTIPLE_PATHS_PER_TYPE, model_type)
            extra_path = Path(paths[0])
            if not extra_path.is_absolute():
                extra_path = base_path / extra_path
            self.add_model_locations(model_type, extra_path, archive_dir / model_type)

    def add_workflow_locations(self, wf: WorkflowFolders) -> None:
        """
        Store a resolved pair of active and archive dir for later use. Ensure they exist and
        check for duplicates.
        """
        active = self.path_from_string(wf.active)
        archive = self.path_from_string(wf.archive)
        if active in self.all_actives:
            raise ConfigException(ConfigError.DUPLICATE_FOLDER, str(active))
        if archive in self.all_archives:
            raise ConfigException(ConfigError.DUPLICATE_FOLDER, str(archive))
        self.all_actives.add(active)
        self.all_archives.add(archive)
        active.mkdir(exist_ok=True, parents=True)
        archive.mkdir(exist_ok=True, parents=True)
        self.workflow_folders.append((active, archive))

    def resolve_workflow_paths(self) -> None:
        """
        Workflow dirs are simple, just add each pair.
        """
        for wf in self.workflows.folders:
            self.add_workflow_locations(wf)

    def add_workflow_folders(self, active_dir: str, archive_dir: str) -> None:
        """
        Add a folder pair and save the changes.
        """
        self.add_workflow_locations(active_dir, archive_dir)
        self.workflows.folders.append(WorkflowFolders(active=active_dir, archive=archive_dir))
        self.save_changes()

    def remove_workflow_folders(self, active_dir: str, archive_dir: str) -> None:
        """
        Remove a folder pair and save changes. We locate it from the fully resolved paths and use
        the list index to match the strings.
        """
        active = self.path_from_string(active_dir)
        archive = self.path_from_string(archive_dir)
        self.workflow_folders.remove((active, archive))
        self.all_actives.remove(active)
        self.all_archives.remove(archive)

    def add_extra_models(self, yaml_filename: str, archive_dirname: str) -> None:
        raise NotImplementedError

    def remove_extra_models(self, yaml_filename: str, archive_dirname: str) -> None:
        raise NotImplementedError

    @property
    def db_file(self) -> Path:
        return self.path_from_string(self.database.database_file)

    @property
    def dbms(self) -> str:
        return self.database.dbms

    @property
    def static_html(self) -> Path:
        return self.path_from_string(self.web.static_html)

    @property
    def host(self) -> str:
        return self.web.host

    @property
    def http_port(self) -> int:
        return self.web.port

    @property
    def full_url(self) -> str:
        return f'http://{self.web.host}:{self.web.port}'

    @property
    def model_types(self) -> dict[str, str]:
        return self.models.types


_config: Configuration | None = None

def load_config(cfg_file: Path | None = None) -> Configuration:
    global _config
    app_root = Path(__file__).resolve().parent.parent
    if cfg_file is None:
        cfg_file = app_root / 'config.toml'
    else:
        cfg_file = Path(cfg_file).resolve()

    toml_string = cfg_file.read_text(encoding='utf-8')
    _config = Configuration.from_toml_string(toml_string)
    _config.resolve_paths(app_root, cfg_file)
    return _config

def get_config() -> Configuration:
    if _config is None:
        raise RuntimeError('Config is not initialized.')
    return _config
