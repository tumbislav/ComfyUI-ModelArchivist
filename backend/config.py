# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: config.py
# purpose: Bootstrap and resolved runtime configuration
# ---------------------------------------------------------------------------

import os
import tomllib
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

class ConfigError(StrEnum):
    CONFIG_NOT_FOUND = 'Configuration file not found'
    CONFIG_UNREADABLE = 'Configuration file not readable'
    INVALID_CONFIG = 'Invalid configuration file'
    INVALID_APP_ROOT = 'Application root not accessible'
    DUPLICATE_FOLDER = 'Duplicate path'
    MULTIPLE_PATHS_PER_TYPE = 'Multiple standalone paths per type are not supported'
    RUNTIME_DIRECTORY_UNREADABLE = 'Runtime data directory not accessible'


class ConfigException(Exception):
    def __init__(self, code: ConfigError, message: str):
        super().__init__()
        self.message = message
        self.code = code

    def __str__(self):
        return f'{self.code}: {self.message}'


@dataclass
class LoggingConfig:
    level: str
    sql_level: str
    file: str


@dataclass
class WebConfig:
    host: str
    port: int
    static_html: str


@dataclass
class DatabaseConfig:
    database_file: str


@dataclass
class OptionsConfig:
    update_json_metadata: bool = True
    ignore_unknown_types: bool = False
    always_recalc_hashes: bool = False


@dataclass
class Configuration:
    """Bootstrap values plus database/environment-derived runtime settings."""
    database: DatabaseConfig
    web: WebConfig
    logging: LoggingConfig

    app_root: Path | None = field(default=None, metadata={'suppress': True})
    cfg_file: Path | None = field(default=None, metadata={'suppress': True})
    mode: str = field(default='standalone', metadata={'suppress': True})
    setup_required: bool = field(default=True, metadata={'suppress': True})
    options: OptionsConfig = field(default_factory=OptionsConfig, metadata={'suppress': True})
    model_folders: dict[str, set[tuple[Path, Path]]] = field(
        default_factory=dict, metadata={'suppress': True})
    workflow_folders: list[tuple[Path, Path]] = field(
        default_factory=list, metadata={'suppress': True})
    all_archive: set[Path] = field(default_factory=set, metadata={'suppress': True})
    all_working: set[Path] = field(default_factory=set, metadata={'suppress': True})
    model_extensions_by_type: dict[str, list[str]] = field(
        default_factory=dict, metadata={'suppress': True})
    model_type_labels: dict[str, str] = field(
        default_factory=dict, metadata={'suppress': True})
    unmapped_model_folders: dict[str, list[Path]] = field(
        default_factory=dict, metadata={'suppress': True})
    unmapped_workflow_folders: list[Path] = field(
        default_factory=list, metadata={'suppress': True})
    model_working_accessible: bool = field(default=True, metadata={'suppress': True})
    model_archive_accessible: bool = field(default=True, metadata={'suppress': True})
    workflow_working_accessible: bool = field(default=True, metadata={'suppress': True})
    workflow_archive_accessible: bool = field(default=True, metadata={'suppress': True})

    def initialize(self, app_root: Path, cfg_file: Path, mode: str = 'standalone') -> None:
        if not app_root.is_dir():
            raise ConfigException(ConfigError.INVALID_APP_ROOT, str(app_root))
        self.app_root = app_root
        self.cfg_file = cfg_file
        self.mode = mode

    def use_runtime_data_directory(self, directory: Path) -> None:
        """Place mutable bootstrap files in an environment-owned directory."""
        directory = Path(directory).absolute()
        try:
            directory.mkdir(exist_ok=True, parents=True)
            next(directory.iterdir(), None)
            if not os.access(directory, os.R_OK | os.W_OK):
                raise PermissionError('directory is not readable and writable')
        except OSError as error:
            raise ConfigException(
                ConfigError.RUNTIME_DIRECTORY_UNREADABLE,
                f'{directory}: {error}') from error
        self.database.database_file = str(directory / 'model_archivist.db')
        self.logging.file = str(directory / 'archivist.log')

    def path_from_string(self, value: str) -> Path:
        if value.startswith('{$app}'):
            return (self.app_root / value[len('{$app}'):].lstrip('/\\')).resolve()
        return Path(value).resolve()

    def reset_runtime_paths(self) -> None:
        self.model_folders.clear()
        self.workflow_folders.clear()
        self.all_archive.clear()
        self.all_working.clear()
        self.unmapped_model_folders.clear()
        self.unmapped_workflow_folders.clear()
        self.model_working_accessible = True
        self.model_archive_accessible = True
        self.workflow_working_accessible = True
        self.workflow_archive_accessible = True

    def _check_folder(self, folder: Path, flag: str) -> None:
        try:
            folder.mkdir(exist_ok=True, parents=True)
            next(folder.iterdir(), None)
            if not os.access(folder, os.R_OK | os.W_OK):
                setattr(self, flag, False)
        except OSError:
            setattr(self, flag, False)

    def add_model_locations(self, model_type: str, working: Path, archive: Path) -> None:
        working, archive = Path(working), Path(archive)
        pair = (working, archive)
        if pair in self.model_folders.get(model_type, set()):
            return
        if working in self.all_working or archive in self.all_archive:
            duplicate = working if working in self.all_working else archive
            raise ConfigException(ConfigError.DUPLICATE_FOLDER, str(duplicate))
        if self.mode == 'standalone' and self.model_folders.get(model_type):
            raise ConfigException(ConfigError.MULTIPLE_PATHS_PER_TYPE, model_type)
        self.all_working.add(working)
        self.all_archive.add(archive)
        self._check_folder(working, 'model_working_accessible')
        self._check_folder(archive, 'model_archive_accessible')
        self.model_folders.setdefault(model_type, set()).add(pair)

    def add_workflow_locations(self, working: Path, archive: Path) -> None:
        working, archive = Path(working), Path(archive)
        if self.mode == 'standalone' and self.workflow_folders:
            raise ConfigException(ConfigError.MULTIPLE_PATHS_PER_TYPE, 'workflow')
        if working in self.all_working or archive in self.all_archive:
            duplicate = working if working in self.all_working else archive
            raise ConfigException(ConfigError.DUPLICATE_FOLDER, str(duplicate))
        self.all_working.add(working)
        self.all_archive.add(archive)
        self._check_folder(working, 'workflow_working_accessible')
        self._check_folder(archive, 'workflow_archive_accessible')
        self.workflow_folders.append((working, archive))

    @property
    def configured(self) -> bool:
        return not self.setup_required

    @property
    def read_only(self) -> bool:
        return not all((self.model_working_accessible, self.model_archive_accessible,
                        self.workflow_working_accessible,
                        self.workflow_archive_accessible))

    @property
    def db_file(self) -> Path:
        return self.path_from_string(self.database.database_file)

    @property
    def dbms_prefix(self) -> str:
        return 'sqlite:///'

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
        return list(dict.fromkeys(extension for values in self.model_extensions_by_type.values()
                                  for extension in values))

    @property
    def model_types(self) -> dict[str, str]:
        return self.model_type_labels

    @property
    def log_file(self) -> str:
        return str(self.path_from_string(self.logging.file))

    @property
    def sql_log_level(self) -> str:
        return self.logging.sql_level

    @property
    def log_config(self) -> dict:
        filename = self.log_file
        formatters = {
            name: {'format': pattern, 'datefmt': '%Y-%m-%d %H:%M:%S'}
            for name, pattern in {
                'default': 'ARCHIVIST %(asctime)s - %(levelname)s: %(funcName)s::%(message)s',
                'database': 'DATABASE  %(asctime)s - %(levelname)s: %(funcName)s::%(message)s',
                'files': 'FILES     %(asctime)s - %(levelname)s: %(funcName)s!%(thread)d::%(message)s',
                'core': 'CORE      %(asctime)s - %(levelname)s: %(funcName)s!%(thread)d::%(message)s',
            }.items()
        }
        handlers = {name: {'formatter': name, 'class': 'logging.FileHandler',
                           'filename': filename} for name in formatters}
        loggers = {'archivist': {'handlers': ['default'], 'level': self.logging.level,
                                 'propagate': False}}
        for name in ('database', 'files', 'core'):
            loggers[f'archivist.{name}'] = {
                'handlers': [name], 'level': self.logging.level, 'propagate': False}
        return {'version': 1, 'disable_existing_loggers': False,
                'formatters': formatters, 'handlers': handlers, 'loggers': loggers}

    @property
    def uvicorn_log_config(self) -> dict:
        return self.log_config


_config: Configuration | None = None


def load_config(cfg_file: Path | None = None, mode: str = 'standalone') -> Configuration:
    global _config
    app_root = Path(__file__).resolve().parent.parent
    cfg_file = app_root / 'config.toml' if cfg_file is None else Path(cfg_file).resolve()
    try:
        toml_string = cfg_file.read_text(encoding='utf-8')
    except FileNotFoundError as error:
        raise ConfigException(ConfigError.CONFIG_NOT_FOUND, str(cfg_file)) from error
    except OSError as error:
        raise ConfigException(ConfigError.CONFIG_UNREADABLE, f'{cfg_file}: {error}') from error
    try:
        values = tomllib.loads(toml_string)
        missing = [name for name in ('database', 'web', 'logging') if name not in values]
        if missing:
            raise ValueError(f'missing sections: {", ".join(missing)}')
        config = Configuration(
            database=DatabaseConfig(**values['database']),
            web=WebConfig(**values['web']),
            logging=LoggingConfig(**values['logging']))
        if (not isinstance(config.database.database_file, str)
                or not isinstance(config.web.host, str)
                or not isinstance(config.web.port, int)
                or isinstance(config.web.port, bool)
                or not 1 <= config.web.port <= 65535
                or not isinstance(config.web.static_html, str)
                or not isinstance(config.logging.level, str)
                or not isinstance(config.logging.sql_level, str)
                or not isinstance(config.logging.file, str)):
            raise ValueError('bootstrap setting has an invalid type or value')
    except Exception as error:
        raise ConfigException(ConfigError.INVALID_CONFIG, f'{cfg_file}: {error}') from error
    config.initialize(app_root, cfg_file, mode)
    _config = config
    return config


def get_config() -> Configuration:
    if _config is None:
        raise RuntimeError('Config is not initialized.')
    return _config
