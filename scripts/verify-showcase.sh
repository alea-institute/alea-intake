#!/usr/bin/env bash
exec python3 - "$@" <<'PY'
import argparse
import json
import os
import subprocess
import sys

parser = argparse.ArgumentParser(description='Verify a deployed showcase without an LLM key')
parser.add_argument('base_url')
parser.add_argument('--mode', required=True, choices=['gated', 'public'])
parser.add_argument('--commit')
args = parser.parse_args()
base = args.base_url.rstrip('/')
preview = os.environ.get('VERIFY_PREVIEW_KEY', '') if args.mode == 'gated' else ''


def fail(label, detail):
    print(f'FAIL {label}: {detail}', flush=True)
    sys.exit(1)


def check(label, condition, detail):
    if not condition:
        fail(label, detail)
    print(f'PASS {label}', flush=True)


def request(method, path, token=None, body=None, gated=True):
    # Keep credentials off the command line and out of diagnostic output.
    options = [('url', base + path), ('request', method)]
    if preview and gated:
        options.append(('header', 'X-Preview-Key: ' + preview))
    if token:
        options.append(('header', 'Authorization: Bearer ' + token))
    if body is not None:
        options += [('header', 'Content-Type: application/json'), ('data', json.dumps(body))]
    config = '\n'.join(name + ' = ' + json.dumps(value, ensure_ascii=False) for name, value in options)
    result = subprocess.run(['curl', '--silent', '--show-error', '--max-time', '30',
                             '--config', '-', '--write-out', '\n%{http_code}'],
                            input=config, text=True, capture_output=True)
    if result.returncode:
        fail(method + ' ' + path, 'curl transport failure')
    try:
        payload, status = result.stdout.rsplit('\n', 1)
        return int(status), payload
    except ValueError:
        fail(method + ' ' + path, 'invalid HTTP response')


def object_body(label, body):
    try:
        value = json.loads(body)
        if isinstance(value, dict):
            return value
    except ValueError:
        pass
    fail(label, 'expected JSON object')


def expect(label, method, path, expected, **kwargs):
    status, body = request(method, path, **kwargs)
    check(label, status in expected, f'HTTP {status}; expected {expected}')
    return body


status, body = request('GET', '/health', gated=False)
health = object_body('health', body)
def commit_matches(deployed, expected):
    # /health reports the full SHA (Coolify's SOURCE_COMMIT); accept an
    # abbreviated --commit of at least 7 hex characters as a prefix match.
    deployed = str(deployed or '').strip().lower()
    expected = str(expected or '').strip().lower()
    if not deployed or not expected:
        return False
    if len(deployed) == len(expected):
        return deployed == expected
    shorter, longer = sorted((deployed, expected), key=len)
    return len(shorter) >= 7 and longer.startswith(shorter)


check('health', status == 200 and bool(health.get('commit')) and
      (args.commit is None or commit_matches(health['commit'], args.commit)),
      f"health or deployed commit mismatch (deployed {health.get('commit')!r})")
if args.mode == 'gated':
    if not preview:
        fail('preview credential', 'VERIFY_PREVIEW_KEY is required in gated mode')
    expect('anonymous page refused', 'GET', '/', (401,), gated=False)
    expect('anonymous API refused', 'POST', '/api/v1/auth/guest', (401,), body={'consent': True}, gated=False)
expect('preview access' if preview else 'public access', 'GET', '/', (200,))

tokens = []
for who in ('A', 'B'):
    body = expect('guest ' + who, 'POST', '/api/v1/auth/guest', (201,), body={'consent': True})
    token = object_body('guest ' + who, body).get('access_token')
    check('guest ' + who + ' token', isinstance(token, str) and bool(token), 'missing guest token')
    tokens.append(token)
a, b = tokens
body = expect('create intake', 'POST', '/api/v1/intake/', (201,), token=a, body={})
created = object_body('create intake', body)
intake, session = created.get('id'), created.get('session_id')
check('intake identifiers', isinstance(intake, int) and isinstance(session, int), 'missing intake/session id')
messages = f'/api/v1/intake/{intake}/messages?session_id={session}'
expect('guest A reads intake', 'GET', messages, (200,), token=a)
expect('no-key analyze', 'POST', f'/api/v1/analysis/{intake}/analyze', (400,), token=a, body={})
expect('isolation', 'GET', messages, (404,), token=b)
expect('end session', 'POST', f'/api/v1/intake/{intake}/end-session', (200,), token=a)
# A purged guest token is denied: the consent middleware runs before auth and
# answers 403 (no consent on record); auth itself answers 401 or 404.
expect('purge guest access', 'GET', messages, (401, 403, 404), token=a)
expect('purge intake inaccessible', 'GET', messages, (404,), token=b)
body = expect('guest B cleanup intake', 'POST', '/api/v1/intake/', (201,), token=b, body={})
cleanup_id = object_body('guest B cleanup intake', body).get('id')
check('cleanup identifier', isinstance(cleanup_id, int), 'missing intake id')
expect('guest B cleanup', 'POST', f'/api/v1/intake/{cleanup_id}/end-session', (200,), token=b)
PY
