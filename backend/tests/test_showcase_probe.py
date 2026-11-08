"""Exercise the executable probe offline through curl's process boundary."""
import os
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('mode', ['gated', 'public'])
@pytest.mark.parametrize('broken', ['', 'commit', 'isolation', 'purge', 'no-key'])
def test_probe_guest_flow(tmp_path, mode, broken):
    curl = tmp_path / 'curl'
    curl.write_text('''#!/usr/bin/python3
import json, os, sys
from pathlib import Path
config = dict()
headers = {}
for line in sys.stdin.read().splitlines():
    name, value = line.split(' = ', 1)
    value = json.loads(value)
    if name == 'header':
        k, v = value.split(': ', 1)
        headers[k] = v
    else:
        config[name] = value
path = config['url'].removeprefix('https://preview.test')
assert 'X-LLM-API-Key' not in headers
key = headers.get('X-Preview-Key')
assert key in (None, 'probe-private')
if os.environ['PROBE_MODE'] == 'public':
    assert key is None
state = Path(os.environ['PROBE_STATE'])
s = json.loads(state.read_text()) if state.exists() else {'guests': 0, 'ended': False}
broken = os.environ['PROBE_BROKEN']
status, body = 200, {}
if path == '/health':
    body = {'commit': 'wrong' if broken == 'commit' else 'build-example'}
elif os.environ['PROBE_MODE'] == 'gated' and key is None:
    status = 401
elif path == '/':
    body = {'page': True}
elif path == '/api/v1/auth/guest':
    assert json.loads(config['data']) == {'consent': True}
    s['guests'] += 1
    status, body = 201, {'access_token': 'guest-' + str(s['guests'])}
elif path == '/api/v1/intake/':
    assert headers['Authorization'] in ('Bearer guest-1', 'Bearer guest-2')
    status, body = 201, {'id': 42, 'session_id': 43}
elif path.endswith('/analyze'):
    status = 202 if broken == 'no-key' else 400
elif path.endswith('/end-session'):
    s['ended'] = True
    body = {'status': 'completed'}
elif path == '/api/v1/intake/42/messages?session_id=43':
    if headers['Authorization'] == 'Bearer guest-2':
        status = 200 if broken == 'isolation' else 404
    elif s['ended']:
        status = 200 if broken == 'purge' else 401
    else:
        body = {'messages': []}
else:
    raise AssertionError(path)
state.write_text(json.dumps(s))
print(json.dumps(body))
sys.stdout.write(str(status))
''')
    curl.chmod(0o755)
    result = subprocess.run(['bash', str(ROOT / 'scripts/verify-showcase.sh'),
                             'https://preview.test', '--mode', mode, '--commit', 'build-example'],
        env={**os.environ, 'PATH': str(tmp_path) + ':' + os.environ['PATH'],
             'VERIFY_PREVIEW_KEY': 'probe-private', 'PROBE_MODE': mode,
             'PROBE_STATE': str(tmp_path / 'state.json'), 'PROBE_BROKEN': broken},
        text=True, capture_output=True)
    assert 'probe-private' not in result.stdout + result.stderr
    if broken:
        assert result.returncode != 0
        label = {'commit': 'health', 'isolation': 'isolation',
                 'purge': 'purge guest access', 'no-key': 'no-key analyze'}[broken]
        assert 'FAIL ' + label in result.stdout + result.stderr
    else:
        assert result.returncode == 0, result.stdout + result.stderr
        for check in ('health', 'guest A', 'guest B', 'no-key', 'isolation', 'purge'):
            assert f'PASS {check}' in result.stdout
