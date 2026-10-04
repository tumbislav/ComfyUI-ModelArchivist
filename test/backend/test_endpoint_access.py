# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: test/backend/test_endpoint_access.py
# purpose: HTTP access, session lifecycle, explicit routes, and proxy regressions
# ---------------------------------------------------------------------------

import asyncio
import importlib
import json
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
import pytest

import backend.config
from backend.server.access import (
    API_PREFIX, APP_PREFIX, INTERNAL_HEADER, REQUEST_HEADER, SESSION_HEADER,
    AccessDenied, AccessPolicy,
)
from backend.server.proxy import create_proxy_handler
from backend.server.public_routes import api_routes, registered_http_routes, static_routes


@pytest.fixture
def server_factory(tmp_path, monkeypatch):
    (tmp_path / 'index.html').write_text('<html>Archivist</html>')
    (tmp_path / 'asset.js').write_text('console.log("asset")')
    (tmp_path / 'build-manifest.json').write_text('{}')
    config = SimpleNamespace(mode='standalone', host='127.0.0.1', http_port=0,
                             static_html=tmp_path, uvicorn_log_config=None)
    monkeypatch.setattr(backend.config, '_config', config)
    previous = sys.modules.pop('backend.server.gui', None)
    gui = importlib.import_module('backend.server.gui')
    servers = []
    threads = []
    create_server = gui.create_server

    def record_server(listener, port):
        server = create_server(listener, port)
        servers.append(server)
        return server

    monkeypatch.setattr(gui, 'create_server', record_server)

    def start(mode='standalone', host='127.0.0.1', open_browser=False):
        config.mode = mode
        config.host = host
        thread, port = gui.start_ui(open_browser=open_browser, block=False, port=0)
        threads.append(thread)
        return f'http://127.0.0.1:{port}', gui.access_policy, gui

    yield start
    for server in servers:
        server.should_exit = True
    for thread in threads:
        thread.join(timeout=5)
        assert not thread.is_alive()
    sys.modules.pop('backend.server.gui', None)
    if previous is not None:
        sys.modules['backend.server.gui'] = previous


def request(origin, path, headers=None, method='GET'):
    try:
        response = urlopen(Request(origin + path, headers=headers or {}, method=method), timeout=3)
    except HTTPError as error:
        response = error
    with response:
        return response.status, response.headers, response.read()


@pytest.mark.parametrize('legacy_iterator', [False, True])
def test_route_inventory_preserves_nested_prefixes_and_hidden_routes(monkeypatch, legacy_iterator):
    from fastapi import APIRouter, FastAPI, routing

    if legacy_iterator:
        monkeypatch.setattr(routing, 'iter_route_contexts', None, raising=False)
    leaf = APIRouter()

    @leaf.get('/{id}', include_in_schema=False)
    def hidden(id: str):
        return {'id': id}

    parent = APIRouter()
    parent.include_router(leaf, prefix='/models')
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.include_router(parent, prefix=API_PREFIX)
    app.include_router(parent, prefix='/second')
    assert registered_http_routes(app.routes) == {
        ('GET', API_PREFIX + '/models/{id}'), ('GET', '/second/models/{id}')}


def test_legacy_flat_inventory_and_unsupported_routes_fail_closed(monkeypatch):
    from fastapi import APIRouter, routing

    monkeypatch.setattr(routing, 'iter_route_contexts', None, raising=False)
    router = APIRouter()
    router.add_api_route('/health', lambda: {}, methods=['GET', 'POST'])
    assert registered_http_routes(router.routes) == {('GET', '/health'), ('POST', '/health')}
    with pytest.raises(RuntimeError, match='explicit HTTP routes'):
        registered_http_routes([SimpleNamespace(path='/unreviewed-mount')])


def test_standalone_launch_and_session_enforcement(server_factory, monkeypatch):
    launched = []
    monkeypatch.setattr('webbrowser.open', launched.append)
    origin, policy, gui = server_factory(open_browser=True)
    assert launched == [policy.launch_url(origin)]
    assert policy.secret not in repr(policy)
    good = {REQUEST_HEADER: '1', SESSION_HEADER: policy.secret}
    assert request(origin, API_PREFIX + '/health', good)[0] == 200
    for headers in ({}, {REQUEST_HEADER: '1'}, {REQUEST_HEADER: '1', SESSION_HEADER: 'wrong'},
                    {REQUEST_HEADER: '1', INTERNAL_HEADER: policy.secret}):
        status, _, body = request(origin, API_PREFIX + '/health', headers)
        assert status in (401, 403)
        assert json.loads(body)['detail']['code']
        assert policy.secret.encode() not in body
    status, _, body = request(origin, APP_PREFIX + '/')
    assert status == 200
    assert policy.secret.encode() not in body
    gui.access_policy = AccessPolicy('standalone')
    assert request(origin, API_PREFIX + '/health', good)[0] == 401


@pytest.mark.parametrize('extra', [
    {'Origin': 'https://attacker.example'}, {'Origin': 'null'},
    {'Sec-Fetch-Site': 'cross-site'}, {'Sec-Fetch-Site': 'same-site'},
])
def test_standalone_rejects_cross_origin_even_with_session(server_factory, extra):
    origin, policy, _ = server_factory()
    headers = {REQUEST_HEADER: '1', SESSION_HEADER: policy.secret, **extra}
    assert request(origin, API_PREFIX + '/health', headers)[0] == 403
    headers = {REQUEST_HEADER: '1', SESSION_HEADER: policy.secret, 'Origin': origin}
    assert request(origin, API_PREFIX + '/health', headers)[0] == 200


def test_only_explicit_routes_and_methods_are_served(server_factory):
    origin, policy, _ = server_factory()
    headers = {REQUEST_HEADER: '1', SESSION_HEADER: policy.secret}
    for path in ('/docs', '/openapi.json', APP_PREFIX + '/build-manifest.json',
                 APP_PREFIX + '/unknown', API_PREFIX + '/unknown'):
        assert request(origin, path, headers)[0] == 404
    assert request(origin, APP_PREFIX + '/asset.js', method='POST')[0] == 405
    assert request(origin, API_PREFIX + '/health', headers, 'DELETE')[0] == 405
    assert request(origin, API_PREFIX + '/health?ordinary=query', headers)[0] == 200
    status, response_headers, body = request(origin, APP_PREFIX + '/asset.js', method='HEAD')
    assert status == 200 and body == b''
    assert 'Access-Control-Allow-Origin' not in response_headers


def test_filesystem_denial_is_structured_and_native_picker_is_absent(server_factory, tmp_path):
    origin, policy, _ = server_factory()
    headers = {REQUEST_HEADER: '1', SESSION_HEADER: policy.secret, 'Content-Type': 'application/json'}
    data = json.dumps({'working_root': str(tmp_path.parent), 'archive_root': str(tmp_path),
                       'extensions': ['bin']}).encode()
    with pytest.raises(HTTPError) as error:
        urlopen(Request(origin + API_PREFIX + '/config/model-mapping-preview', data=data,
                        headers=headers), timeout=3)
    with error.value as response:
        assert response.code == 403
        detail = json.loads(response.read())['detail']
        assert detail['code'] == 'filesystem_outside_roots'
        assert detail['params']['path'] == str(tmp_path.parent)
    assert request(origin, API_PREFIX + '/config/pick-directory', headers, 'POST')[0] == 404


def test_directory_browser_routes_require_session_and_valid_role(server_factory, tmp_path):
    from urllib.parse import urlencode
    origin, policy, _ = server_factory()
    headers = {REQUEST_HEADER: '1', SESSION_HEADER: policy.secret}
    (tmp_path / 'folder').mkdir()
    endpoint = API_PREFIX + '/config/directories?'
    query = urlencode({'path': str(tmp_path), 'role': 'working'})
    assert request(origin, endpoint + query)[0] in (401, 403)
    status, _, body = request(origin, endpoint + query, headers)
    assert status == 200
    assert [item['name'] for item in json.loads(body)['directories']] == ['folder']
    assert request(origin, endpoint + urlencode({'path': str(tmp_path), 'role': 'all'}), headers)[0] == 422
    assert request(origin, API_PREFIX + '/config/directory-roots', headers)[0] == 422
    assert request(origin, API_PREFIX + '/config/directory-roots?role=archive', headers)[0] == 200


def test_embedded_server_uses_loopback_and_separate_internal_token(server_factory):
    origin, policy, gui = server_factory('comfyui', host='192.0.2.1')
    # A successful bind with an unassigned configured address proves embedded mode overrides it.
    for path in (APP_PREFIX + '/', API_PREFIX + '/health'):
        assert request(origin, path)[0] == 401
        assert request(origin, path, {SESSION_HEADER: policy.secret, REQUEST_HEADER: '1'})[0] == 401
        assert request(origin, path, {INTERNAL_HEADER: policy.secret})[0] == 200
    with pytest.raises(ValueError):
        policy.launch_url(origin)
    gui.access_policy = None
    assert request(origin, API_PREFIX + '/health', {INTERNAL_HEADER: policy.secret})[0] == 503


def test_asset_inventory_excludes_private_files_and_rejects_api_collision(tmp_path):
    (tmp_path / 'index.html').write_text('app')
    for name in ('.env', 'build-manifest.json', 'source.js.map'):
        (tmp_path / name).write_text('private')
    assert set(static_routes(tmp_path)) == {APP_PREFIX, APP_PREFIX + '/', APP_PREFIX + '/index.html'}
    (tmp_path / 'api').mkdir()
    (tmp_path / 'api' / 'health').write_text('collision')
    with pytest.raises(ValueError):
        static_routes(tmp_path)


def test_proxy_access_boundary_header_isolation_and_explicit_routes():
    async def scenario():
        received = []

        async def upstream(request):
            received.append(dict(request.headers))
            return web.json_response({'ok': True}, headers={INTERNAL_HEADER: 'server-only'})

        backend = web.Application()
        backend.router.add_get(API_PREFIX + '/health', upstream)
        async with TestServer(backend) as internal:
            async def authorize(request):
                if request.headers.get('Comfy-User') == 'denied':
                    raise AccessDenied('host_user_denied', 'Host rejected this user.')

            proxy = create_proxy_handler(str(internal.make_url('')).rstrip('/'), 'server-only', authorize)
            public = web.Application()
            for method, path in api_routes():
                public.router.add_route(method, path, proxy)
            async with TestClient(TestServer(public)) as client:
                for headers, status in (({}, 403),
                                        ({REQUEST_HEADER: '1', 'Comfy-User': 'denied'}, 403),
                                        ({REQUEST_HEADER: '1', 'Origin': 'https://evil.example'}, 403)):
                    response = await client.get(API_PREFIX + '/health', headers=headers)
                    assert response.status == status
                assert received == []
                response = await client.get(API_PREFIX + '/health?scope=models', headers={
                    REQUEST_HEADER: '1', INTERNAL_HEADER: 'forged', SESSION_HEADER: 'browser-secret',
                    'Comfy-User': 'default', 'Authorization': 'Bearer host-secret',
                    'Cookie': 'host=session', 'X-Forwarded-For': '127.0.0.1',
                    'Connection': 'X-Remove', 'X-Remove': 'discard',
                })
                assert response.status == 200
                assert INTERNAL_HEADER not in response.headers
                assert 'server-only' not in await response.text()
                headers = {key.lower(): value for key, value in received[-1].items()}
                assert headers[INTERNAL_HEADER.lower()] == 'server-only'
                for name in ('authorization', 'cookie', 'comfy-user', 'x-forwarded-for',
                             'x-remove', SESSION_HEADER.lower()):
                    assert name not in headers
                assert (await client.get(API_PREFIX + '/not-exposed')).status == 404
                assert (await client.delete(API_PREFIX + '/health')).status == 405
                assert len(received) == 1

    asyncio.run(scenario())


def test_comfy_entrypoint_preserves_host_checks_and_registers_only_reviewed_routes(tmp_path, monkeypatch):
    import backend.repository.repository as repository

    (tmp_path / 'index.html').write_text('app')
    config = SimpleNamespace(mode='comfyui', host='0.0.0.0', static_html=tmp_path)
    monkeypatch.setattr(backend.config, 'load_config', lambda **kwargs: config)
    monkeypatch.setattr(backend.config, 'initialize_logging', lambda config: None)
    monkeypatch.setattr(repository, 'start_repo', lambda: None)
    monkeypatch.setattr('backend.environment.set_environment_provider', lambda provider: None)
    starts = []

    def start_ui(**kwargs):
        starts.append(kwargs)
        return None, 12345

    monkeypatch.setitem(sys.modules, 'backend.server.gui', SimpleNamespace(start_ui=start_ui))
    monkeypatch.setitem(sys.modules, 'folder_paths', SimpleNamespace(folder_names_and_paths={}))

    class UserManager:
        def get_request_user_id(self, request):
            user = request.headers.get('Comfy-User', 'default')
            if user not in ('default', 'named-profile'):
                raise KeyError(user)
            return user

    host = SimpleNamespace(routes=web.RouteTableDef(), user_manager=UserManager())
    monkeypatch.setitem(sys.modules, 'server', SimpleNamespace(PromptServer=SimpleNamespace(instance=host)))
    entry = runpy.run_path(str(Path(__file__).resolve().parents[2] / '__init__.py'))
    assert len(starts) == 1
    assert starts[0]['policy'].mode == 'comfyui'
    assert starts[0]['open_browser'] is False
    expected = set(api_routes()) | {('GET', path) for path in static_routes(tmp_path)}
    assert {(route.method, route.path) for route in host.routes} == expected
    assert all('*' not in route.path and route.method != '*' for route in host.routes)

    async def scenario():
        from aiohttp.test_utils import make_mocked_request

        authorize = entry['authorize_comfy_request']
        for user in ('default', 'named-profile'):
            await authorize(make_mocked_request('GET', API_PREFIX + '/health',
                                               headers={'Comfy-User': user}))
        with pytest.raises(AccessDenied):
            await authorize(make_mocked_request('GET', API_PREFIX + '/health',
                                               headers={'Comfy-User': 'unknown'}))
        host.user_manager = None
        with pytest.raises(AccessDenied) as failure:
            await authorize(make_mocked_request('GET', API_PREFIX + '/health'))
        assert failure.value.status == 503

        app = web.Application()
        # Reproduce PromptServer.add_routes(), including its placement of kwargs.
        aliases = web.RouteTableDef()
        for route in host.routes:
            aliases.route(route.method, '/api' + route.path)(route.handler, **route.kwargs)
        app.add_routes(aliases)
        app.add_routes(host.routes)
        async with TestClient(TestServer(app)) as client:
            assert (await client.head(API_PREFIX + '/health')).status == 405
            assert (await client.get(APP_PREFIX + '/unlisted')).status == 404
            assert (await client.post(APP_PREFIX + '/index.html')).status == 405
            for path in (API_PREFIX + '/health', APP_PREFIX + '/index.html'):
                assert (await client.get('/api' + path)).status == 404

    asyncio.run(scenario())
