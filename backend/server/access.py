# ---------------------------------------------------------------------------
# system: ModelArchivist
# file: backend/server/access.py
# purpose: Transport-independent access policies and browser request checks
# ---------------------------------------------------------------------------

from dataclasses import dataclass, field
import secrets
from typing import Mapping
from urllib.parse import urlsplit


APP_PREFIX = '/model-archivist'
API_PREFIX = f'{APP_PREFIX}/api'
INTERNAL_HEADER = 'X-Archivist-Internal'
SESSION_HEADER = 'X-Archivist-Session'
REQUEST_HEADER = 'X-Archivist-Request'


@dataclass
class AccessDenied(Exception):
    code: str
    message: str
    status: int = 403

    def detail(self) -> dict:
        return {'code': self.code, 'message': self.message, 'params': {}}


def check_browser_request(headers: Mapping[str, str], scheme: str, host: str) -> None:
    """Require same-origin API usage, including under permissive host CORS settings.

    These checks prevent cross-site browser calls; they are not authentication.
    The caller must supply case-insensitive headers.
    """
    if headers.get(REQUEST_HEADER) != '1':
        raise AccessDenied('request_header_required', 'An Archivist API request header is required.')
    if headers.get('Sec-Fetch-Site', 'none') not in ('same-origin', 'none'):
        raise AccessDenied('cross_origin_denied', 'Cross-origin API requests are not permitted.')
    origin = headers.get('Origin')
    if origin is not None:
        try:
            supplied = urlsplit(origin)
            expected = urlsplit(f'{scheme}://{host}')
            def authority(value):
                return (value.scheme, value.hostname,
                        value.port or (443 if value.scheme == 'https' else 80))
            valid = (supplied.scheme in ('http', 'https') and not supplied.username
                     and not supplied.password and supplied.path in ('', '/')
                     and not supplied.query and not supplied.fragment
                     and authority(supplied) == authority(expected))
        except ValueError:
            valid = False
        if not valid:
            raise AccessDenied('cross_origin_denied', 'Cross-origin API requests are not permitted.')


@dataclass
class AccessPolicy:
    """One process-lifetime credential, with an explicit transport role."""
    mode: str
    secret: str = field(default_factory=lambda: secrets.token_urlsafe(32), repr=False)

    def __post_init__(self):
        if self.mode not in ('standalone', 'comfyui'):
            raise ValueError('Unsupported access policy mode')

    def authorize(self, headers: Mapping[str, str], *, api: bool,
                  scheme: str, host: str) -> None:
        if self.mode == 'comfyui':
            supplied = headers.get(INTERNAL_HEADER, '')
        elif api:
            check_browser_request(headers, scheme, host)
            supplied = headers.get(SESSION_HEADER, '')
        else:
            return
        if not secrets.compare_digest(supplied.encode('utf-8'), self.secret.encode('utf-8')):
            raise AccessDenied('access_session_required',
                               'Access is missing or expired. Reopen Archivist from its launcher.', 401)

    def launch_url(self, origin: str) -> str:
        if self.mode != 'standalone':
            raise ValueError('Internal credentials must never be included in a browser URL')
        return f'{origin}{APP_PREFIX}/#archivist-session={self.secret}'
