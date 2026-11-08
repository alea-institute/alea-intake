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


async def test_preview_cookie_has_max_age(preview):
    client, settings, _ = preview
    cookie = (await client.get('/__preview?key=preview-example', follow_redirects=False)).headers['set-cookie']
    assert f'Max-Age={30 * 86400}' in cookie
    settings.preview_cookie_days = 0
    cookie = (await client.get('/__preview?key=preview-example', follow_redirects=False)).headers['set-cookie']
    assert 'Max-Age' not in cookie and 'HttpOnly' in cookie


# --- Cloudflare Access JWT path (no network: the JWKS client is stubbed) ---

TEAM = 'example-team.cloudflareaccess.com'
AUD = 'aud-tag-example'


@pytest.fixture(scope='module')
def rsa_keys():
    from cryptography.hazmat.primitives.asymmetric import rsa
    return (rsa.generate_private_key(public_exponent=65537, key_size=2048),
            rsa.generate_private_key(public_exponent=65537, key_size=2048))


@pytest.fixture
def access(preview, rsa_keys, monkeypatch):
    import json
    import jwt
    from app import preview as preview_module
    signing, _ = rsa_keys
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(signing.public_key()))
    jwk.update(kid='kid-1', use='sig', alg='RS256')
    calls = []

    class FakeJWKClient:
        def __init__(self, uri, **kwargs):
            calls.append(('init', uri))

        def get_signing_keys(self, refresh=False):
            calls.append(('fetch', refresh))
            if state['fail']:
                raise jwt.PyJWKClientConnectionError('offline')
            return [jwt.PyJWK.from_dict(jwk)]

    state = {'fail': False, 'calls': calls}
    monkeypatch.setattr(preview_module, 'PyJWKClient', FakeJWKClient)
    preview_module._access_keys.cache_clear()
    client, settings, app = preview
    settings.cf_access_team_domain = TEAM
    settings.cf_access_aud = AUD
    yield client, settings, app, state
    preview_module._access_keys.cache_clear()


def access_token(key, **overrides):
    import time
    import jwt
    now = int(time.time())
    claims = {'aud': [AUD], 'iss': f'https://{TEAM}', 'iat': now, 'exp': now + 600,
              'email': 'owner@example.com', 'sub': 'subject-example'}
    headers = {'kid': overrides.pop('kid', 'kid-1')}
    alg = overrides.pop('alg', 'RS256')
    claims.update(overrides)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, key, algorithm=alg, headers=headers)


def access_headers(token):
    return {'Cf-Access-Jwt-Assertion': token}


async def test_access_token_passes_http_and_websocket(access, rsa_keys):
    client, _, app, state = access
    token = access_token(rsa_keys[0])
    response = await client.get('/', headers=access_headers(token))
    assert response.status_code == 200
    assert (await client.post('/api/example', headers=access_headers(token))).status_code == 200
    messages = await socket_messages(app, [(b'cf-access-jwt-assertion', token.encode())])
    assert messages[1]['text'] == 'private app content'
    assert ('init', f'https://{TEAM}/cdn-cgi/access/certs') in state['calls']
    assert response.headers.get('set-cookie') is None


@pytest.mark.parametrize('overrides', [
    {'aud': ['other-aud']},
    {'aud': None},
    {'iss': 'https://other-team.cloudflareaccess.com'},
    {'iss': None},
    {'exp': 1_000_000, 'iat': 999_000},
    {'exp': None},
    {'iat': None},
])
async def test_access_token_bad_claims_refused(access, rsa_keys, overrides):
    client, _, app, _ = access
    token = access_token(rsa_keys[0], **overrides)
    response = await client.get('/', headers=access_headers(token))
    assert response.status_code == 401
    assert 'private app content' not in response.text
    assert await socket_messages(app, [(b'cf-access-jwt-assertion', token.encode())]) == [
        {'type': 'websocket.close', 'code': 1008}]


async def test_access_token_bad_signature_and_algorithms_refused(access, rsa_keys):
    import base64
    import json
    client, _, app, _ = access
    forged = access_token(rsa_keys[1])  # right kid, wrong private key
    tampered_header, payload, signature = access_token(rsa_keys[0]).split('.')
    claims = json.loads(base64.urlsafe_b64decode(payload + '=='))
    claims['email'] = 'intruder@example.com'
    tampered = '.'.join([tampered_header, base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip('='), signature])
    hs256 = access_token('a-shared-secret-of-adequate-length-0123', alg='HS256')
    unsigned = access_token(None, alg='none')
    for token in (forged, tampered, hs256, unsigned, 'not-a-jwt', access_token(rsa_keys[0], kid='unknown')):
        assert (await client.get('/', headers=access_headers(token))).status_code == 401
        assert await socket_messages(app, [(b'cf-access-jwt-assertion', token.encode())]) == [
            {'type': 'websocket.close', 'code': 1008}]


async def test_access_email_allowlist(access, rsa_keys):
    client, settings, app, _ = access
    settings.cf_access_emails = 'Owner@Example.com, second@example.org'
    assert (await client.get('/', headers=access_headers(access_token(rsa_keys[0])))).status_code == 200
    for token in (access_token(rsa_keys[0], email='someone@example.com'), access_token(rsa_keys[0], email=None)):
        assert (await client.get('/', headers=access_headers(token))).status_code == 401
        assert await socket_messages(app, [(b'cf-access-jwt-assertion', token.encode())]) == [
            {'type': 'websocket.close', 'code': 1008}]


@pytest.mark.parametrize('unset', ['cf_access_team_domain', 'cf_access_aud'])
async def test_access_token_ignored_when_not_configured(access, rsa_keys, unset):
    client, settings, app, state = access
    setattr(settings, unset, '')
    token = access_token(rsa_keys[0])
    assert (await client.get('/', headers=access_headers(token))).status_code == 401
    assert await socket_messages(app, [(b'cf-access-jwt-assertion', token.encode())]) == [
        {'type': 'websocket.close', 'code': 1008}]
    assert state['calls'] == []
    assert (await client.get('/', headers={'X-Preview-Key': 'preview-example'})).status_code == 200


async def test_access_configured_keeps_passphrase_and_health(access):
    client, _, app, state = access
    assert (await client.get('/health')).status_code == 200
    assert (await client.get('/')).status_code == 401
    assert (await client.get('/', headers={'X-Preview-Key': 'preview-example'})).status_code == 200
    assert (await client.get('/', headers={'X-Preview-Key': 'preview-example',
                                           'Cf-Access-Jwt-Assertion': 'garbage'})).status_code == 200
    assert (await socket_messages(app, [(b'x-preview-key', b'preview-example')]))[1]['text'] == 'private app content'
    assert state['calls'] == []


async def test_access_key_fetch_failure_is_401_not_500(access, rsa_keys):
    client, _, app, state = access
    state['fail'] = True
    token = access_token(rsa_keys[0])
    assert (await client.get('/', headers=access_headers(token))).status_code == 401
    assert await socket_messages(app, [(b'cf-access-jwt-assertion', token.encode())]) == [
        {'type': 'websocket.close', 'code': 1008}]


async def test_access_unknown_kid_forces_one_throttled_refresh(access, rsa_keys):
    client, _, _, state = access
    for _ in range(3):
        assert (await client.get('/', headers=access_headers(access_token(rsa_keys[0], kid='rotated')))).status_code == 401
    assert [c for c in state['calls'] if c == ('fetch', True)] == [('fetch', True)]
