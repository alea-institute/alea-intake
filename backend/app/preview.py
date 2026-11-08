"""Shared pre-launch access gate for HTTP and WebSocket traffic."""
import hashlib
import hmac

from starlette.requests import HTTPConnection, Request
from starlette.responses import PlainTextResponse, RedirectResponse

from app import config


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
        signature = hmac.new(settings.secret_key.encode(), passphrase.encode(), hashlib.sha256).hexdigest()
        matches = lambda value, expected: hmac.compare_digest(value.encode(), expected.encode())
        if scope['type'] == 'http' and scope['method'] == 'GET' and scope['path'] == '/__preview':
            request = Request(scope)
            if matches(request.query_params.get('key', ''), passphrase):
                response = RedirectResponse('/', status_code=303)
                response.set_cookie('alea_preview', signature, httponly=True,
                                    secure=request.url.scheme == 'https', samesite='lax')
                response.headers['Cache-Control'] = 'no-store'
                response.headers['Referrer-Policy'] = 'no-referrer'
                return await response(scope, receive, send)
        elif (matches(connection.headers.get('x-preview-key', ''), passphrase)
              or matches(connection.cookies.get('alea_preview', ''), signature)):
            return await self.app(scope, receive, send)
        if scope['type'] == 'websocket':
            return await send({'type': 'websocket.close', 'code': 1008})
        await PlainTextResponse('Preview access required.', status_code=401,
                                headers={'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer'})(scope, receive, send)
