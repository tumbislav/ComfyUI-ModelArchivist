# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: backend/server/proxy.py
# purpose: Explicit aiohttp proxy with a replaceable host access boundary
# ---------------------------------------------------------------------------

from collections.abc import Awaitable, Callable

from aiohttp import ClientError, ClientSession, web

from .access import (API_PREFIX, INTERNAL_HEADER, SESSION_HEADER, AccessDenied,
                     check_browser_request)


_HOP_HEADERS = frozenset({
    'connection', 'content-length', 'keep-alive', 'proxy-authenticate',
    'proxy-authorization', 'te', 'trailer', 'transfer-encoding', 'upgrade'
})
_PRIVATE_HEADERS = frozenset({INTERNAL_HEADER.lower(), SESSION_HEADER.lower()})


def forwarded_headers(headers, *, request: bool) -> dict[str, str]:
    excluded = _HOP_HEADERS | _PRIVATE_HEADERS
    excluded |= {item.strip().lower() for item in headers.get('Connection', '').split(',')}
    if request:
        excluded |= {'host', 'authorization', 'cookie', 'comfy-user', 'forwarded'}
    return {name: value for name, value in headers.items()
            if name.lower() not in excluded
            and not name.lower().startswith(('x-forwarded-', 'access-control-'))}


def create_proxy_handler(internal_url: str, secret: str,
                         authorize: Callable[[web.Request], Awaitable[None]]):
    """The host adapter runs on the original request, before credentials are stripped."""
    async def proxy(request: web.Request) -> web.Response:
        try:
            is_api = request.path.startswith(f'{API_PREFIX}/')
            if is_api:
                check_browser_request(request.headers, request.scheme, request.host)
            await authorize(request)
        except AccessDenied as error:
            return web.json_response({'detail': error.detail()}, status=error.status)

        headers = forwarded_headers(request.headers, request=True)
        headers[INTERNAL_HEADER] = secret
        try:
            async with ClientSession(auto_decompress=False) as session:
                async with session.request(
                        request.method, f'{internal_url}{request.rel_url}',
                        headers=headers, data=await request.read(),
                        allow_redirects=False) as upstream:
                    return web.Response(
                        status=upstream.status,
                        headers=forwarded_headers(upstream.headers, request=False),
                        body=await upstream.read())
        except (OSError, ClientError):
            return web.json_response({'detail': {
                'code': 'backend_unavailable', 'message': 'Model Archivist backend is unavailable.',
                'params': {}}}, status=502)

    return proxy
