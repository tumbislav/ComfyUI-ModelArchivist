# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: config.py
# purpose: Application config
# ---------------------------------------------------------------------------

import os
from pathlib import Path
import yaml
from fancy_dataclass import TOMLDataclass
from dataclasses import dataclass, field
from enum import StrEnum


class ConfigError(StrEnum):
    CONFIG_NOT_FOUND = 'Configuration file not found'
    CONFIG_UNREADABLE = 'Configuration file not readable'
    INVALID_CONFIG = 'Invalid configuration file'
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
class LoggingConfig(TOMLDataclass):
    level: str
    sql_level: str
    file: str

@dataclass
class OptionsConfig(TOMLDataclass):
    update_json_metadata: bool
    ignore_unknown_types: bool
    always_recalc_hashes: bool

@dataclass
class WebConfig(TOMLDataclass):
    host: str
    port: int
    static_html: str

@dataclass
class DatabaseConfig(TOMLDataclass):
    database_file: str
    dbms_prefix: str

@dataclass
class WorkflowFolders(TOMLDataclass):
    working: str
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
    working: str
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
    logging: LoggingConfig

    model_folders: dict[str, set[tuple[Path, Path]]] = field(default_factory=dict, metadata={'suppress': True})
    workflow_folders: list[tuple[Path, Path]] = field(default_factory=list, metadata={'suppress': True})
    all_archive: set[Path] = field(default_factory=set, metadata={'suppress': True})
    all_working: set[Path] = field(default_factory=set, metadata={'suppress': True})

    model_working_accessible: bool = field(default=True, metadata={'suppress': True})
    model_archive_accessible: bool = field(default=True, metadata={'suppress': True})
    workflow_working_accessible: bool = field(default=True, metadata={'suppress': True})
    workflow_archive_accessible: bool = field(default=True, metadata={'suppress': True})

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
        self.model_working_accessible = True
        self.model_archive_accessible = True
        self.workflow_working_accessible = True
        self.workflow_archive_accessible = True
        # user_root, comfy_root and archive_root can be relative to app_root
        self.user_root = self.path_from_string(self.paths.user)
        self.comfy_root = self.path_from_string(self.paths.comfy)
        self.archive_root = self.path_from_string(self.paths.archive)

        self.resolve_model_paths()
        self.resolve_workflow_paths()

    def ensure_folder_accessible(self, folder: Path, flag: str) -> None:
        """Create a folder when needed and clear its accessibility flag on failure."""
        try:
            folder.mkdir(exist_ok=True, parents=True)
            next(folder.iterdir(), None)
            if not os.access(folder, os.R_OK | os.W_OK):
                setattr(self, flag, False)
        except OSError:
            setattr(self, flag, False)

    def add_model_locations(self, model_type: str, working: Path, archive: Path, prevent_dupes: bool = True) -> None:
        """
        Store a resolved pair of working and archive dir for later use. Ensure they exist and
        check for duplicates.
        """
        if model_type in self.models.ignore:
            return
        if working in self.all_working and prevent_dupes:
            raise ConfigException(ConfigError.DUPLICATE_FOLDER, str(working))
        if archive in self.all_archive and prevent_dupes:
            raise ConfigException(ConfigError.DUPLICATE_FOLDER, str(archive))
        self.all_working.add(working)
        self.all_archive.add(archive)
        self.ensure_folder_accessible(working, 'model_working_accessible')
        self.ensure_folder_accessible(archive, 'model_archive_accessible')
        if model_type not in self.model_folders:
            self.model_folders[model_type] = {(working, archive)}
        else:
            self.model_folders[model_type].add((working, archive))

    def resolve_model_paths(self) -> None:
        """
        Resolve model directories by model type.
        """
        model_root = self.path_from_string(self.models.working)
        archive_root = self.path_from_string(self.models.archive)

        # Start from the working models folder and update the archive models
        try:
            model_dirs = list(model_root.iterdir())
        except OSError:
            self.model_working_accessible = False
            model_dirs = []
        for model_type in (d.stem for d in model_dirs if d.is_dir()):
            self.add_model_locations(model_type, model_root / model_type, archive_root / model_type)
        # Then do the inverse
        try:
            archive_dirs = list(archive_root.iterdir())
        except OSError:
            self.model_archive_accessible = False
            archive_dirs = []
        for model_type in (d.stem for d in archive_dirs if d.is_dir()):
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

    def add_workflow_locations(self, working: Path, archive: Path) -> None:
        """
        Store a resolved pair of working and archive dir for later use. Ensure they exist and
        check for duplicates.
        """
        if working in self.all_working:
            raise ConfigException(ConfigError.DUPLICATE_FOLDER, str(working))
        if archive in self.all_archive:
            raise ConfigException(ConfigError.DUPLICATE_FOLDER, str(archive))
        self.all_working.add(working)
        self.all_archive.add(archive)
        self.ensure_folder_accessible(working, 'workflow_working_accessible')
        self.ensure_folder_accessible(archive, 'workflow_archive_accessible')
        self.workflow_folders.append((working, archive))

    def resolve_workflow_paths(self) -> None:
        """
        Workflow dirs are simple, just add each pair.
        """
        for wf in self.workflows.folders:
            self.add_workflow_locations(self.path_from_string(wf.working), self.path_from_string(wf.archive))

    @property
    def read_only(self) -> bool:
        return not all((
            self.model_working_accessible,
            self.model_archive_accessible,
            self.workflow_working_accessible,
            self.workflow_archive_accessible,
        ))

    def add_workflow_folders(self, working_dir: str, archive_dir: str) -> None:
        """
        Add a folder pair and save the changes.
        """
        self.add_workflow_locations(self.path_from_string(working_dir), self.path_from_string(archive_dir))
        self.workflows.folders.append(WorkflowFolders(working=working_dir, archive=archive_dir))
        self.save_changes()

    def remove_workflow_folders(self, working_dir: str, archive_dir: str) -> None:
        """
        Remove a folder pair and save changes. We locate it from the fully resolved paths and use
        the list index to match the strings.
        """
        working = self.path_from_string(working_dir)
        archive = self.path_from_string(archive_dir)
        self.workflow_folders.remove((working, archive))
        self.all_working.remove(working)
        self.all_archive.remove(archive)

    def add_extra_models(self, yaml_filename: str, archive_dirname: str) -> None:
        raise NotImplementedError

    def remove_extra_models(self, yaml_filename: str, archive_dirname: str) -> None:
        raise NotImplementedError

    @property
    def db_file(self) -> Path:
        return self.path_from_string(self.database.database_file)

    @property
    def dbms_prefix(self) -> str:
        return self.database.dbms_prefix

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
    def model_extensions(self) -> list[str]:
        return self.models.extensions

    @property
    def model_types(self) -> dict[str, str]:
        return self.models.types

    @property
    def log_file(self) -> str:
        return str(self.path_from_string(self.logging.file))

    @property
    def sql_log_level(self) -> str:
        return self.logging.sql_level

    @property
    def log_config(self) -> dict:
        filename = str(self.log_file)
        return {
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': {
                'default': {
                    'format': 'ARCHIVIST %(asctime)s - %(levelname)s: %(funcName)s::%(message)s',
                    'datefmt': '%Y-%m-%d %H:%M:%S'
                },
                'database': {
                    'format': 'DATABASE  %(asctime)s - %(levelname)s: %(funcName)s::%(message)s',
                    'datefmt': '%Y-%m-%d %H:%M:%S'
                },
                'files': {
                    'format': 'FILES     %(asctime)s - %(levelname)s: %(funcName)s!%(thread)d::%(message)s',
                    'datefmt': '%Y-%m-%d %H:%M:%S'
                },
                'core': {
                    'format': 'CORE      %(asctime)s - %(levelname)s: %(funcName)s!%(thread)d::%(message)s',
                    'datefmt': '%Y-%m-%d %H:%M:%S'
                }
            },
            'handlers': {
                'default': {
                    'formatter': 'default',
                    'class': 'logging.FileHandler',
                    'filename': filename
                },
                'database': {
                    'formatter': 'database',
                    'class': 'logging.FileHandler',
                    'filename': filename
                },
                'files': {
                    'formatter': 'files',
                    'class': 'logging.FileHandler',
                    'filename': filename
                },
                'core': {
                    'formatter': 'core',
                    'class': 'logging.FileHandler',
                    'filename': filename
                }
            },
            'loggers': {
                'archivist': {
                    'handlers': ['default'],
                    'level': self.logging.level,
                    'propagate': False
                },
                'archivist.database': {
                    'handlers': ['database'],
                    'level': self.logging.level,
                    'propagate': False
                },
                'archivist.files': {
                    'handlers': ['files'],
                    'level': self.logging.level,
                    'propagate': False
                },
                'archivist.core': {
                    'handlers': ['core'],
                    'level': self.logging.level,
                    'propagate': False
                }
            }
        }

    @property
    def uvicorn_log_config(self) -> dict:
        filename = str(self.path_from_string(self.logging.file))
        return {
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': {
                'default': {
                    '()': 'uvicorn.logging.DefaultFormatter',
                    'fmt': 'UVICORN   %(asctime)s - %(levelname)s: %(message)s',
                    'datefmt': '%Y-%m-%d %H:%M:%S',
                },
                'access': {
                    '()': 'uvicorn.logging.AccessFormatter',
                    'fmt': 'REQUEST   %(asctime)s - %(levelname)s: %(client_addr)s - "%(request_line)s" %(status_code)s',
                    'datefmt': '%Y-%m-%d %H:%M:%S',
                },
            },
            'handlers': {
                'default': {
                    'formatter': 'default',
                    'class': 'logging.FileHandler',
                    'filename': filename
                },
                'access': {
                    'formatter': 'access',
                    'class': 'logging.FileHandler',
                    'filename': filename
                },
            },
            'loggers': {
                'uvicorn': {
                    'handlers': ['default'],
                    'level': self.logging.level,
                    'propagate': False
                },
                'uvicorn.error': {
                    'level': self.logging.level
                },
                'uvicorn.access': {
                    'handlers': ['access'], 
                    'level': self.logging.level, 
                    'propagate': False
                },
            },
        }


_config: Configuration | None = None

def load_config(cfg_file: Path | None = None) -> Configuration:
    global _config
    app_root = Path(__file__).resolve().parent.parent
    if cfg_file is None:
        cfg_file = app_root / 'config.toml'
    else:
        cfg_file = Path(cfg_file).resolve()

    try:
        toml_string = cfg_file.read_text(encoding='utf-8')
    except FileNotFoundError as error:
        raise ConfigException(ConfigError.CONFIG_NOT_FOUND, str(cfg_file)) from error
    except OSError as error:
        raise ConfigException(ConfigError.CONFIG_UNREADABLE, f'{cfg_file}: {error}') from error

    try:
        config = Configuration.from_toml_string(toml_string)
        required_sections = ('paths', 'database', 'models', 'workflows', 'web', 'options', 'logging')
        missing_sections = [name for name in required_sections if getattr(config, name, None) is None]
        if missing_sections:
            raise ValueError(f'missing sections: {", ".join(missing_sections)}')
    except Exception as error:
        raise ConfigException(ConfigError.INVALID_CONFIG, f'{cfg_file}: {error}') from error

    config.resolve_paths(app_root, cfg_file)
    _config = config
    return config

def get_config() -> Configuration:
    if _config is None:
        raise RuntimeError('Config is not initialized.')
    return _config
