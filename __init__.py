# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: __init__.py
# purpose: ComfyUI plugin entry point
# ---------------------------------------------------------------------------

import logging.config
import sys
from pathlib import Path

# ComfyUI imports custom nodes by file location without placing each custom-node
# directory on sys.path. The standalone application intentionally uses `backend`
# as its top-level package, so expose this repository root before importing it.
_plugin_root = str(Path(__file__).resolve().parent)
if _plugin_root not in sys.path:
    sys.path.insert(0, _plugin_root)

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
WEB_DIRECTORY = './web'
__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS', 'WEB_DIRECTORY']
_launch_url = 'http://127.0.0.1:5173'

try:
    import folder_paths
    from aiohttp import web as aiohttp_web
    from server import PromptServer

    from backend.config import load_config
    from backend.environment import ComfyEnvironmentProvider, set_environment_provider
    from backend.repository.repository import start_repo

    @PromptServer.instance.routes.get('/model-archivist/launch-url')
    async def archivist_launch_url(_request):
        return aiohttp_web.json_response({'url': _launch_url})

    def _start_archivist() -> None:
        global _launch_url
        set_environment_provider(ComfyEnvironmentProvider(folder_paths))
        config = load_config(mode='comfyui')
        _launch_url = config.full_url
        logging.config.dictConfig(config.log_config)
        start_repo()
        from backend.server.gui import start_ui
        start_ui(open_browser=False, block=False)

    _start_archivist()
except ModuleNotFoundError as exc:
    if exc.name not in {'folder_paths', 'server'}:
        raise
except Exception:
    logging.getLogger('archivist.root').exception(
        'Model Archivist failed to initialize inside ComfyUI')
