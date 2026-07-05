#!/usr/bin/env python3
"""Persona UAT driver — runs one synthetic persona end-to-end against a live
alea-intake deployment and captures every artifact for rubric judging.

Flow (matches the system map): register -> login -> consent -> create intake
(unbound; analysis is practice-area-agnostic) -> stream the client narrative over
the intake WebSocket -> upload synthetic PDFs -> trigger analysis (inline) -> poll
status -> pull results (claims/elements/gaps/questions) -> generate memo -> read
memo markdown -> export pdf/json. All raw outputs are written under
docs/evidence/persona-campaign/runs/<persona>/ for the judge stage.

Usage:
    python3 scripts/persona_run.py <persona_dir> [BASE_URL]

<persona_dir> must contain:
    narrative.txt          the client's messy first-person narrative
    docs/*.pdf             (optional) synthetic uploads (lease/notice/pay stub)

Requires: websockets (in backend/.venv). Run with backend/.venv/bin/python.
"""
import asyncio
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import websockets

BASE = ""  # set in main


def _req(method, path, token=None, body=None, timeout=120, raw=False, headers=None):
    data = None
    hdrs = headers or {}
    if body is not None and not raw:
        data = json.dumps(body).encode()
        hdrs.setdefault("content-type", "application/json")
    elif raw and body is not None:
        data = body
    if token:
        hdrs["Authorization"] = "Bearer " + token
    req = urllib.request.Request(BASE + path, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body_bytes = r.read()
            ctype = r.headers.get("content-type", "")
            if "application/json" in ctype:
                return r.status, json.loads(body_bytes.decode()), dict(r.headers)
            return r.status, body_bytes, dict(r.headers)
    except urllib.error.HTTPError as e:
        rb = e.read()
        try:
            return e.code, json.loads(rb.decode()), dict(e.headers)
        except Exception:
            return e.code, {"_raw": rb[:400].decode(errors="replace")}, dict(e.headers)


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


async def stream_narrative(session_id, token, party_id, narrative, transcript):
    ws_base = BASE.replace("https://", "wss://").replace("http://", "ws://")
    url = f"{ws_base}/api/ws/intake/{session_id}?token={token}"
    # Split the narrative into a couple of realistic chunks on blank lines.
    chunks = [c.strip() for c in narrative.split("\n\n") if c.strip()]
    if len(chunks) > 4:
        # keep it to ~3 messages: head, middle blob, tail
        chunks = [chunks[0], "\n\n".join(chunks[1:-1]), chunks[-1]]
    safety_alerts = []
    async with websockets.connect(url, max_size=4 * 1024 * 1024) as ws:
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


def poll_analysis(intake_id, token, transcript, max_wait=240):
    start = time.time()
    last = {}
    while time.time() - start < max_wait:
        s, j, _ = _req("GET", f"/api/v1/analysis/{intake_id}/status", token=token)
        last = j if isinstance(j, dict) else {}
        transcript.append({"stage": "poll_status", "http": s, "status": last.get("status"),
                           "iteration": last.get("iteration"), "progress": last.get("progress_pct")})
        if last.get("status") in ("converged", "completed", "failed", "error"):
            break
        time.sleep(4)
    return last


def run(persona_dir: Path, out_dir: Path):
    transcript = []
    email = f"persona_{persona_dir.name}_{int(time.time())}@example.com"
    pw = "PersonaTest123!"
    result = {"persona": persona_dir.name, "email": email, "base": BASE, "steps": {}}

    # 1. register
    s, j, _ = _req("POST", "/api/v1/auth/register",
                   body={"email": email, "password": pw, "full_name": f"Persona {persona_dir.name}"})
    token = (j or {}).get("access_token")
    result["steps"]["register"] = {"http": s, "ok": s == 201 and bool(token)}
    if not token:
        result["fatal"] = f"register failed: {s} {j}"
        return result

    # 2. consent
    s, j, _ = _req("POST", "/api/v1/consent/grant", token=token,
                   body={"consent_version": "1.0",
                         "consent_items": {"ai_processing": True, "data_storage": True}})
    result["steps"]["consent"] = {"http": s, "ok": s == 201}

    # 3. create intake (unbound)
    s, j, _ = _req("POST", "/api/v1/intake/", token=token, body={})
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
        alerts = asyncio.run(stream_narrative(session_id, token, party_id, narrative, transcript))
        result["steps"]["narrative"] = {"ok": True, "safety_alerts": len(alerts)}
        result["safety_alerts"] = alerts
    except Exception as e:
        result["steps"]["narrative"] = {"ok": False, "error": repr(e)}

    # 5. upload docs
    docs_dir = persona_dir / "docs"
    uploaded = []
    if docs_dir.is_dir():
        for f in sorted(docs_dir.glob("*")):
            ctype = mimetypes.guess_type(f.name)[0] or "application/pdf"
            body, mp_ctype = _multipart({"session_id": str(session_id), "party_id": str(party_id or "")},
                                        "file", f.name, f.read_bytes(), ctype)
            s, j, _ = _req("POST", f"/api/v1/intake/{intake_id}/document", token=token,
                           body=body, raw=True, headers={"content-type": mp_ctype})
            uploaded.append({"file": f.name, "http": s,
                             "extraction_status": (j or {}).get("extraction_status") if isinstance(j, dict) else None,
                             "detail": (j if isinstance(j, dict) else {}).get("detail")})
    result["steps"]["uploads"] = uploaded

    # 6. trigger analysis (inline)
    s, j, _ = _req("POST", f"/api/v1/analysis/{intake_id}/analyze", token=token, body={}, timeout=300)
    run_id = (j or {}).get("run_id")
    result["steps"]["analyze"] = {"http": s, "run_id": run_id,
                                  "status": (j or {}).get("status"),
                                  "detail": (j or {}).get("detail")}

    # 7. poll + results
    last = poll_analysis(intake_id, token, transcript)
    result["steps"]["final_status"] = last
    s, j, _ = _req("GET", f"/api/v1/analysis/{intake_id}/results", token=token)
    result["steps"]["results_http"] = s
    result["analysis"] = j if isinstance(j, dict) else {"_raw": str(j)[:500]}
    run_id = run_id or (j or {}).get("run_id")

    # 8. generate memos — a professional (law_firm) AND a plain-language
    # (court_self_help) memo so the judge can score both claim correctness and
    # RUB-INTAKE-10 reading level. legal_aid = accessible (10th grade) as a spare.
    memo_docs = []
    for profile in ("law_firm", "court_self_help", "legal_aid"):
        s, j, _ = _req("POST", "/api/v1/output/generate", token=token,
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
        s, j, _ = _req("GET", f"/api/v1/output/{doc_id}", token=token)
        md = (j or {}).get("markdown_content", "") if isinstance(j, dict) else ""
        (out_dir / f"memo_{doc_id}.md").write_text(md or "")
        entry = {"doc_id": doc_id, "profile": d.get("profile"),
                 "completeness": (j or {}).get("completeness_score") if isinstance(j, dict) else None,
                 "memo_chars": len(md or ""), "exports": {}}
        for fmt in ("pdf", "json"):
            s2, body2, hdrs2 = _req("GET", f"/api/v1/output/{doc_id}/export/{fmt}", token=token)
            ok = s2 == 200 and isinstance(body2, (bytes, bytearray)) and len(body2) > 0
            magic = ""
            if isinstance(body2, (bytes, bytearray)):
                magic = bytes(body2[:5]).decode(errors="replace")
                (out_dir / f"export_{doc_id}.{fmt}").write_bytes(bytes(body2))
            entry["exports"][fmt] = {"http": s2, "bytes": len(body2) if isinstance(body2, (bytes, bytearray)) else 0,
                                     "content_type": hdrs2.get("content-type") if isinstance(hdrs2, dict) else None,
                                     "magic": magic,
                                     "ok": ok and (fmt != "pdf" or magic.startswith("%PDF"))}
        outputs.append(entry)
    result["outputs"] = outputs
    result["transcript"] = transcript
    return result


def main():
    global BASE
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    persona_dir = Path(sys.argv[1]).resolve()
    BASE = (sys.argv[2] if len(sys.argv) > 2 else
            os.environ.get("ALEA_SMOKE_BASE",
                           "https://alea-intake-dev-production.up.railway.app")).rstrip("/")
    repo = Path(__file__).resolve().parents[1]
    out_dir = repo / "docs" / "evidence" / "persona-campaign" / "runs" / persona_dir.name
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"== Persona run: {persona_dir.name} vs {BASE} ==")
    result = run(persona_dir, out_dir)
    (out_dir / "run.json").write_text(json.dumps(result, indent=2, default=str))
    # compact console summary
    a = result.get("analysis", {})
    claims = a.get("claims", []) if isinstance(a, dict) else []
    gaps = a.get("gaps", []) if isinstance(a, dict) else []
    qs = a.get("questions", []) if isinstance(a, dict) else []
    print(f"  register={result['steps'].get('register', {}).get('ok')}"
          f" narrative={result['steps'].get('narrative', {}).get('ok')}"
          f" analyze={result['steps'].get('analyze', {}).get('status')}")
    print(f"  claims={len(claims)} gaps={len(gaps)} questions={len(qs)}"
          f" safety_alerts={len(result.get('safety_alerts', []))}")
    for c in claims[:12]:
        print(f"    - claim: {c.get('claim_name')} | iri={c.get('folio_iri')} "
              f"| conf={c.get('confidence')} | elements={len(c.get('elements', []))}")
    for o in result.get("outputs", []):
        print(f"  memo doc {o['doc_id']} ({o['profile']}): {o['memo_chars']} chars, "
              f"exports={ {k: v.get('ok') for k, v in o['exports'].items()} }")
    if result.get("fatal"):
        print(f"  FATAL: {result['fatal']}")
    print(f"  -> {out_dir}/run.json")


if __name__ == "__main__":
    main()
