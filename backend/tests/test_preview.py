"""Preview access covers HTTP, static pages and WebSocket upgrades."""
import hashlib
import hmac

import pytest
from fastapi import FastAPI, WebSocket
from httpx import AsyncClient, ASGITransport


@pytest.fixture
async def preview(monkeypatch):
    from app import config
    from app.preview import PreviewGate
    settings = config.Settings(_env_file=None, preview_passphrase='preview-example',
                               secret_key='signing-example')
    monkeypatch.setattr(config, 'get_settings', lambda: settings)
    app = FastAPI()
    @app.get('/health')
    @app.get('/')
    @app.post('/api/example')
    async def page():
        return {'content': 'private app content'}
    @app.websocket('/ws')
    async def socket(ws: WebSocket):
        await ws.accept()
        await ws.send_text('private app content')
        await ws.close()
    app.add_middleware(PreviewGate)
    async with AsyncClient(transport=ASGITransport(app), base_url='https://test') as client:
        yield client, settings, app


async def test_preview_refuses_pages_api_and_websocket(preview):
    client, _, app = preview
    for method, path in [('GET', '/'), ('POST', '/api/example'), ('GET', '/assets/app.js'), ('POST', '/health')]:
        response = await client.request(method, path)
        assert response.status_code == 401
        assert 'private app content' not in response.text
        assert response.headers['content-type'].startswith('text/plain')
    assert (await client.get('/health')).status_code == 200
    assert await socket_messages(app) == [{'type': 'websocket.close', 'code': 1008}]


async def test_preview_header_and_wrong_key(preview):
    client, _, app = preview
    assert (await client.get('/', headers={'X-Preview-Key': 'preview-example'})).status_code == 200
    assert (await client.get('/', headers={'X-Preview-Key': 'wrong'})).status_code == 401
    assert (await client.get('/__preview?key=wrong')).status_code == 401
    assert (await client.get('/', headers={'Cookie': 'alea_preview=forged'})).status_code == 401
    assert (await socket_messages(app, [(b'x-preview-key', b'preview-example')]))[1]['text'] == 'private app content'


@pytest.mark.parametrize('scheme,secure', [('https', True), ('http', False)])
async def test_preview_cookie_flow(preview, scheme, secure):
    client, settings, app = preview
    response = await client.get(f'{scheme}://test/__preview?key=preview-example', follow_redirects=False)
    assert response.status_code == 303
    assert response.headers['location'] == '/'
    cookie = response.headers['set-cookie']
    assert 'HttpOnly' in cookie and 'SameSite=lax' in cookie
    assert ('; Secure' in cookie) == secure
    assert 'preview-example' not in cookie
    assert client.cookies['alea_preview'] == hmac.new(b'signing-example', b'preview-example', hashlib.sha256).hexdigest()
    assert (await client.get(f'{scheme}://test/')).status_code == 200
    assert (await socket_messages(app, [(b'cookie', ('alea_preview=' + client.cookies['alea_preview']).encode())]))[1]['text'] == 'private app content'
    settings.preview_passphrase = 'rotated'
    assert (await client.get('/')).status_code == 401


async def test_preview_off_is_public(preview):
    client, settings, app = preview
    settings.preview_passphrase = ''
    assert (await client.get('/')).status_code == 200
    assert (await client.post('/api/example')).status_code == 200
    assert (await socket_messages(app))[1]['text'] == 'private app content'


async def socket_messages(app, headers=()):
    sent = []
    async def receive():
        return {'type': 'websocket.connect'}
    async def send(message):
        sent.append(message)
    await app({'type': 'websocket', 'path': '/ws', 'scheme': 'wss',
               'query_string': b'', 'headers': list(headers)}, receive, send)
    return sent
