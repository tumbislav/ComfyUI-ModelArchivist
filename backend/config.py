# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: config.py
# purpose: Application config
# ---------------------------------------------------------------------------

from typing import Dict
import tomllib
import tomli_w
from pathlib import Path
import logging
from urllib.parse import urlparse

logger = logging.getLogger('model_archivist')


class Configuration:
    """
    Config defines the folders where models are stored and the location of the database
    which we use to track them. Changing the config file lets us work with different
    instances of Comfy.
    """

    def __init__(self) -> None:
        self.app_root = None
        self.cfg_file = None
        self.comfy_root = None
        self.archive_root = None
        self.db_path = None
        self.model_extensions = None
        self.ignore_types = None
        self.model_types = None
        self.extra_models = None
        self.workflow_active = None
        self.workflow_archive = None
        self.html_root = None
        self.url = None
        self.port = None
        self.update_json_metadata = None
        self.force_rehash = None
        self.reset_force_rehash = None
        self.ignore_unknown_types = None
        self.remove_inaccessible = None

    def attach(self, cfg_file: Path | None) -> None:
        self.app_root = Path(__file__).resolve().parent.parent
        if cfg_file is None:
            self.cfg_file = self.app_root / 'backend' / 'config.toml'
            logger.info('Configuration.attach: creating a default config.')
            self.create_default()
            self.write_toml()
        else:
            self.cfg_file = Path(cfg_file)
            self.load_toml()


    def load_toml(self) -> bool:
        if not self.cfg_file.exists():
            logger.warning(f'Configuration.load_toml: {self.cfg_file.name} file not found.')
            return False
        raw = tomllib.loads(self.cfg_file.read_text(encoding='utf-8'))
        self.extract(raw)
        return True

    def write_toml(self) -> None:
        raw = {'folders': {'comfy_root': self.comfy_root,
                           'archive_root': self.archive_root,
                           'db_paths': self.db_path,
                           'workflow_active': self.workflow_active,
                           'workflow_archive': self.workflow_archive
                           },
               'options': {'update_json_metadata': self.update_json_metadata,
                           'force_rehash': self.force_rehash,
                           'reset_force_rehash': self.reset_force_rehash,
                           'ignore_unknown_types': self.ignore_unknown_types,
                           'remove_inaccessible': self.remove_inaccessible
                           },
               'models': {
                    'extensions': self.model_extensions,
                    'ignore_types': self.ignore_types
               },
               'model_types': self.model_types,
               'extra_models': [{'yaml': y, 'archive': a} for y, a in self.extra_models]}
        self.cfg_file.write_text(tomli_w.dumps(raw), encoding='utf-8')

    def create_default(self):
        """
        Try to find comfy_root, assuming we're sitting in a (sub)subdir
        """
        self.comfy_root = self.app_root
        for _ in range(3):
            self.comfy_root = self.comfy_root.parent
            if (self.comfy_root / 'models').is_dir():
                logger.info(f'Configuration.create_default: setting {self.comfy_root} as ComfyUI root')
                break
        else:
            raise Exception('ComfyUI not found.')
        self.archive_root = self.comfy_root / 'model_archive'
        self.db_path = self.app_root / 'model_archivist.db'
        self.model_extensions = ['safetensors', 'pth', 'gguf']
        self.ignore_types = ['examples']
        self.model_types = {'checkpoints': 'Checkpoint', 'loras': 'LoRA'}
        self.extra_models = None
        self.workflow_active = self.comfy_root / 'user' / 'default' / 'workflows'
        self.workflow_archive = self.comfy_root / 'user' / 'default' / 'workflow_archive'
        self.html_root = self.app_root / 'frontend' / 'build'
        self.url = 'http://127.0.0.1:5173'
        self.port = urlparse(self.url).port
        self.update_json_metadata = True
        self.force_rehash = False
        self.reset_force_rehash = True
        self.ignore_unknown_types = False
        self.remove_inaccessible = True

    def extract(self, raw: Dict) -> None:
        """
        Map from TOML dictionary to class values
        """
        self.comfy_root = Path(raw['folders']['comfy_root']).resolve()
        if 'archive_root' not in raw['folders']:
            archive_root = None
        else:
            archive_root = Path(raw['folders']['archive_root']).resolve()
        self.archive_root = archive_root
        self.db_path = Path(raw['folders'].get('database', self.comfy_root / 'model_archivist.db')).resolve()
        self.model_extensions = [ext.lower() for ext in raw['models']['extensions']]
        self.ignore_types = [ty for ty in raw['models']['ignore_types']]

        # optional stuff for models
        self.model_types = {ty.lower(): disp for ty, disp in raw['model_types'].items()}
        self.extra_models = [(Path(extra['yaml']).resolve(), Path(extra['archive']).resolve())
                             for extra in raw.get('extra_models', [])]

        # web UI configurations
        web_params = raw.get('web', {})
        self.html_root = web_params.get('html_root', self.app_root / 'frontend' / 'build')
        self.url = web_params.get('url', 'http://127.0.0.1:5173')
        self.port = urlparse(self.url).port

        # options
        options = raw.get('options', {})
        self.update_json_metadata = options.get('update_json_metadata', True)
        self.force_rehash = options.get('force_rehash', False)
        self.reset_force_rehash = options.get('reset_force_rehash', True)
        self.remove_inaccessible = options.get('remove_inaccessible', True)


config = Configuration()
