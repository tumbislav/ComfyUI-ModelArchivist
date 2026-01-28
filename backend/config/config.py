# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: config.py
# purpose: Application configuration
# ---------------------------------------------------------------------------

from typing import Dict
import tomllib
import tomli_w
from pathlib import Path
import logging

logger = logging.getLogger('model_archivist')


class Configuration:
    """
    Config defines the folders where models are stored and the location of the database
    which we use to track them. Changing the config file lets us work with different
    instances of Comfy.
    """

    def __init__(self) -> None:
        self.app_root = None
        self.cfg_root = None
        self.cfg_file = None
        self.comfy_root = None
        self.inactive_root = None
        self.archive_root = None
        self.db_path = None
        self.model_extensions = None
        self.model_types = None
        self.extra_models = None
        self.restrict_to_known_types = False # for future upgrades
        self.workflow_active = None
        self.workflow_inactive = None
        self.workflow_archive = None
        self.html_root = None
        self.url = None
        self.port = None

    def attach(self, cfg_file: Path | None, app_root: Path) -> None:
        self.app_root = app_root
        if cfg_file is None:
            self.cfg_root = Path(__file__).parent
        else:
            self.cfg_root = cfg_file.parent
        self.cfg_file = self.cfg_root / 'config.toml'

        raw = self.load_toml()
        self.extract(raw)

    def load_toml(self) -> Dict | None:
        if not self.cfg_file.exists():
            logger.warning('config.toml file not found. Creating a default one.')
            conf = self.create_default()
            self.write_toml(conf)
            return conf
        else:
            try:
                return tomllib.loads(self.cfg_file.read_text(encoding='utf-8'))
            except Exception as e:  # noqa
                logger.warning('Cannot read config file.')
                return None

    def write_toml(self, raw: Dict | None = None) -> None:
        if raw is None:
            raw = {'folder_paths': {'comfy_root': self.comfy_root,
                                    'inactive_root': self.inactive_root,
                                    'archive_root': self.archive_root,
                                    'db_paths': self.db_path},
#TODO workflow folders
                   'config': {'restrict_to_known_types': self.restrict_to_known_types},
                   'model_extensions': self.model_extensions,
                   'model_types': self.model_types,
                   'extra_models': self.extra_models}
        try:
            self.cfg_file.write_text(tomli_w.dumps(raw), encoding='utf-8')
        except Exception as e: # noqa
            logger.critical('Cannot write config file.')

    def create_default(self) -> Dict:
        """
        Try to find comfy_root, assuming we're sitting in a (sub)subdir
        """
        root = self.app_root.parent
        if (root /'models').is_dir():
            logger.info(f'Trying {root} as ComfyUI root')
        else:
            root = root.parent
            if (root / 'models').is_dir():
                logger.info(f'Trying {root} as ComfyUI root')
            else:
                logger.critical('ComfyUI not found, giving up.')
                raise Exception('ComfyUI not found.')
        return {'folder_paths': {'comfy_root': root,
                                 'inactive_root': root / 'inactive_models',
                                 'archive_root': root / 'model_archive',
                                 'db_paths': root / 'model_archivist.db'},
                'config': {'restrict_to_known_types': False},
                'model_extensions': ['safetensors', 'pth'],
                'model_types': {'checkpoints': 'Checkpoint', 'loras': 'LoRA'},
                'extra_models': [{'yaml': root / 'extra_model_paths.yaml'}]}

    def extract(self, raw: Dict) -> None:
        try:
            self.comfy_root = Path(raw['folder_paths']['comfy_root']).resolve()
            self.inactive_root = Path(raw['folder_paths']['inactive_root']).resolve()
            if 'archive_root' not in raw['folder_paths']:
                archive_root = None
            else:
                archive_root = Path(raw['folder_paths']['archive_root']).resolve()
            self.archive_root = archive_root
            self.db_path = Path(raw['folder_paths'].get('database',
                                                        self.comfy_root / 'model_archivist.db')).resolve()
        except KeyError as e:
            logger.critical(f'Missing paths in config.toml, cannot continue\n{e}')
            return

        self.model_extensions = {ext.lower() for ext in raw['models']['extensions']}
        self.model_types = {ty.lower(): disp for ty, disp in raw['model_types'].items()}
        extras_list = raw.get('extra_model_paths', [])
        settings = raw.get('settings', {})
        self.restrict_to_known_types = settings.get('restrict_to_known_types', False)
        self.extra_models = []
        for extras in extras_list:
            extras['yaml'] = Path(extras['yaml']).resolve()
            if 'inactive' in extras:
                extras['inactive'] = Path(extras['inactive']).resolve()
            else:
                extras['inactive'] = self.inactive_root
            if 'archive' in extras:
                extras['archive'] = Path(extras['archive']).resolve()
            else:
                extras['archive'] = self.archive_root
            self.extra_models.append(extras)
        web_params = raw.get('web', {})
        self.html_root = web_params.get('html_root', self.app_root.parent.parent / 'frontend' / 'build')
        url_base = web_params.get('url_base', 'http://127.0.0.1')
        self.port = web_params.get('port', 5173)
        self.url = f'{url_base}:{self.port}'


config = Configuration()
