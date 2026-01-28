# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: gui.py
# purpose: REST interface to frontend GUI
# ---------------------------------------------------------------------------


from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
import webbrowser

from ..config.config import config
from ..model.archivist import archivist


app = FastAPI(title='Model Archivist API', version='0.1.0')

app.add_middleware(
    CORSMiddleware,
    allow_origins=[config.url],
    allow_credentials=True,
    allow_methods=['GET', 'POST', 'PATCH', 'PUT', 'DELETE'],
    allow_headers=['*'],
)


@app.get('/models')
def get_models() -> list[dict]:
    models = archivist.get_models()
    return models


app.mount('/', app= StaticFiles(directory=config.html_root, html=True), name='static')


def start_server():
    webbrowser.open(f'{config.url}')
    uvicorn.run(app, port=config.port, log_level='info')
