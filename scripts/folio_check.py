#!/usr/bin/env python3
"""Deterministic FOLIO validation of a persona run's claim/fact IRIs (RUB-INTAKE-05).

Gestalt lane-1 (deterministic, near-zero cost): loads FOLIO via folio-python and
checks that every FOLIO IRI the system mapped actually resolves to a real concept,
reporting its label + branch so a human/semantic pass (RUB-INTAKE-06) can judge fit.

Usage:
    backend/.venv/bin/python scripts/folio_check.py <run.json> [<run.json> ...]
    backend/.venv/bin/python scripts/folio_check.py --all   # every runs/*/run.json

Reads claims[].folio_iri (and any fact-level resolved IRIs if present) from each
run.json produced by persona_run.py and emits a compact PASS/FAIL table.
"""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RUNS = REPO / "docs/evidence/persona-campaign/runs"
IRI_RE = re.compile(r"https?://folio\.openlegalstandard\.org/\S+")


def load_folio():
    from folio import FOLIO
    return FOLIO()  # default branch; loads OWL (cached)


def iter_iris(run: dict):
    a = run.get("analysis", {}) or {}
    for c in a.get("claims", []) or []:
        iri = c.get("folio_iri")
        if iri:
            yield ("claim", c.get("claim_name", ""), iri)
    # facts / resolved concepts if the run payload carries them
    for f in a.get("facts", []) or []:
        for rc in f.get("resolved_iris", []) or f.get("folio_concepts", []) or []:
            iri = rc.get("iri") if isinstance(rc, dict) else rc
            if iri:
                yield ("fact", (f.get("assertion_text") or "")[:50], iri)


def resolve(folio, iri: str):
    """Return (ok, label, branch) for an IRI using folio-python."""
    try:
        obj = None
        # folio-python supports __getitem__ by IRI/id and .get_by_iri in some versions
        for accessor in ("get_by_iri", "__getitem__"):
            try:
                obj = getattr(folio, accessor)(iri) if accessor == "get_by_iri" else folio[iri]
                if obj:
                    break
            except Exception:
                continue
        if not obj:
            return False, "", ""
        label = getattr(obj, "label", None) or getattr(obj, "preferred_label", None) or ""
        # branch/parent hint
        branch = ""
        parents = getattr(obj, "sub_class_of", None) or getattr(obj, "parents", None) or []
        if parents:
            branch = str(parents[0])
        return True, str(label), branch
    except Exception as e:
        return False, f"error:{e}", ""


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(2)
    if args == ["--all"]:
        paths = sorted(RUNS.glob("*/run.json"))
    else:
        paths = [Path(a) for a in args]

    folio = load_folio()
    grand_ok = grand_total = 0
    for p in paths:
        if not p.exists():
            print(f"!! {p} missing")
            continue
        run = json.loads(p.read_text())
        rows = list(iter_iris(run))
        print(f"\n== {p.parent.name} ({len(rows)} mapped IRIs) ==")
        ok_n = 0
        for kind, name, iri in rows:
            ok, label, branch = resolve(folio, iri)
            grand_total += 1
            if ok:
                ok_n += 1
                grand_ok += 1
            flag = "PASS" if ok else "FAIL"
            print(f"  [{flag}] {kind}: {name[:40]!r} -> {iri}")
            if ok:
                print(f"         label={label!r} branch~{branch[:60]}")
        if rows:
            print(f"  -> {ok_n}/{len(rows)} IRIs resolve")
        else:
            print("  (no FOLIO IRIs mapped — expected while pipeline is inert)")
    print(f"\n== TOTAL: {grand_ok}/{grand_total} IRIs resolve ==")


if __name__ == "__main__":
    main()
