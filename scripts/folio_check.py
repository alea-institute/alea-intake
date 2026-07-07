#!/usr/bin/env python3
"""Deterministic FOLIO validation of mapped claim/fact IRIs (RUB-INTAKE-05).

Gestalt **lane 1** (deterministic, reproducible, near-zero token cost): loads
FOLIO via folio-python and, for every FOLIO IRI the system mapped, checks that

  1. the IRI **resolves** to a real concept in the current ontology,
  2. the concept is **not deprecated**, and
  3. the concept is **well-rooted** — its ``rdfs:subClassOf`` chain reaches the
     FOLIO root, so it sits under a real top-level branch (Event, Area of Law,
     Actor / Player, Document / Artifact, ...) rather than floating.

It reports each concept's label + resolved top-level branch so the *semantic*
pass (RUB-INTAKE-06 — "is this the RIGHT concept for this claim?") has the facts
it needs. Branch *fit* is a judgment call and deliberately left to that pass;
this script only certifies the IRI is real, live, and placed in the taxonomy.

Usage:
    backend/.venv/bin/python scripts/folio_check.py <run.json> [<run.json> ...]
    backend/.venv/bin/python scripts/folio_check.py --all      # every runs/*/run.json
    backend/.venv/bin/python scripts/folio_check.py --iri R7f8oRno6qr0y6rzgnqVgK0 ...
    backend/.venv/bin/python scripts/folio_check.py --iri - < iris.txt
    backend/.venv/bin/python scripts/folio_check.py --all --json    # machine summary

Exit code is 0 only when every checked IRI passes — usable as a CI/oracle gate.
folio-python is installed in backend/.venv.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RUNS = REPO / "docs/evidence/persona-campaign/runs"
OWL_THING = "http://www.w3.org/2002/07/owl#Thing"


def load_folio():
    from folio import FOLIO

    return FOLIO()  # default branch; OWL is cached after first load


def iter_iris(run: dict):
    """Yield (kind, name, iri) for every FOLIO IRI a persona run.json carries."""
    a = run.get("analysis", {}) or {}
    for c in a.get("claims", []) or []:
        iri = c.get("folio_iri")
        if iri:
            yield ("claim", c.get("claim_name", "") or "", iri)
        for el in c.get("elements", []) or []:
            iri = el.get("folio_iri")
            if iri:
                yield ("element", el.get("name", el.get("element_name", "")) or "", iri)
    # facts / resolved concepts, if the payload carries them
    for f in a.get("facts", []) or []:
        for rc in f.get("resolved_iris", []) or f.get("folio_concepts", []) or []:
            iri = rc.get("iri") if isinstance(rc, dict) else rc
            if iri:
                yield ("fact", (f.get("assertion_text") or "")[:50], iri)


def branch_of(folio, iri: str) -> tuple[str, bool]:
    """Walk subClassOf to the root; return (top_branch_label, is_rooted).

    is_rooted is True when the chain terminates at owl:Thing through at least one
    real FOLIO node (i.e. the concept is not orphaned directly under owl:Thing
    with no legal-domain ancestor).
    """
    seen: set[str] = set()
    cur = iri
    last_folio_label = ""
    reached_thing = False
    while cur and cur not in seen:
        seen.add(cur)
        if cur == OWL_THING:
            reached_thing = True
            break
        if cur not in folio:
            break
        obj = folio[cur]
        if obj.label:
            last_folio_label = obj.label
        parents = obj.sub_class_of or []
        cur = parents[0] if parents else None
    # rooted = reached owl:Thing via >=1 real folio node above the concept itself
    is_rooted = reached_thing and bool(last_folio_label)
    return last_folio_label, is_rooted


def check_iri(folio, iri: str) -> dict:
    """Return a structured verdict for a single IRI."""
    normalized = folio.normalize_iri(iri) if hasattr(folio, "normalize_iri") else iri
    if normalized not in folio:
        return {"iri": iri, "ok": False, "reason": "does-not-resolve"}
    obj = folio[normalized]
    branch, rooted = branch_of(folio, normalized)
    deprecated = bool(getattr(obj, "deprecated", False))
    ok = not deprecated and rooted
    reason = "ok"
    if deprecated:
        reason = "deprecated"
    elif not rooted:
        reason = "orphaned-not-rooted"
    return {
        "iri": normalized,
        "ok": ok,
        "reason": reason,
        "label": obj.label or obj.preferred_label or "",
        "branch": branch,
        "deprecated": deprecated,
        "has_definition": bool(getattr(obj, "definition", None)),
    }


def _emit_row(kind: str, name: str, v: dict) -> None:
    flag = "PASS" if v["ok"] else "FAIL"
    print(f"  [{flag}] {kind}: {name[:40]!r} -> {v['iri']}")
    if v.get("label"):
        extra = "" if v["reason"] == "ok" else f"  <{v['reason'].upper()}>"
        print(f"         label={v['label']!r}  branch={v.get('branch','')!r}{extra}")
    else:
        print(f"         <{v['reason'].upper()}>")


def main() -> None:
    args = sys.argv[1:]
    as_json = "--json" in args
    args = [a for a in args if a != "--json"]
    if not args:
        print(__doc__)
        sys.exit(2)

    # Collect (kind, name, iri) triples from whichever input mode.
    triples: list[tuple[str, str, str]] = []
    if args[0] == "--iri":
        raw = args[1:]
        if raw == ["-"]:
            raw = [line.strip() for line in sys.stdin if line.strip()]
        triples = [("iri", "", i) for i in raw]
        paths: list[Path] = []
    else:
        paths = sorted(RUNS.glob("*/run.json")) if args == ["--all"] else [Path(a) for a in args]

    folio = load_folio()
    grand_ok = grand_total = 0
    summary: list[dict] = []

    def tally(kind: str, name: str, iri: str) -> None:
        nonlocal grand_ok, grand_total
        v = check_iri(folio, iri)
        grand_total += 1
        if v["ok"]:
            grand_ok += 1
        if not as_json:
            _emit_row(kind, name, v)
        summary.append({"kind": kind, "name": name, **v})

    if triples:  # --iri mode
        if not as_json:
            print(f"\n== ad-hoc IRIs ({len(triples)}) ==")
        for kind, name, iri in triples:
            tally(kind, name, iri)
    else:  # run.json mode
        for p in paths:
            if not p.exists():
                print(f"!! {p} missing", file=sys.stderr)
                continue
            run = json.loads(p.read_text())
            rows = list(iter_iris(run))
            if not as_json:
                print(f"\n== {p.parent.name} ({len(rows)} mapped IRIs) ==")
            if not rows and not as_json:
                print("  (no FOLIO IRIs mapped — expected while the pipeline is LLM-blocked)")
            for kind, name, iri in rows:
                tally(kind, name, iri)

    result = {"ok": grand_ok, "total": grand_total, "pass": grand_ok == grand_total, "rows": summary}
    if as_json:
        print(json.dumps(result, indent=2))
    else:
        print(f"\n== TOTAL: {grand_ok}/{grand_total} IRIs resolve + rooted + live ==")

    sys.exit(0 if grand_ok == grand_total else 1)


if __name__ == "__main__":
    main()
