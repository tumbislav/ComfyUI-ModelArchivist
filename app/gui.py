# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: gui.py
# purpose: REST interface to web GUI
# ---------------------------------------------------------------------------

from app.model.archivist import archivist

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import Any
import webbrowser


def open_gui() -> None:
    webbrowser.open_new_tab("http://127.0.0.1:5173")


app = FastAPI(title='Model Archivist API', version='0.1.0')

app.add_middleware(
    CORSMiddleware,
    allow_origins=['http://127.0.0.1:5173', 'http://localhost:5173'],
    allow_credentials=True,
    allow_methods=['GET', 'POST', 'PATCH', 'PUT', 'DELETE'],
    allow_headers=['*'],
)


@app.get('/models')
def get_models() -> list[dict[str, Any]]:
    models = archivist.get_models()
    return list(models)


@app.get('/health')
def health() -> dict[str, str]:
    return {'status': 'ok'}
