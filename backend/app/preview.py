"""Shared pre-launch access gate for HTTP and WebSocket traffic.

A request passes the gate with the preview passphrase (``X-Preview-Key``
header or the signed ``alea_preview`` cookie) or, when Cloudflare Access is
configured, with a valid ``Cf-Access-Jwt-Assertion`` token.
"""
import asyncio
import hashlib
import hmac
import logging
import threading
import time
from functools import lru_cache

import jwt
from jwt import PyJWKClient
from starlette.requests import HTTPConnection, Request
from starlette.responses import PlainTextResponse, RedirectResponse

from app import config

logger = logging.getLogger(__name__)

ACCESS_HEADER = 'cf-access-jwt-assertion'
JWKS_TTL_SECONDS = 3600
JWKS_FETCH_TIMEOUT_SECONDS = 5
# Unknown key ids force at most one JWKS refetch per interval, so junk tokens
# cannot turn every request into an outbound fetch.
JWKS_FORCED_REFRESH_INTERVAL_SECONDS = 60
JWT_LEEWAY_SECONDS = 30


def _matches(value, expected):
    return hmac.compare_digest(value.encode(), expected.encode())


@lru_cache(maxsize=8)
def _signature(secret_key, passphrase):
    return hmac.new(secret_key.encode(), passphrase.encode(), hashlib.sha256).hexdigest()


class _AccessKeys:
    """Cached Cloudflare Access signing keys for one team domain."""

    def __init__(self, team_domain):
        self._client = PyJWKClient(f'https://{team_domain}/cdn-cgi/access/certs',
                                   cache_jwk_set=True, lifespan=JWKS_TTL_SECONDS,
                                   timeout=JWKS_FETCH_TIMEOUT_SECONDS)
        self._lock = threading.Lock()
        self._last_forced = float('-inf')

    def key_for(self, kid):
        with self._lock:
            key = self._find(kid, refresh=False)
            if key is None and time.monotonic() - self._last_forced >= JWKS_FORCED_REFRESH_INTERVAL_SECONDS:
                self._last_forced = time.monotonic()
                key = self._find(kid, refresh=True)
            return key

    def _find(self, kid, refresh):
        for signing_key in self._client.get_signing_keys(refresh=refresh):
            if signing_key.key_id == kid:
                return signing_key.key
        return None


@lru_cache(maxsize=4)
def _access_keys(team_domain):
    return _AccessKeys(team_domain)


def _email_domain(claims):
    email = claims.get('email')
    return email.rsplit('@', 1)[-1] if isinstance(email, str) and '@' in email else '-'


def _verify_access_token(token, team_domain, audience, allowed_emails):
    """Return True when ``token`` is a valid Access JWT for this application."""
    try:
        header = jwt.get_unverified_header(token)
        kid = header.get('kid')
        if header.get('alg') != 'RS256' or not isinstance(kid, str):
            return False
        key = _access_keys(team_domain).key_for(kid)
        if key is None:
            return False
        claims = jwt.decode(token, key, algorithms=['RS256'], audience=audience,
                            issuer=f'https://{team_domain}', leeway=JWT_LEEWAY_SECONDS,
                            options={'require': ['exp', 'iat', 'aud', 'iss']})
    except jwt.PyJWKClientError as exc:
        logger.warning('Cloudflare Access key fetch failed (%s)', type(exc).__name__)
        return False
    except jwt.PyJWTError as exc:
        logger.debug('Cloudflare Access token refused (%s)', type(exc).__name__)
        return False
    except Exception as exc:  # never let verification turn into a 500
        logger.warning('Cloudflare Access verification error (%s)', type(exc).__name__)
        return False
    if allowed_emails:
        email = claims.get('email')
        if not isinstance(email, str) or email.strip().lower() not in allowed_emails:
            logger.info('Cloudflare Access identity not allowlisted (domain %s)', _email_domain(claims))
            return False
    return True


def _allowed_emails(raw):
    return frozenset(part.strip().lower() for part in raw.split(',') if part.strip())


async def _access_allowed(connection, settings):
    team_domain = settings.cf_access_team_domain.strip()
    audience = settings.cf_access_aud.strip()
    token = connection.headers.get(ACCESS_HEADER, '')
    if not (team_domain and audience and token):
        return False
    return await asyncio.to_thread(_verify_access_token, token, team_domain, audience,
                                   _allowed_emails(settings.cf_access_emails))


class PreviewGate:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        settings = config.get_settings()
        passphrase = settings.preview_passphrase
        if scope['type'] not in ('http', 'websocket') or not passphrase:
            return await self.app(scope, receive, send)
        if scope['type'] == 'http' and scope['method'] == 'GET' and scope['path'] == '/health':
            return await self.app(scope, receive, send)
        connection = HTTPConnection(scope)
        signature = _signature(settings.secret_key, passphrase)
        if scope['type'] == 'http' and scope['method'] == 'GET' and scope['path'] == '/__preview':
            request = Request(scope)
            if _matches(request.query_params.get('key', ''), passphrase):
                response = RedirectResponse('/', status_code=303)
                days = settings.preview_cookie_days
                response.set_cookie('alea_preview', signature, max_age=days * 86400 if days > 0 else None,
                                    httponly=True, secure=request.url.scheme == 'https', samesite='lax')
                response.headers['Cache-Control'] = 'no-store'
                response.headers['Referrer-Policy'] = 'no-referrer'
                return await response(scope, receive, send)
        elif (_matches(connection.headers.get('x-preview-key', ''), passphrase)
              or _matches(connection.cookies.get('alea_preview', ''), signature)
              or await _access_allowed(connection, settings)):
            return await self.app(scope, receive, send)
        if scope['type'] == 'websocket':
            return await send({'type': 'websocket.close', 'code': 1008})
        await PlainTextResponse('Preview access required.', status_code=401,
                                headers={'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer'})(scope, receive, send)
