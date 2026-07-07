#!/usr/bin/env python
"""Deterministic sidecar checks for persona runs (RUB-08/09/10/15 inputs).

For every docs/evidence/persona-campaign/runs/<persona>/run.json:
  - reading level: Flesch-Kincaid grade (stdlib heuristic) per memo profile
    (RUB-10 target: court_self_help ~6th grade)
  - deadlines: what the pipeline computed (compare to personas/ANSWER-KEYS.md)
  - exports: integrity flags per format (RUB-15)

Read-only. No LLM, no network. Usage:
    backend/.venv/bin/python scripts/memo_checks.py [--json]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RUNS = Path(__file__).resolve().parents[1] / "docs/evidence/persona-campaign/runs"

_VOWELS = "aeiouy"


def _syllables(word: str) -> int:
    word = word.lower().strip(".,;:!?\"'()[]")
    if not word:
        return 0
    count, prev = 0, False
    for ch in word:
        is_v = ch in _VOWELS
        if is_v and not prev:
            count += 1
        prev = is_v
    if word.endswith("e") and count > 1:
        count -= 1
    return max(count, 1)


def fk_grade(text: str) -> float | None:
    """Flesch-Kincaid grade level; None if too little text."""
    # Strip markdown noise so headings/tables don't skew sentence counts.
    text = re.sub(r"[#*_`>|-]+", " ", text)
    words = [w for w in text.split() if any(c.isalpha() for c in w)]
    sentences = [s for s in re.split(r"[.!?]+", text) if len(s.split()) >= 2]
    if len(words) < 30 or not sentences:
        return None
    syll = sum(_syllables(w) for w in words)
    return round(
        0.39 * (len(words) / len(sentences)) + 11.8 * (syll / len(words)) - 15.59, 1
    )


def check_run(run_path: Path) -> dict:
    r = json.loads(run_path.read_text())
    persona = r.get("persona") or run_path.parent.name
    a = r.get("analysis") or {}
    out: dict = {
        "persona": persona,
        "claims": len(a.get("claims") or []),
        "claims_with_iri": sum(1 for c in a.get("claims") or [] if c.get("folio_iri")),
        "gaps": len(a.get("gaps") or []),
        "questions": len(a.get("questions") or []),
        "deadlines": a.get("deadlines") if isinstance(a.get("deadlines"), list) else [],
        "memos": [],
        "exports_ok": True,
    }
    for o in r.get("outputs") or []:
        profile = o.get("profile")
        memo_file = run_path.parent / f"memo_{o.get('doc_id')}.md"
        grade = fk_grade(memo_file.read_text()) if memo_file.exists() else None
        out["memos"].append(
            {"profile": profile, "chars": o.get("memo_chars"), "fk_grade": grade}
        )
        for fmt, e in (o.get("exports") or {}).items():
            if not e.get("ok"):
                out["exports_ok"] = False
                out.setdefault("export_failures", []).append(
                    {"doc": o.get("doc_id"), "format": fmt, "http": e.get("http")}
                )
    return out


def main() -> int:
    as_json = "--json" in sys.argv
    results = []
    for p in sorted(RUNS.glob("*/run.json")):
        results.append(check_run(p))
    if as_json:
        print(json.dumps(results, indent=1))
        return 0
    for r in results:
        print(f"== {r['persona']} ==")
        print(
            f"  claims={r['claims']} (with_iri={r['claims_with_iri']}) "
            f"gaps={r['gaps']} questions={r['questions']}"
        )
        for m in r["memos"]:
            tag = ""
            if m["profile"] == "court_self_help" and m["fk_grade"] is not None:
                tag = "  <-- RUB-10 target ~6"
            print(f"  memo {m['profile']}: {m['chars']} chars, FK grade {m['fk_grade']}{tag}")
        if r["deadlines"]:
            for d in r["deadlines"]:
                print(f"  deadline: {json.dumps(d, default=str)[:180]}")
        else:
            print("  deadline: NONE (RUB-08 gate check)")
        print(f"  exports_ok={r['exports_ok']}"
              + (f" failures={r.get('export_failures')}" if not r["exports_ok"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
