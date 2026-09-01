# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: gui.py
# purpose: REST interface to frontend GUI amd web server
# ---------------------------------------------------------------------------


from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import Response
import uvicorn
import webbrowser
from threading import Thread
import socket
import time

from backend.config import get_config
from .routers import (admin, collections, configuration, health, models, operations, tags,
                      user_types, workflows)

app = FastAPI(title='Model Archivist API', version='1.0.0')
APP_PREFIX = '/model-archivist'
API_PREFIX = f'{APP_PREFIX}/api'

config = get_config()

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=False,
    allow_methods=['*'],
    allow_headers=['*']
)

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
        app, host=config.host, port=port, log_config=config.uvicorn_log_config)
    return uvicorn.Server(server_config)

_mounted = False


def start_ui(open_browser: bool = True, block: bool = True,
             port: int | None = None) -> tuple[Thread, int]:
    """Start FastAPI on the configured port, or an OS-assigned private port."""
    global _mounted
    if not _mounted:
        app.mount(APP_PREFIX, app=AppFiles(directory=config.static_html, html=True),
                  name='static')
        _mounted = True
    requested_port = config.http_port if port is None else port
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        listener.bind((config.host, requested_port))
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
        webbrowser.open(f'http://{config.host}:{actual_port}{APP_PREFIX}/')
    if block:
        server_thread.join()
    return server_thread, actual_port

