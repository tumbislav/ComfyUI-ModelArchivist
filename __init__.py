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
_internal_url = 'http://127.0.0.1:5173'
_hop_by_hop_headers = frozenset({
    'connection', 'content-length', 'keep-alive', 'proxy-authenticate',
    'proxy-authorization', 'te', 'trailer', 'transfer-encoding', 'upgrade'
})

try:
    import folder_paths
    from aiohttp import web as aiohttp_web
    from aiohttp import ClientSession
    from server import PromptServer

    from backend.config import load_config
    from backend.environment import ComfyEnvironmentProvider, set_environment_provider
    from backend.repository.repository import start_repo

    @PromptServer.instance.routes.route('*', '/model-archivist/{tail:.*}')
    async def archivist_proxy(request):
        """Expose the internal FastAPI service through ComfyUI's public origin."""
        target = f'{_internal_url}{request.rel_url}'
        request_headers = {
            name: value for name, value in request.headers.items()
            if name.lower() not in _hop_by_hop_headers and name.lower() != 'host'
        }
        try:
            async with ClientSession(auto_decompress=False) as session:
                async with session.request(
                        request.method, target, headers=request_headers,
                        data=await request.read(), allow_redirects=False) as upstream:
                    response_headers = {
                        name: value for name, value in upstream.headers.items()
                        if name.lower() not in _hop_by_hop_headers
                    }
                    return aiohttp_web.Response(
                        status=upstream.status, headers=response_headers,
                        body=await upstream.read())
        except OSError as error:
            return aiohttp_web.json_response(
                {'error': 'Model Archivist backend is unavailable', 'detail': str(error)},
                status=502)

    def _start_archivist() -> None:
        global _internal_url
        set_environment_provider(ComfyEnvironmentProvider(folder_paths))
        config = load_config(mode='comfyui')
        _internal_url = config.full_url
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
