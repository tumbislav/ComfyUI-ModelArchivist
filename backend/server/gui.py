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
from .routers import admin, collections, health, models, operations, tags, workflows

app = FastAPI(title='Model Archivist API', version='1.0.0')

config = get_config()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[config.http_port],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*']
)

app.include_router(models.router)
app.include_router(workflows.router)
app.include_router(collections.router)
app.include_router(tags.router)
app.include_router(health.router)
app.include_router(admin.router)
app.include_router(operations.router)


class AppFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        response: Response = await super().get_response(path, scope)
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response


def await_port(interval: float, timeout: float) -> bool:
    cutoff = time.time() + timeout
    while time.time() < cutoff:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as the_socket:
            the_socket.settimeout(interval)
            try:
                the_socket.connect((config.host, config.http_port))
                return True
            except OSError as e:
                interval *= 2.0
    return False

def run_server():
    uvicorn.run(app, host=config.host, port=config.http_port, log_config=config.uvicorn_log_config)

def start_ui():
    app.mount('/', app=AppFiles(directory=config.static_html, html=True), name='static')
    server_thread = Thread(target=run_server, daemon=True)
    server_thread.start()
    if await_port(0.1, 10):
        webbrowser.open(f'{config.full_url}')
    else:
        raise RuntimeError('Server not ready in time.')
    server_thread.join()

