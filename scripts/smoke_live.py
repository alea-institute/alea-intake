#!/usr/bin/env python3
"""Automated end-to-end smoke test against a live alea-intake deployment.

Exercises the core user journey over the public REST API — auth, consent
enforcement, practice-area binding (Phase 13), and input validation — so you can
confirm a deploy is healthy without clicking through the UI. Stdlib only; no deps.

Usage:
    python3 scripts/smoke_live.py [BASE_URL]
    ALEA_SMOKE_BASE=https://... python3 scripts/smoke_live.py

Default BASE_URL is the dev server. Exits 0 if all checks pass, 1 otherwise.

Note: the conversational message flow runs over WebSocket and is not covered here;
this harness validates the REST surface.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = (
    (sys.argv[1] if len(sys.argv) > 1 else None)
    or os.environ.get("ALEA_SMOKE_BASE")
    or "https://alea-intake-dev-production.up.railway.app"
).rstrip("/")

results: list[tuple[str, bool, str]] = []


def call(method, path, token=None, body=None, timeout=30):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"content-type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode()
            return r.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"_raw": raw[:200]}


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def main():
    print(f"== Automated E2E smoke: {BASE} ==")
    email = f"smoke+{int(time.time())}@example.com"
    pw = "SmokeTest123!"

    s, j = call("GET", "/health")
    check("health: healthy + db up",
          s == 200 and j.get("status") == "healthy" and j.get("database", {}).get("status") == "up",
          f"status={j.get('status')} db={j.get('database', {}).get('status')}")

    s, j = call("GET", "/api/practice-areas")
    ids = [p.get("id") for p in j.get("practice_areas", [])]
    check("practice-areas: personal_injury present", s == 200 and "personal_injury" in ids, f"ids={ids}")

    s, j = call("POST", "/api/v1/auth/register",
                body={"email": email, "password": pw, "full_name": "Smoke Test"})
    token = j.get("access_token")
    check("register: 201 + token", s == 201 and bool(token), f"http={s}")

    s, j = call("POST", "/api/v1/auth/login", body={"email": email, "password": pw})
    check("login: 200 + token", s == 200 and bool(j.get("access_token")), f"http={s}")
    token = j.get("access_token") or token

    # Consent gate: intake must be blocked before consent is granted.
    s, j = call("POST", "/api/v1/intake/", token=token, body={"practice_area_id": "personal_injury"})
    check("consent gate: intake blocked w/o consent (403)", s == 403, f"http={s}")

    s, j = call("POST", "/api/v1/consent/grant", token=token,
                body={"consent_version": "1.0", "consent_items": {"ai_processing": True, "data_storage": True}})
    check("consent: grant 201", s == 201, f"http={s}")

    s, j = call("POST", "/api/v1/intake/", token=token, body={"practice_area_id": "personal_injury"})
    check("intake: create PI (201) + bound", s == 201 and j.get("practice_area_id") == "personal_injury",
          f"http={s} pa={j.get('practice_area_id')}")
    pi_id, pi_sess = j.get("id"), j.get("session_id")

    s, j = call("POST", "/api/v1/intake/", token=token, body={})
    check("intake: create generic (201) + unbound", s == 201 and j.get("practice_area_id") in (None, ""),
          f"http={s} pa={j.get('practice_area_id')}")

    s, j = call("POST", "/api/v1/intake/", token=token, body={"practice_area_id": "totally_not_real_xyz"})
    check("intake: unknown practice area -> 400", s == 400, f"http={s}")

    s, j = call("GET", "/api/v1/intake/", token=token)
    n = len(j) if isinstance(j, list) else len(j.get("items", j.get("intakes", [])))
    check("intake: list returns created intakes", s == 200 and n >= 2, f"http={s} count={n}")

    if pi_id and pi_sess:
        s, j = call("GET", f"/api/v1/intake/{pi_id}/messages?session_id={pi_sess}", token=token)
        check("intake: messages endpoint 200", s == 200, f"http={s}")

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"\n== RESULT: {passed}/{total} passed ==")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
