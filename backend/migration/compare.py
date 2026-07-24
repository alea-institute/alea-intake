#!/usr/bin/env python3
"""Classified-delta comparator for the alea-intake -> folio-resolve migration.

Diffs two captures written by ``harness.py``, buckets every difference, classifies each one
against the corpus's stated expectation, then runs the migration canaries. Exits non-zero if a
canary fails or if any delta classifies as a **regression**.

Buckets
-------
* ``term_delta``   — expansion / branch-signal / stopword output changed
* ``score_delta``  — a fixed (query, label) pair scores differently, or ``_combine_score`` moved
* ``set_delta``    — a resolve seam gained or lost concepts
* ``rank_delta``   — the same concept set came back with different confidences/ordering
* ``fit_delta``    — a claim->concept fitness verdict changed

Classification
--------------
Unlike folio-mapper (whose swap was a pure internals swap onto code it had donated, so its bar
was an EMPTY delta), alea-intake's Stage-2 label scorer was a genuinely different, hand-rolled
set-intersection scorer, and its geographic gate was a hand-curated label list. Replacing them
with the library's word-order-invariant scorer and ``PlaceNameGate`` therefore *must* move
numbers. ``corpus.json`` records what each row is supposed to do (``expect`` / ``expect_reject``)
and every delta is bucketed as **intended_fix**, **regression**, or **neutral** against it.

Canaries
--------
1. **PLACE-REJECTED** — every claim-fitness row the corpus marks ``expect_reject`` must be
   rejected (BUG-21: no claim may map to a place / agency / placeholder / unfit branch), and no
   row marked fit may start being rejected.
2. **PLACES-RESOLVABLE** — the *general* resolver must still resolve an explicitly named place
   ("Macedonia" -> Macedonia). The place gate belongs to claim fitness, not to
   ``resolve_concepts``; this canary fails if it leaks in (the mirror of folio-mapper's
   PLACES-PRESERVED).
3. **EMPTY-STAYS-EMPTY** — stopword-only / empty / nonsense narratives must keep resolving to
   zero concepts.
4. **EMBED-DEGRADE** — with the embedding backend raising, narratives that still resolved via
   the label stage must keep doing so (BUG-9: the cascade is the point).
5. **NO-RECALL-LOSS** — a recall-sensitive narrative (exact / word_order / expansion /
   sub_phrase / compound / prefix) that resolved at least one concept must not fall to zero.

Usage::

    .venv/bin/python migration/compare.py --baseline baseline --candidate candidate
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

MIGRATION = Path(__file__).resolve().parent
CAPTURES_DIR = MIGRATION / "captures"
CORPUS_PATH = MIGRATION / "corpus.json"

# Narrative categories whose recall must not shrink (real legal content in the query).
RECALL_SENSITIVE = {"exact", "word_order", "expansion", "sub_phrase", "compound", "prefix"}
# Narrative categories where LOSING candidates is the point (junk the old scorer let through).
PRECISION_SENSITIVE = {"homonym", "short", "abbreviation"}
# Narrative categories that must resolve to nothing, before and after.
MUST_BE_EMPTY = {"stopword_only", "empty", "nonsense"}


def _load(name: str) -> dict[str, Any]:
    return json.loads((CAPTURES_DIR / f"{name}.json").read_text())


def _by_id(rows: list[dict]) -> dict[str, dict]:
    return {r["id"]: r for r in rows}


def _corpus() -> dict[str, Any]:
    return json.loads(CORPUS_PATH.read_text())


# ---------------------------------------------------------------------------
# Seam diffs
# ---------------------------------------------------------------------------


def diff_expansion(base: dict, cand: dict) -> list[dict]:
    out: list[dict] = []
    b, c = _by_id(base["expansion"]), _by_id(cand["expansion"])
    for rid, brow in b.items():
        crow = c.get(rid)
        if crow is None:
            out.append({"bucket": "term_delta", "seam": "expansion", "id": rid,
                        "classification": "regression", "why": "missing in candidate"})
            continue
        if brow["expansions"] != crow["expansions"] or brow["branch_signals"] != crow["branch_signals"]:
            out.append({
                "bucket": "term_delta", "seam": "expansion", "id": rid, "text": brow["text"],
                "classification": "neutral",
                "why": "consumer-narrative expansion vocabulary is a local seam; a change here is unexpected",
                "baseline": {"expansions": brow["expansions"], "branch_signals": brow["branch_signals"]},
                "candidate": {"expansions": crow["expansions"], "branch_signals": crow["branch_signals"]},
            })
    return out


def diff_stopword(base: dict, cand: dict) -> list[dict]:
    out: list[dict] = []
    b, c = _by_id(base["stopword"]), _by_id(cand["stopword"])
    for rid, brow in b.items():
        crow = c.get(rid, {})
        if brow["stopword_only"] != crow.get("stopword_only"):
            out.append({
                "bucket": "term_delta", "seam": "stopword", "id": rid, "text": brow["text"],
                "classification": "regression",
                "why": "the consumer stopword vocabulary is a local seam and must not move",
                "baseline": brow["stopword_only"], "candidate": crow.get("stopword_only"),
            })
    return out


def diff_combine(base: dict, cand: dict) -> list[dict]:
    out: list[dict] = []
    b, c = _by_id(base["combine"]), _by_id(cand["combine"])
    for rid, brow in b.items():
        crow = c.get(rid, {})
        if brow["combined"] != crow.get("combined"):
            out.append({
                "bucket": "score_delta", "seam": "combine", "id": rid,
                "classification": "regression",
                "why": "the 3-stage weighted-combine policy is a local seam and must not move",
                "baseline": brow["combined"], "candidate": crow.get("combined"),
            })
    return out


def diff_label_score(base: dict, cand: dict, expectations: dict[str, dict]) -> list[dict]:
    out: list[dict] = []
    b, c = _by_id(base["label_score"]), _by_id(cand["label_score"])
    for rid, brow in b.items():
        crow = c.get(rid)
        if crow is None:
            out.append({"bucket": "score_delta", "seam": "label_score", "id": rid,
                        "classification": "regression", "why": "missing in candidate"})
            continue
        bs, cs = brow["label_score"], crow["label_score"]
        if bs == cs:
            continue
        spec = expectations.get(rid, {})
        expect = spec.get("expect", "any")
        if bs is None or cs is None:
            direction = "appeared" if bs is None else "vanished"
        elif cs > bs:
            direction = "up"
        else:
            direction = "down"

        if expect == "same":
            classification = "regression"
        elif expect == "any":
            classification = "neutral"
        elif expect == direction:
            classification = "intended_fix"
        else:
            classification = "regression"

        out.append({
            "bucket": "score_delta", "seam": "label_score", "id": rid,
            "query": brow["query"], "label": brow["label"],
            "baseline": bs, "candidate": cs, "direction": direction,
            "expect": expect, "classification": classification,
            "why": spec.get("why", ""),
        })
    return out


def _rows(row: dict) -> dict[str, dict]:
    return {r["iri"]: r for r in row.get("top", [])}


def diff_resolve(seam: str, base: dict, cand: dict) -> list[dict]:
    out: list[dict] = []
    b, c = _by_id(base[seam]), _by_id(cand[seam])
    for rid, brow in b.items():
        crow = c.get(rid)
        if crow is None:
            out.append({"bucket": "set_delta", "seam": seam, "id": rid,
                        "classification": "regression", "why": "missing in candidate"})
            continue
        category = brow.get("category", "")
        btop, ctop = _rows(brow), _rows(crow)
        gained = sorted((r["label"], r["confidence"]) for i, r in ctop.items() if i not in btop)
        lost = sorted((r["label"], r["confidence"]) for i, r in btop.items() if i not in ctop)
        rescored = sorted(
            (r["label"], r["confidence"], ctop[i]["confidence"])
            for i, r in btop.items()
            if i in ctop and ctop[i]["confidence"] != r["confidence"]
        )
        if not (gained or lost or rescored):
            continue

        if category in MUST_BE_EMPTY:
            classification = "regression" if gained else "neutral"
            why = "a stopword-only / empty / nonsense narrative must resolve to nothing"
        elif category in RECALL_SENSITIVE:
            if crow["total"] == 0 and brow["total"] > 0:
                classification, why = "regression", "recall-sensitive narrative fell to zero concepts"
            elif gained and not lost:
                classification, why = "intended_fix", "recall gained on a legal-content narrative"
            elif lost and not gained:
                classification, why = "neutral", "candidate dropped below the 0.5 confidence bar"
            else:
                classification, why = "neutral", "candidate set changed on a recall-sensitive narrative"
        elif category in PRECISION_SENSITIVE:
            classification = "intended_fix" if lost and not gained else "neutral"
            why = "precision-sensitive narrative: dropping weak candidates is the goal"
        else:  # place, long_narrative, ...
            classification, why = "neutral", "no directional expectation for this category"

        out.append({
            "bucket": "set_delta" if (gained or lost) else "rank_delta",
            "seam": seam, "id": rid, "text": brow.get("text"), "category": category,
            "baseline_total": brow["total"], "candidate_total": crow["total"],
            "gained": gained, "lost": lost, "rescored": rescored[:5],
            "classification": classification, "why": why,
        })
    return out


def diff_fit(base: dict, cand: dict, expectations: dict[str, dict]) -> list[dict]:
    out: list[dict] = []
    b, c = _by_id(base["fit"]), _by_id(cand["fit"])
    for rid, brow in b.items():
        crow = c.get(rid)
        if crow is None:
            out.append({"bucket": "fit_delta", "id": rid, "classification": "regression",
                        "why": "missing in candidate"})
            continue
        if brow["rejected"] == crow["rejected"] and brow["unfit_reason"] == crow["unfit_reason"]:
            continue
        expect_reject = expectations.get(rid, {}).get("expect_reject", False)
        if crow["rejected"] and not brow["rejected"]:
            classification = "intended_fix" if expect_reject else "regression"
            why = ("a claim mapping the corpus marks unfit is now rejected"
                   if expect_reject else "a GOOD claim mapping started being rejected")
        elif brow["rejected"] and not crow["rejected"]:
            classification = "regression" if expect_reject else "intended_fix"
            why = ("an unfit claim mapping stopped being rejected"
                   if expect_reject else "a good claim mapping stopped being rejected")
        else:
            classification, why = "neutral", "rejection reason changed, verdict unchanged"
        out.append({
            "bucket": "fit_delta", "id": rid, "claim": brow["claim_name"],
            "label": brow["label"], "branch": brow["branch"], "category": brow["category"],
            "baseline": {"rejected": brow["rejected"], "reason": brow["unfit_reason"]},
            "candidate": {"rejected": crow["rejected"], "reason": crow["unfit_reason"]},
            "classification": classification, "why": why,
        })
    return out


# ---------------------------------------------------------------------------
# Canaries
# ---------------------------------------------------------------------------


def canary_place_rejected(cand: dict, expectations: dict[str, dict]) -> list[str]:
    failures: list[str] = []
    for row in cand["fit"]:
        expect_reject = expectations.get(row["id"], {}).get("expect_reject", False)
        if expect_reject and not row["rejected"]:
            failures.append(
                f"PLACE-REJECTED: {row['id']} — claim {row['claim_name']!r} -> {row['label']!r} "
                f"[{row['branch']}] is NOT rejected (BUG-21 regression)"
            )
        if not expect_reject and row["rejected"]:
            failures.append(
                f"PLACE-REJECTED: {row['id']} — a good claim mapping to {row['label']!r} "
                f"[{row['branch']}] was rejected as {row['unfit_reason']!r} (over-rejection)"
            )
    return failures


def canary_places_resolvable(base: dict, cand: dict) -> list[str]:
    failures: list[str] = []
    b, c = _by_id(base["resolve"]), _by_id(cand["resolve"])
    for rid, brow in b.items():
        if brow.get("category") != "place":
            continue
        crow = c.get(rid, {})
        if brow["total"] > 0 and crow.get("total", 0) == 0:
            failures.append(
                f"PLACES-RESOLVABLE: {rid} ({brow['text']!r}) lost every concept — the claim-fitness "
                "place gate must not leak into the general resolver"
            )
    return failures


def canary_empty_stays_empty(cand: dict) -> list[str]:
    return [
        f"EMPTY-STAYS-EMPTY: {row['id']} ({row['text']!r}) resolved {row['total']} concept(s)"
        for row in cand["resolve"]
        if row.get("category") in MUST_BE_EMPTY and row["total"] > 0
    ]


def canary_embed_degrade(base: dict, cand: dict) -> list[str]:
    failures: list[str] = []
    b, c = _by_id(base["resolve_no_embed"]), _by_id(cand["resolve_no_embed"])
    for rid, brow in b.items():
        crow = c.get(rid, {})
        if brow["total"] > 0 and crow.get("total", 0) == 0:
            failures.append(
                f"EMBED-DEGRADE: {rid} ({brow['text']!r}) resolved nothing with the embedding "
                "backend down — the BUG-9 label-stage cascade is broken"
            )
    return failures


def canary_no_recall_loss(base: dict, cand: dict) -> list[str]:
    failures: list[str] = []
    b, c = _by_id(base["resolve"]), _by_id(cand["resolve"])
    for rid, brow in b.items():
        if brow.get("category") not in RECALL_SENSITIVE:
            continue
        crow = c.get(rid, {})
        if brow["total"] > 0 and crow.get("total", 0) == 0:
            failures.append(
                f"NO-RECALL-LOSS: {rid} ({brow['text']!r}) fell from {brow['total']} concepts to zero"
            )
    return failures


# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", default="baseline")
    parser.add_argument("--candidate", default="candidate")
    parser.add_argument("--report", default=str(MIGRATION / "DELTA-REPORT.md"))
    args = parser.parse_args()

    base, cand = _load(args.baseline), _load(args.candidate)
    if base["corpus_hash"] != cand["corpus_hash"]:
        print("FATAL: captures came from different corpora (corpus_hash mismatch)")
        return 2

    corpus = _corpus()
    score_expect = {r["id"]: r for r in corpus["score_pairs"]}
    fit_expect = {r["id"]: r for r in corpus["fit"]}

    deltas: list[dict] = []
    deltas += diff_expansion(base, cand)
    deltas += diff_stopword(base, cand)
    deltas += diff_combine(base, cand)
    deltas += diff_label_score(base, cand, score_expect)
    deltas += diff_resolve("resolve", base, cand)
    deltas += diff_resolve("resolve_no_embed", base, cand)
    deltas += diff_fit(base, cand, fit_expect)

    failures = (
        canary_place_rejected(cand, fit_expect)
        + canary_places_resolvable(base, cand)
        + canary_empty_stays_empty(cand)
        + canary_embed_degrade(base, cand)
        + canary_no_recall_loss(base, cand)
    )

    buckets: dict[str, int] = {}
    classes: dict[str, int] = {}
    for d in deltas:
        buckets[d["bucket"]] = buckets.get(d["bucket"], 0) + 1
        classes[d["classification"]] = classes.get(d["classification"], 0) + 1

    regressions = [d for d in deltas if d["classification"] == "regression"]

    payload = {
        "baseline": args.baseline,
        "candidate": args.candidate,
        "baseline_env": base["env"],
        "candidate_env": cand["env"],
        "buckets": buckets,
        "classifications": classes,
        "deltas": deltas,
        "canary_failures": failures,
    }
    CAPTURES_DIR.mkdir(parents=True, exist_ok=True)
    (CAPTURES_DIR / "delta.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    lines = [
        "# alea-intake -> folio-resolve migration — classified delta report",
        "",
        f"- baseline capture: `{args.baseline}` (folio-resolve consumed: "
        f"`{base['env'].get('folio_resolve_consumed', False)}`)",
        f"- candidate capture: `{args.candidate}` (folio-resolve consumed: "
        f"`{cand['env'].get('folio_resolve_consumed', False)}`, version "
        f"`{cand['env'].get('folio_resolve_version')}`)",
        f"- corpus hash: `{base['corpus_hash'][:16]}…`",
        "",
        "## Headline",
        "",
        f"- Intended fixes: **{classes.get('intended_fix', 0)}**",
        f"- Regressions: **{len(regressions)}**",
        f"- Neutral changes: **{classes.get('neutral', 0)}**",
        "",
        "## Buckets",
        "",
    ]
    lines += [f"- **{k}** — {v}" for k, v in sorted(buckets.items())] or ["- _(empty)_"]
    lines += ["", "## Canaries", ""]
    if failures:
        lines += [f"- ❌ {f}" for f in failures]
    else:
        lines += [
            "- ✅ PLACE-REJECTED — every unfit claim mapping rejected; no good mapping over-rejected",
            "- ✅ PLACES-RESOLVABLE — the general resolver still resolves explicitly named places",
            "- ✅ EMPTY-STAYS-EMPTY — stopword-only / empty / nonsense narratives resolve to nothing",
            "- ✅ EMBED-DEGRADE — the label stage still carries the cascade when embeddings fail (BUG-9)",
            "- ✅ NO-RECALL-LOSS — no recall-sensitive narrative fell to zero concepts",
        ]

    if deltas:
        lines += ["", "## Deltas", "", "| id | seam | bucket | class | why | baseline | candidate |",
                  "|----|------|--------|-------|-----|----------|-----------|"]
        for d in sorted(deltas, key=lambda x: (x["classification"], x["seam"] if "seam" in x else "fit", x["id"])):
            if d.get("seam") == "label_score":
                b_s, c_s = d["baseline"], d["candidate"]
            elif d["bucket"] == "fit_delta":
                b_s = f"rejected={d['baseline']['rejected']} ({d['baseline']['reason']})"
                c_s = f"rejected={d['candidate']['rejected']} ({d['candidate']['reason']})"
            else:
                b_s = f"{d.get('baseline_total', d.get('baseline'))}"
                c_s = f"{d.get('candidate_total', d.get('candidate'))}"
                if d.get("gained") or d.get("lost"):
                    b_s += f" lost={d.get('lost')}"
                    c_s += f" gained={d.get('gained')}"
            lines.append(
                f"| {d['id']} | {d.get('seam', 'fit')} | {d['bucket']} | **{d['classification']}** | "
                f"{d.get('why', '')} | {b_s} | {c_s} |"
            )
    else:
        lines += ["", "## Deltas", "", "_(empty — behavior parity)_"]

    Path(args.report).write_text("\n".join(lines) + "\n")

    print(f"buckets:         {buckets or '{} (empty delta)'}")
    print(f"classifications: {classes or '{}'}")
    for f in failures:
        print(f"CANARY FAIL: {f}")
    for r in regressions:
        print(f"REGRESSION: {r['id']} — {r.get('why', '')}")
    print(f"wrote {args.report} and {CAPTURES_DIR / 'delta.json'}")
    return 1 if (failures or regressions) else 0


if __name__ == "__main__":
    raise SystemExit(main())
