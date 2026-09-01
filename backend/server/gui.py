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


def await_port(interval: float, timeout: float) -> bool:
    """Wait without busy-spinning while the background server binds its socket."""
    cutoff = time.time() + timeout
    interval = max(0.01, min(interval, 0.5))
    while time.time() < cutoff:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as the_socket:
            the_socket.settimeout(interval)
            try:
                the_socket.connect((config.host, config.http_port))
                return True
            except OSError:
                time.sleep(interval)
                interval = min(interval * 2.0, 0.5)
    return False

def run_server():
    uvicorn.run(app, host=config.host, port=config.http_port, log_config=config.uvicorn_log_config)

_mounted = False


def start_ui(open_browser: bool = True, block: bool = True):
    global _mounted
    if not _mounted:
        app.mount(APP_PREFIX, app=AppFiles(directory=config.static_html, html=True),
                  name='static')
        _mounted = True
    startup_errors: list[BaseException] = []

    def server_target() -> None:
        try:
            run_server()
        except BaseException as error:
            startup_errors.append(error)

    server_thread = Thread(target=server_target, daemon=True)
    server_thread.start()
    if await_port(0.1, 10):
        if open_browser:
            webbrowser.open(f'{config.full_url}{APP_PREFIX}/')
    else:
        if startup_errors:
            raise RuntimeError(
                f'Archivist web server failed to start: {startup_errors[0]}') from startup_errors[0]
        raise RuntimeError('Archivist web server was not ready within 10 seconds.')
    if block:
        server_thread.join()
    return server_thread

