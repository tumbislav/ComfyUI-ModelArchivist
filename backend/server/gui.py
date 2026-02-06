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

from backend.config import config
from .routers import models, health, admin


app = FastAPI(title='Model Archivist API', version='0.1.0')

app.add_middleware(
    CORSMiddleware,
    allow_origins=[config.url],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*']
)

app.include_router(models.router)
app.include_router(health.router)
app.include_router(admin.router)


class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        response: Response = await super().get_response(path, scope)
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response

app.mount('/', app=StaticFiles(directory=config.html_root, html=True), name='static')


def start_server():
    webbrowser.open(f'{config.url}')
    uvicorn.run(app, host='127.0.0.1', port=config.port, log_level='info')
