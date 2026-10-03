# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: __init__.py
# purpose: ComfyUI plugin entry point
# ---------------------------------------------------------------------------

import logging
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

try:
    import folder_paths
    from server import PromptServer

    from backend.config import initialize_logging, load_config
    from backend.environment import ComfyEnvironmentProvider, set_environment_provider
    from backend.repository.repository import start_repo
    from backend.server.access import API_PREFIX, AccessDenied, AccessPolicy
    from backend.server.proxy import create_proxy_handler
    from backend.server.public_routes import api_routes, static_routes

    async def authorize_comfy_request(request):
        """Preserve host middleware and profile checks; profiles are not a login.

        All routes remain on PromptServer's application, so its middleware runs
        first. Future authenticated hosts can supply a different adapter here.
        Static navigation has no Comfy-User header; API requests carry the profile
        selected by the Comfy launcher. No profile grants extra privileges.
        """
        if not request.path.startswith(f'{API_PREFIX}/'):
            return
        manager = getattr(PromptServer.instance, 'user_manager', None)
        resolve_user = getattr(manager, 'get_request_user_id', None)
        if not callable(resolve_user):
            raise AccessDenied('host_access_unavailable',
                               'ComfyUI user access checks are unavailable.', 503)
        try:
            user = resolve_user(request)
        except KeyError:
            raise AccessDenied('host_user_denied', 'ComfyUI did not accept this user.') from None
        if not user:
            raise AccessDenied('host_user_denied', 'ComfyUI did not accept this user.')

    def _start_archivist() -> None:
        environment = ComfyEnvironmentProvider(folder_paths)
        set_environment_provider(environment)
        config = load_config(mode='comfyui')
        runtime_directory = environment.runtime_data_directory()
        if runtime_directory is not None:
            config.use_runtime_data_directory(runtime_directory)
        initialize_logging(config)
        start_repo()
        from backend.server.gui import start_ui
        policy = AccessPolicy('comfyui')
        _server_thread, internal_port = start_ui(
            open_browser=False, block=False, port=0, policy=policy)
        proxy = create_proxy_handler(
            f'http://127.0.0.1:{internal_port}', policy.secret, authorize_comfy_request)
        routes = PromptServer.instance.routes
        for method, path in api_routes():
            if method == 'GET':
                routes.get(path, allow_head=False)(proxy)
            else:
                routes.route(method, path)(proxy)
        for path in static_routes(config.static_html):
            routes.get(path)(proxy)

    _start_archivist()
except ModuleNotFoundError as exc:
    if exc.name not in {'folder_paths', 'server'}:
        raise
except Exception:
    logging.getLogger('archivist.root').exception(
        'Model Archivist failed to initialize inside ComfyUI')
