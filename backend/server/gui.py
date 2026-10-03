# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: gui.py
# purpose: REST interface to frontend GUI amd web server
# ---------------------------------------------------------------------------


from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response, JSONResponse
import uvicorn
import webbrowser
from threading import Thread
import socket
import time

from backend.config import get_config
from .access import API_PREFIX, AccessDenied, AccessPolicy
from .public_routes import api_routes, registered_http_routes, static_routes
from .routers import (admin, collections, configuration, health, models, operations, tags,
                      user_types, workflows)

app = FastAPI(title='Model Archivist API', version='1.0.0',
              docs_url=None, redoc_url=None, openapi_url=None,
              redirect_slashes=False)

config = get_config()

access_policy: AccessPolicy | None = None


@app.middleware('http')
async def enforce_access(request: Request, call_next):
    if access_policy is None:
        return JSONResponse({'detail': {
            'code': 'access_unavailable', 'message': 'Access policy is not initialized.',
            'params': {}}}, status_code=503)
    try:
        access_policy.authorize(
            request.headers,
            api=request.url.path == API_PREFIX or request.url.path.startswith(f'{API_PREFIX}/'),
            scheme=request.url.scheme, host=request.headers.get('host', ''))
    except AccessDenied as error:
        return JSONResponse({'detail': error.detail()}, status_code=error.status)
    response = await call_next(request)
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Cache-Control'] = 'no-store'
    return response

app.include_router(models.router, prefix=API_PREFIX)
app.include_router(workflows.router, prefix=API_PREFIX)
app.include_router(user_types.router, prefix=API_PREFIX)
app.include_router(collections.router, prefix=API_PREFIX)
app.include_router(tags.router, prefix=API_PREFIX)
app.include_router(health.router, prefix=API_PREFIX)
app.include_router(admin.router, prefix=API_PREFIX)
app.include_router(operations.router, prefix=API_PREFIX)
app.include_router(configuration.router, prefix=API_PREFIX)


class AppFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        response: Response = await super().get_response(path, scope)
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response


def create_server(listener: socket.socket, port: int) -> uvicorn.Server:
    server_config = uvicorn.Config(
        app, host=listener.getsockname()[0], port=port,
        proxy_headers=False, log_config=config.uvicorn_log_config)
    return uvicorn.Server(server_config)

_mounted = False


def start_ui(open_browser: bool = True, block: bool = True,
             port: int | None = None, policy: AccessPolicy | None = None) -> tuple[Thread, int]:
    """Start FastAPI on the configured port, or an OS-assigned private port."""
    global _mounted, access_policy
    access_policy = policy or AccessPolicy(config.mode)
    if access_policy.mode != config.mode:
        raise ValueError('Access policy does not match the operating mode')
    if not _mounted:
        actual = registered_http_routes(app.routes)
        if actual != set(api_routes()):
            raise RuntimeError('API routes do not match the reviewed public route list')
        files = AppFiles(directory=config.static_html)

        def asset_handler(relative: str):
            async def serve(request: Request):
                return await files.get_response(relative, request.scope)
            return serve

        for path, relative in static_routes(config.static_html).items():
            app.add_api_route(path, asset_handler(relative), methods=['GET', 'HEAD'],
                              include_in_schema=False)
        _mounted = True
    requested_port = config.http_port if port is None else port
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        bind_host = '127.0.0.1' if config.mode == 'comfyui' else config.host
        listener.bind((bind_host, requested_port))
        listener.listen(2048)
        listener.setblocking(False)
    except BaseException:
        listener.close()
        raise
    actual_port = listener.getsockname()[1]
    server = create_server(listener, actual_port)
    startup_errors: list[BaseException] = []

    def server_target() -> None:
        try:
            server.run(sockets=[listener])
        except BaseException as error:
            startup_errors.append(error)

    server_thread = Thread(target=server_target, daemon=True)
    server_thread.start()
    cutoff = time.monotonic() + 10
    while not server.started and server_thread.is_alive() and time.monotonic() < cutoff:
        time.sleep(0.05)
    if not server.started:
        if startup_errors:
            raise RuntimeError(
                f'Archivist web server failed to start: {startup_errors[0]}') from startup_errors[0]
        raise RuntimeError('Archivist web server was not ready within 10 seconds.')
    if open_browser:
        browser_host = '127.0.0.1' if bind_host == '0.0.0.0' else bind_host
        webbrowser.open(access_policy.launch_url(f'http://{browser_host}:{actual_port}'))
    if block:
        server_thread.join()
    return server_thread, actual_port

