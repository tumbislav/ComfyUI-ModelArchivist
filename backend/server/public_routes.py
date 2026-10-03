# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: backend/server/public_routes.py
# purpose: Explicit public API surface and exact frontend asset routes
# ---------------------------------------------------------------------------

from pathlib import Path

from fastapi import routing

from .access import API_PREFIX, APP_PREFIX


# New API endpoints must be explicitly reviewed and added here.
PUBLIC_API_ROUTES = (
    ('GET', '/about'),
    ('GET', '/collections'),
    ('POST', '/collections'),
    ('GET', '/config/file_formats'),
    ('GET', '/config/directory-roots'),
    ('GET', '/config/directories'),
    ('PUT', '/config/model-extensions'),
    ('POST', '/config/model-mapping-preview'),
    ('GET', '/config/model-mapping-roots'),
    ('PUT', '/config/model-type'),
    ('GET', '/config/model_types'),
    ('PUT', '/config/models'),
    ('GET', '/config/repository'),
    ('PUT', '/config/repository'),
    ('PUT', '/config/workflows'),
    ('GET', '/health'),
    ('GET', '/models'),
    ('GET', '/models/base-models'),
    ('POST', '/models/bulk/base-model'),
    ('POST', '/models/bulk/move'),
    ('POST', '/models/bulk/synchronize'),
    ('POST', '/models/bulk/tags'),
    ('GET', '/models/relative-paths'),
    ('POST', '/models/relocate'),
    ('POST', '/models/search'),
    ('GET', '/repository-status'),
    ('GET', '/repository-summary'),
    ('POST', '/scan'),
    ('GET', '/server-status'),
    ('GET', '/tags'),
    ('POST', '/tags/remap'),
    ('GET', '/tags/rules'),
    ('GET', '/tags/usage'),
    ('POST', '/user-objects/relocate'),
    ('GET', '/user-types'),
    ('POST', '/user-types'),
    ('GET', '/workflows'),
    ('POST', '/workflows/bulk/move'),
    ('POST', '/workflows/bulk/synchronize'),
    ('POST', '/workflows/bulk/tags'),
    ('GET', '/workflows/relative-paths'),
    ('POST', '/workflows/relocate'),
    ('POST', '/workflows/search'),
    ('DELETE', '/collections/{id}'),
    ('GET', '/collections/{id}'),
    ('PUT', '/collections/{id}'),
    ('GET', '/collections/{id}/members'),
    ('POST', '/collections/{id}/models'),
    ('POST', '/collections/{id}/move'),
    ('POST', '/collections/{id}/synchronize'),
    ('POST', '/collections/{id}/user-objects'),
    ('POST', '/collections/{id}/workflows'),
    ('GET', '/models/{id}'),
    ('PUT', '/models/{id}'),
    ('POST', '/models/{id}/move'),
    ('POST', '/models/{id}/synchronize'),
    ('GET', '/operations/{id}'),
    ('GET', '/scan/{timestamp}'),
    ('GET', '/user-objects/{id}'),
    ('PUT', '/user-objects/{id}'),
    ('POST', '/user-objects/{id}/move'),
    ('POST', '/user-objects/{id}/synchronize'),
    ('DELETE', '/user-types/{id}'),
    ('GET', '/user-types/{id}'),
    ('PUT', '/user-types/{id}'),
    ('POST', '/user-types/{id}/deletion-preview'),
    ('GET', '/user-types/{id}/objects'),
    ('POST', '/user-types/{id}/objects/search'),
    ('GET', '/user-types/{id}/relative-paths'),
    ('GET', '/workflows/{id}'),
    ('PUT', '/workflows/{id}'),
    ('POST', '/workflows/{id}/move'),
    ('POST', '/workflows/{id}/synchronize'),
)


def api_routes() -> tuple[tuple[str, str], ...]:
    return tuple((method, API_PREFIX + path) for method, path in PUBLIC_API_ROUTES)


def registered_http_routes(routes) -> set[tuple[str, str]]:
    """Inspect effective paths, including prefixes from lazy router inclusion."""
    iterator = getattr(routing, 'iter_route_contexts', None)
    if iterator is not None:
        resolved = iterator(routes)
    else:
        # Older FastAPI releases expose flat routes. Releases 0.137.0/0.137.1
        # have lazy inclusion but predate the public context iterator.
        resolved = (
            item
            for route in routes
            for item in (route.effective_route_contexts()
                         if hasattr(route, 'effective_route_contexts') else (route,))
        )
    result = set()
    for route in resolved:
        path = getattr(route, 'path', None)
        methods = getattr(route, 'methods', None)
        if not isinstance(path, str) or not methods:
            raise RuntimeError('Public route validation requires explicit HTTP routes')
        result.update((method, path) for method in methods)
    return result


def static_routes(directory: Path) -> dict[str, str]:
    """Snapshot trusted build files; never accept a browser-supplied file path."""
    root = directory.resolve()
    routes = {}
    for file in sorted(root.rglob('*')):
        relative = file.relative_to(root)
        if (not file.is_file() or not file.resolve().is_relative_to(root)
                or any(part.startswith('.') for part in relative.parts)
                or file.name == 'build-manifest.json' or file.suffix == '.map'):
            continue
        name = relative.as_posix()
        if relative.parts[0] == 'api' or any(char in name for char in '{}%\\'):
            raise ValueError('Frontend asset conflicts with public routing')
        routes[f'{APP_PREFIX}/{name}'] = name
    if f'{APP_PREFIX}/index.html' not in routes:
        raise RuntimeError('Frontend build is missing index.html')
    routes[f'{APP_PREFIX}/'] = 'index.html'
    routes[APP_PREFIX] = 'index.html'
    return routes
