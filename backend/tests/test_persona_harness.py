"""Offline contracts for the deployed campaign."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def test_missing_operator_key_refuses_start():
    with pytest.raises(ValueError, match='PERSONA_LLM_API_KEY'):
        load('persona_run').Campaign('https://preview.test', environ={})


@pytest.mark.parametrize('failed_gate', [None, 'folio', 'exports', 'deadlines', 'narrative', 'empty'])
def test_main_exit_reflects_gates_after_writing_artifacts(tmp_path, monkeypatch, failed_gate):
    runner = load('persona_run')
    campaign = runner.Campaign('https://preview.test', environ={'PERSONA_LLM_API_KEY': 'test-only-key'}, folio={})
    monkeypatch.setattr(campaign, 'commit', lambda: 'build-a')
    monkeypatch.setattr(campaign, 'run_persona', lambda *args: {
        'outputs': [{'id': 1}], 'steps': {'narrative': {'ok': failed_gate != 'narrative'}},
    })
    checker = SimpleNamespace(iter_iris=lambda result: [(None, None, 'test-iri')],
                              check_iri=lambda *args: {'ok': failed_gate != 'folio'})
    memo = SimpleNamespace(check_run=lambda path: {
        'exports_ok': failed_gate != 'exports', 'deadline_check': {'ok': failed_gate != 'deadlines'},
    })
    monkeypatch.setattr(runner, 'sidecar', lambda name: checker if name == 'folio_check' else memo)
    monkeypatch.setattr(runner, 'Campaign', lambda base: campaign)
    monkeypatch.setattr(runner, 'REPO', tmp_path)
    args = ['persona_run.py', '--base-url', 'https://preview.test']
    if failed_gate != 'empty':
        args.append(str(tmp_path / 'example'))
    monkeypatch.setattr(runner.sys, 'argv', args)
    assert runner.main() == (0 if failed_gate is None else 1)
    out = tmp_path / 'docs/evidence/persona-campaign/runs'
    assert (out / 'comparison.md').exists()
    if failed_gate != 'empty':
        checks = json.loads((out / 'example/run.json').read_text())['deterministic_checks']
        assert all(checks.values()) == (failed_gate is None)

def test_commit_changes_abort_before_next_persona(tmp_path, monkeypatch):
    runner = load('persona_run')
    commits = iter(['build-a', 'build-a', 'build-b'])
    def respond(request):
        assert request.url.path == '/health'
        return httpx.Response(200, json={'commit': next(commits)})
    campaign = runner.Campaign('https://preview.test', environ={'PERSONA_LLM_API_KEY': 'operator-secret'}, transport=httpx.MockTransport(respond))
    monkeypatch.setattr(campaign, 'run_persona', lambda *a: {'outputs': [], 'analysis': {}})
    with pytest.raises(RuntimeError, match='commit changed'):
        campaign.run([Path('first'), Path('second')], tmp_path)

def test_guest_flow_secrets_preview_and_models(tmp_path, monkeypatch, caplog):
    runner = load('persona_run')
    persona = tmp_path / 'example'
    persona.mkdir()
    (persona / 'narrative.txt').write_text('My landlord locked me out.')
    requests = []
    def respond(request):
        requests.append(request)
        path = request.url.path
        body = {
            '/health': {'commit': 'build-a'},
            '/api/v1/auth/guest': {'access_token': 'guest-secret'},
            '/api/v1/intake/': {'id': 1, 'session_id': 2, 'party_id': 3},
            '/api/v1/analysis/1/analyze': {'run_id': 4},
            '/api/v1/analysis/1/status': {'status': 'completed'},
            '/api/v1/analysis/1/results': {'run_id': 4, 'claims': [], 'usage': {'input_tokens': 100, 'output_tokens': 20}},
            '/api/v1/output/generate': {'documents': [{'id': 5}]},
            '/api/v1/output/5': {'markdown_content': 'Memo echoes operator-secret.'},
            '/api/v1/output/5/export/json': {'executive_summary': 'Substantive memo'},
        }.get(path, {})
        if path.endswith('/export/pdf'):
            return httpx.Response(200, content=b'%PDF-1.4\noperator-secret')
        return httpx.Response(201 if request.method == 'POST' else 200, json=body)
    campaign = runner.Campaign('https://preview.test', environ={'PERSONA_LLM_API_KEY': 'operator-secret', 'PERSONA_PREVIEW_KEY': 'preview:secret', 'PERSONA_TOKEN_RATES': '{"gpt-4o-mini": [0.15, 0.6]}'}, transport=httpx.MockTransport(respond), folio={})
    async def narrative(*args):
        return []
    monkeypatch.setattr(campaign, 'stream_narrative', narrative)
    out = tmp_path / 'runs'
    campaign.run([persona], out, models=['gpt-4o-mini', 'other-model'])
    assert all(r.headers['X-Preview-Key'] == 'preview:secret' for r in requests)
    assert all('Proxy-Authorization' not in r.headers for r in requests)
    assert all(r.headers['X-LLM-API-Key'] == 'operator-secret' for r in requests if r.url.path != '/health')
    assert all('operator-secret' not in str(r.url) for r in requests)
    assert sum(r.url.path == '/api/v1/auth/guest' for r in requests) == 2
    assert 'gpt-4o-mini' in (out / 'comparison.md').read_text()
    runs = list(out.rglob('run.json'))
    assert len(runs) == 2
    metadata = next(json.loads(p.read_text()) for p in runs if json.loads(p.read_text())['model'] == 'gpt-4o-mini')
    assert metadata['estimated_cost_usd'] == pytest.approx(0.000027)
    assert metadata['commit'] == 'build-a'
    assert metadata['judge_model'] and metadata['judge_prompt_version']
    assert metadata['started_at'] and metadata['finished_at']
    for file in out.rglob('*'):
        if file.is_file():
            assert all(secret not in file.read_bytes() for secret in [b'operator-secret', b'preview:secret', b'guest-secret'])
    assert 'operator-secret' not in caplog.text

def test_folio_rejects_substring_and_accepts_exact_iri():
    checker = load('folio_check')
    class Ontology(dict):
        def __contains__(self, iri):
            return any(iri.lower() in obj.label.lower() for obj in self.values()) or super().__contains__(iri)
    iri = 'https://folio.openlegalstandard.org/Rrepresentation'
    folio = Ontology({iri: SimpleNamespace(iri=iri, label='Representation', sub_class_of=[checker.OWL_THING])})
    assert checker.check_iri(folio, 'Resen')['ok'] is False
    assert checker.check_iri(folio, iri)['ok'] is True


def test_deadline_dates_are_compared_to_answer_key():
    checker = load('memo_checks')
    assert checker.deadline_check('consumer-debt', [{'date': '2026-07-25'}])['ok']
    assert not checker.deadline_check('consumer-debt', [{'date': '2026-07-20'}])['ok']


async def test_websocket_auth_is_first_message_and_preview_is_attached(monkeypatch, caplog):
    import logging
    caplog.set_level(logging.DEBUG)
    runner = load('persona_run')
    sent, connections = [], []
    class Socket:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def send(self, frame):
            sent.append(json.loads(frame))
        async def recv(self):
            return json.dumps({'type': 'session_state' if not sent else 'system_message'})
    def connect(url, **kwargs):
        kwargs["logger"].debug("sending operator-secret")
        connections.append((url, kwargs))
        return Socket()
    monkeypatch.setattr(runner.websockets, 'connect', connect)
    campaign = runner.Campaign('https://preview.test', environ={'PERSONA_LLM_API_KEY': 'operator-secret', 'PERSONA_PREVIEW_KEY': 'preview-secret'})
    await campaign.stream_narrative(2, 'guest-token', 3, 'My story.', [])
    assert connections[0][0] == 'wss://preview.test/api/ws/intake/2'
    assert connections[0][1]['additional_headers']['X-Preview-Key'] == 'preview-secret'
    assert sent[0] == {'type': 'auth', 'token': 'guest-token', 'llm_api_key': 'operator-secret', 'llm_provider': 'openai', 'llm_model': 'gpt-4o-mini'}
    assert sent[1]['content'] == 'My story.'
    assert 'operator-secret' not in caplog.text


def test_folio_checks_nested_output_iris():
    checker = load('folio_check')
    run = {'analysis': {'claims': [], 'gaps': [{'folio_iri': 'Resen'}]},
           'outputs': [{'concept': {'iri': 'https://folio.openlegalstandard.org/Rreal'}}]}
    assert {iri for _, _, iri in checker.iter_iris(run)} == {'Resen', 'https://folio.openlegalstandard.org/Rreal'}
