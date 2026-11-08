#!/usr/bin/env python3
"""Run synthetic guest personas on one deployed commit, with explicit operator BYOK.

Usage: persona_run.py <persona_dir> <base_url>
       persona_run.py --base-url URL --models gpt-4o-mini candidate-model

PERSONA_LLM_API_KEY is required. PERSONA_LLM_PROVIDER/MODEL select the client.
PERSONA_PREVIEW_KEY supplies X-Preview-Key for the app preview gate.
"""
import argparse
import asyncio
import importlib.util
import json
import logging
import mimetypes
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
import websockets

REPO = Path(__file__).resolve().parents[1]

def sidecar(name):
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def now():
    return datetime.now(timezone.utc).isoformat()


class Campaign:
    def __init__(self, base, *, environ=None, transport=None, folio=None):
        env = os.environ if environ is None else environ
        self.key = env.get("PERSONA_LLM_API_KEY", "").strip()
        if not self.key:
            raise ValueError("PERSONA_LLM_API_KEY is required")
        self.base = base.rstrip("/")
        self.provider = env.get("PERSONA_LLM_PROVIDER", "openai")
        self.model = env.get("PERSONA_LLM_MODEL", "gpt-4o-mini")
        self.judge_model = env.get("PERSONA_JUDGE_MODEL", "gpt-4o-mini")
        self.secrets = [self.key]
        self.preview_headers = {}
        preview = env.get("PERSONA_PREVIEW_KEY")
        if preview:
            self.secrets.append(preview)
            self.preview_headers["X-Preview-Key"] = preview
        self.client = httpx.Client(base_url=self.base, transport=transport, timeout=300)
        self.folio = folio
        self.usage = []
        self.rates = json.loads(env.get("PERSONA_TOKEN_RATES", "{}"))

    def write(self, path, value):
        data = value if isinstance(value, bytes) else value.encode()
        for secret in self.secrets:
            for encoded in (secret, json.dumps(secret)[1:-1]):
                data = data.replace(encoded.encode(), b"[REDACTED]")
        path.write_bytes(data)

    def request(self, method, path, token=None, body=None, timeout=120, raw=False, headers=None):
        hdrs = {"X-LLM-API-Key": self.key, "X-LLM-Provider": self.provider,
                "X-LLM-Model": self.model, **(headers or {}), **self.preview_headers}
        if token:
            hdrs["Authorization"] = "Bearer " + token
        # Preview access and guest authentication use separate headers.
        response = self.client.request(method, path, headers=hdrs,
            content=body if raw else None, json=body if not raw else None, timeout=timeout)
        if not response.is_success:
            raise RuntimeError(f"Request failed: {method} {path} HTTP {response.status_code}")
        value = response.json() if "application/json" in response.headers.get("content-type", "") else response.content
        if isinstance(value, dict) and isinstance(value.get("usage"), dict):
            self.usage.append(value["usage"])
        return response.status_code, value, dict(response.headers)

    def commit(self):
        _, health, _ = self.request("GET", "/health")
        commit = health.get("commit")
        if not commit:
            raise RuntimeError("Deployment health has no commit")
        return commit

    def run(self, personas, out_root, models=None):
        commit = self.commit()
        models = models or [self.model]
        rows = []
        try:
            for index, model in enumerate(models):
                self.model = model
                for persona in personas:
                    if self.commit() != commit:
                        raise RuntimeError("Deployment commit changed during campaign")
                    out = out_root / persona.name
                    if len(models) > 1:
                        out = out / f"model-{index + 1}"
                    out.mkdir(parents=True, exist_ok=True)
                    self.usage = []
                    started = now()
                    result = self.run_persona(persona, out)
                    result.update(commit=commit, provider=self.provider, model=model,
                        started_at=started, finished_at=now(), judge_model=self.judge_model,
                        judge_prompt_version="intake-quality-v1.3-round-3", usage=self.usage)
                    self.write(out / "run.json", json.dumps(result, indent=2))
                    checker = sidecar("folio_check")
                    iris = list(checker.iter_iris(result))
                    if iris and self.folio is None:
                        self.folio = checker.load_folio()
                    folio_rows = [checker.check_iri(self.folio, iri) for _, _, iri in iris]
                    memo = sidecar("memo_checks").check_run(out / "run.json")
                    gates = {"folio": bool(iris) and all(row["ok"] for row in folio_rows),
                             "exports": bool(result.get("outputs")) and memo["exports_ok"],
                             "deadlines": memo["deadline_check"]["ok"],
                             "narrative": result.get("steps", {}).get("narrative", {}).get("ok", False)}
                    cost = self.cost(model)
                    result.update(deterministic_checks=gates, folio_checks=folio_rows,
                                  memo_checks=memo, estimated_cost_usd=cost)
                    self.write(out / "run.json", json.dumps(result, indent=2))
                    rows.append((model, persona.name, gates, cost))
            table = "| Model | Persona | Deterministic checks passed | Cost USD |\n|---|---|---|---|\n"
            for model, persona, gates, cost in rows:
                table += f"| {model} | {persona} | {sum(gates.values())}/{len(gates)} | {cost if cost is not None else 'unavailable'} |\n"
            self.write(out_root / "comparison.md", table)
            return rows
        finally:
            self.client.close()

    def cost(self, model):
        # Operator-supplied USD per million input/output tokens; never invent a price.
        rates = self.rates.get(model)
        if not rates or not self.usage:
            return None
        return sum((u.get("input_tokens", u.get("prompt_tokens", 0)) * rates[0] +
                    u.get("output_tokens", u.get("completion_tokens", 0)) * rates[1]) / 1_000_000
                   for u in self.usage)

    async def stream_narrative(self, session_id, token, party_id, narrative, transcript):
        ws_base = self.base.replace("https://", "wss://").replace("http://", "ws://")
        url = f"{ws_base}/api/ws/intake/{session_id}"
        # Split the narrative into a couple of realistic chunks on blank lines.
        chunks = [c.strip() for c in narrative.split("\n\n") if c.strip()]
        if len(chunks) > 4:
            # keep it to ~3 messages: head, middle blob, tail
            chunks = [chunks[0], "\n\n".join(chunks[1:-1]), chunks[-1]]
        safety_alerts = []
        async with websockets.connect(url, max_size=4 * 1024 * 1024, additional_headers=self.preview_headers,
                                      logger=logging.Logger("persona.websocket", level=logging.CRITICAL)) as ws:
            await ws.send(json.dumps({"type": "auth", "token": token,
                                      "llm_api_key": self.key, "llm_provider": self.provider,
                                      "llm_model": self.model}))
            # initial session_state
            try:
                first = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
                transcript.append({"dir": "recv", "msg": first})
            except asyncio.TimeoutError:
                pass
            for i, chunk in enumerate(chunks):
                frame = {"type": "text_message", "content": chunk,
                         "client_id": f"c{i}", "party_id": party_id}
                await ws.send(json.dumps(frame))
                transcript.append({"dir": "send", "msg": {"type": "text_message", "len": len(chunk)}})
                # Expect message_ack then system_message (+ maybe safety_alert). Read a few frames.
                got_system = False
                for _ in range(6):
                    try:
                        resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=90))
                    except asyncio.TimeoutError:
                        break
                    transcript.append({"dir": "recv", "msg": resp})
                    if resp.get("type") == "safety_alert":
                        safety_alerts.append(resp)
                    if resp.get("type") == "system_message":
                        got_system = True
                        break
                if not got_system:
                    transcript.append({"dir": "note", "msg": "no system_message before timeout"})
        return safety_alerts


    def poll_analysis(self, intake_id, token, transcript, max_wait=240):
        start = time.time()
        last = {}
        while time.time() - start < max_wait:
            s, j, _ = self.request("GET", f"/api/v1/analysis/{intake_id}/status", token=token)
            last = j if isinstance(j, dict) else {}
            transcript.append({"stage": "poll_status", "http": s, "status": last.get("status"),
                               "iteration": last.get("iteration"), "progress": last.get("progress_pct")})
            if last.get("status") in ("converged", "completed"):
                return last
            if last.get("status") in ("failed", "error"):
                raise RuntimeError("Analysis failed")
            time.sleep(4)
        raise RuntimeError("Analysis timed out")


    def run_persona(self, persona_dir: Path, out_dir: Path):
        transcript = []
        result = {"persona": persona_dir.name, "base": self.base, "steps": {}}
        s, j, _ = self.request("POST", "/api/v1/auth/guest", body={"consent": True})
        token = j["access_token"]
        self.secrets.append(token)
        result["steps"]["guest"] = {"http": s, "ok": s == 201}

        # 2. consent
        s, j, _ = self.request("POST", "/api/v1/consent/grant", token=token,
                       body={"consent_version": "1.0",
                             "consent_items": {"ai_processing": True, "data_storage": True}})
        result["steps"]["consent"] = {"http": s, "ok": s == 201}

        # 3. create intake (unbound)
        s, j, _ = self.request("POST", "/api/v1/intake/", token=token, body={})
        intake_id = (j or {}).get("id")
        session_id = (j or {}).get("session_id")
        party_id = (j or {}).get("party_id")
        result["steps"]["create_intake"] = {"http": s, "ok": s == 201,
                                             "intake_id": intake_id, "session_id": session_id,
                                             "party_id": party_id,
                                             "practice_area_id": (j or {}).get("practice_area_id")}
        if not (intake_id and session_id):
            result["fatal"] = f"create intake failed: {s} {j}"
            return result

        # 4. stream narrative over WS
        narrative = (persona_dir / "narrative.txt").read_text()
        try:
            alerts = asyncio.run(self.stream_narrative(session_id, token, party_id, narrative, transcript))
            result["steps"]["narrative"] = {"ok": True, "safety_alerts": len(alerts)}
            result["safety_alerts"] = alerts
        except Exception as e:
            result["steps"]["narrative"] = {"ok": False, "error": "Narrative delivery failed"}

        # 5. upload docs
        docs_dir = persona_dir / "docs"
        uploaded = []
        if docs_dir.is_dir():
            for f in sorted(docs_dir.glob("*")):
                ctype = mimetypes.guess_type(f.name)[0] or "application/pdf"
                body, mp_ctype = _multipart({"session_id": str(session_id), "party_id": str(party_id or "")},
                                            "file", f.name, f.read_bytes(), ctype)
                s, j, _ = self.request("POST", f"/api/v1/intake/{intake_id}/document", token=token,
                               body=body, raw=True, headers={"content-type": mp_ctype})
                uploaded.append({"file": f.name, "http": s,
                                 "extraction_status": (j or {}).get("extraction_status") if isinstance(j, dict) else None,
                                 "detail": (j if isinstance(j, dict) else {}).get("detail")})
        result["steps"]["uploads"] = uploaded

        # 6. trigger analysis (inline)
        s, j, _ = self.request("POST", f"/api/v1/analysis/{intake_id}/analyze", token=token, body={}, timeout=300)
        run_id = (j or {}).get("run_id")
        result["steps"]["analyze"] = {"http": s, "run_id": run_id,
                                      "status": (j or {}).get("status"),
                                      "detail": (j or {}).get("detail")}

        # 7. poll + results
        last = self.poll_analysis(intake_id, token, transcript)
        result["steps"]["final_status"] = last
        s, j, _ = self.request("GET", f"/api/v1/analysis/{intake_id}/results", token=token)
        result["steps"]["results_http"] = s
        result["analysis"] = j if isinstance(j, dict) else {"_raw": str(j)[:500]}
        run_id = run_id or (j or {}).get("run_id")

        # 8. generate memos — a professional (law_firm) AND a plain-language
        # (court_self_help) memo so the judge can score both claim correctness and
        # RUB-INTAKE-10 reading level. legal_aid = accessible (10th grade) as a spare.
        memo_docs = []
        for profile in ("law_firm", "court_self_help", "legal_aid"):
            s, j, _ = self.request("POST", "/api/v1/output/generate", token=token,
                           body={"run_id": run_id, "intake_id": intake_id, "profile_types": [profile]},
                           timeout=300)
            if s in (200, 201) and isinstance(j, dict):
                for d in j.get("documents", []):
                    memo_docs.append({"profile": profile, **d})
            else:
                memo_docs.append({"profile": profile, "http": s,
                                  "detail": (j if isinstance(j, dict) else {}).get("detail")})
        result["steps"]["output_generate"] = memo_docs

        # 9. read memo markdown + exports for each generated doc
        outputs = []
        for d in memo_docs:
            doc_id = d.get("id")
            if not doc_id:
                continue
            s, j, _ = self.request("GET", f"/api/v1/output/{doc_id}", token=token)
            md = (j or {}).get("markdown_content", "") if isinstance(j, dict) else ""
            self.write(out_dir / f"memo_{doc_id}.md", md or "")
            entry = {"doc_id": doc_id, "profile": d.get("profile"),
                     "completeness": (j or {}).get("completeness_score") if isinstance(j, dict) else None,
                     "memo_chars": len(md or ""), "exports": {}}
            for fmt in ("pdf", "json"):
                s2, body2, hdrs2 = self.request("GET", f"/api/v1/output/{doc_id}/export/{fmt}", token=token)
                # _req auto-parses application/json responses into dict/list —
                # the JSON export arrives parsed, not as bytes (was misreported
                # as bytes=0 / ok=False). Normalize both shapes to bytes.
                if isinstance(body2, (dict, list)):
                    body_bytes = json.dumps(body2, indent=1).encode()
                    parsed_ok = bool(body2)
                elif isinstance(body2, (bytes, bytearray)):
                    body_bytes = bytes(body2)
                    parsed_ok = len(body_bytes) > 0
                else:
                    body_bytes = b""
                    parsed_ok = False
                magic = body_bytes[:5].decode(errors="replace")
                if body_bytes:
                    self.write(out_dir / f"export_{doc_id}.{fmt}", body_bytes)
                ctype = None
                if isinstance(hdrs2, dict):
                    ctype = {k.lower(): v for k, v in hdrs2.items()}.get("content-type")
                # BUG-18: a parsed dict is truthy even when every field is an empty
                # shell ({claims_by_jurisdiction:{}, deadlines:[], executive_summary:
                # ""}). The old ok=bool(body2) passed those. Assert the JSON export
                # actually carries structured substance so an empty-shell export
                # FAILS RUB-15.
                json_substance = None
                if fmt == "json" and isinstance(body2, dict):
                    json_substance = bool(
                        body2.get("claims_by_jurisdiction")
                        or body2.get("deadlines")
                        or (body2.get("executive_summary") or "").strip()
                    )
                entry["exports"][fmt] = {"http": s2, "bytes": len(body_bytes),
                                         "content_type": ctype,
                                         "magic": magic,
                                         "json_substance": json_substance,
                                         "ok": s2 == 200 and parsed_ok
                                               and (fmt != "pdf" or magic.startswith("%PDF"))
                                               and (fmt != "json" or json_substance is True)}
            outputs.append(entry)
        result["outputs"] = outputs
        result["transcript"] = transcript
        return result


def _multipart(fields, file_field, filename, file_bytes, file_ctype):
    boundary = "----alea" + uuid.uuid4().hex
    parts = []
    for k, v in fields.items():
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
    parts.append(
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"{file_field}\"; filename=\"{filename}\"\r\n"
        f"Content-Type: {file_ctype}\r\n\r\n".encode()
    )
    parts.append(file_bytes)
    parts.append(f"\r\n--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("persona_dir", nargs="?", type=Path)
    parser.add_argument("url", nargs="?")
    parser.add_argument("--base-url", default=os.environ.get("ALEA_SMOKE_BASE"))
    parser.add_argument("--models", nargs="+")
    args = parser.parse_args()
    base = args.base_url or args.url
    if not base:
        parser.error("a deployed --base-url is required")
    personas = [args.persona_dir] if args.persona_dir else sorted(
        p.parent for p in (REPO / "docs/evidence/persona-campaign/personas").glob("*/narrative.txt"))
    try:
        Campaign(base).run(personas, REPO / "docs/evidence/persona-campaign/runs", args.models)
    except (ValueError, RuntimeError, httpx.HTTPError):
        print("Campaign aborted; check configuration, deployment and run artifacts.", file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
