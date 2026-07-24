#!/usr/bin/env python3
"""Characterization lab for the ``_combine_score`` averaging oddity.

``migration/README.md`` records the defect in one line: *"a weak embedding hit is worse than no
embedding hit"*. This module pins that down exactly — the algebra, the minimal reproductions
through the real ``_combine_score``, an end-to-end demonstration through the real
``resolve_concepts``, and an analytic comparison of three candidate remedies against four
invariants plus the synthetic corpus.

**Nothing here changes behavior.** The remedies live in ``migration/sweep.py`` (harness code);
``app/`` is untouched. Run it, read ``captures/combine-lab.md``, decide separately.

Usage::

    .venv/bin/python migration/combine_lab.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execv(sys.executable, [sys.executable, *sys.argv])

MIGRATION = Path(__file__).resolve().parent
BACKEND = MIGRATION.parent
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(MIGRATION))

import logging  # noqa: E402

logging.disable(logging.CRITICAL)

import sweep  # noqa: E402  (harness module: the remedies live there)

CAPTURES_DIR = MIGRATION / "captures"
RULES = ("current", "floor", "presence", "coverage")
REF_PENALTY = 0.7
REF_THRESHOLD = 0.5


# ---------------------------------------------------------------------------
# 1. The algebra
# ---------------------------------------------------------------------------


def inversion_algebra(penalty: float = REF_PENALTY, threshold: float = REF_THRESHOLD) -> dict:
    """Closed form for both halves of the oddity.

    A candidate the label stage scores ``L``:

    * not retrieved by embeddings at all  ->  ``penalty × L``
    * retrieved at cosine ``e``           ->  ``(e + L) / 2``   (weights are equal: 0.3 / 0.3)

    **Rank inversion** when ``(e + L)/2 < penalty × L``, i.e. ``e < (2·penalty − 1) × L``.
    **Accept inversion** — the damaging half — when the candidate would have cleared the bar
    unretrieved but does not retrieved: ``penalty × L ≥ threshold > (e + L)/2``, i.e.
    ``L ≥ threshold/penalty`` and ``e < 2·threshold − L``.
    """
    return {
        "penalty": penalty,
        "threshold": threshold,
        "rank_inversion_when": f"e < {2 * penalty - 1:.2f} × L",
        "accept_inversion_when": (
            f"L ≥ {threshold / penalty:.4f} and e < {2 * threshold:.2f} − L"
        ),
        # The widest possible accept-inversion band: L at the solo bar exactly.
        "worst_case_L": round(threshold / penalty, 4),
        "worst_case_e_band": round(2 * threshold - threshold / penalty, 4),
    }


# ---------------------------------------------------------------------------
# 2. Minimal reproductions through the REAL _combine_score
# ---------------------------------------------------------------------------


def minimal_cases() -> list[dict]:
    """Hand-built (embedding, label) pairs that isolate the inversion.

    Uses the production function itself — these are observations, not a model of it.
    """
    from app.services.folio.concept_resolver import _combine_score

    cases = [
        ("no embedding hit", None, 0.72),
        ("embedding hit at 0.05", 0.05, 0.72),
        ("embedding hit at 0.10", 0.10, 0.72),
        ("embedding hit at 0.28", 0.28, 0.72),
        ("embedding hit at 0.40", 0.40, 0.72),
        ("the corpus's real shape: Habitability -> Breach of Warranty of Habitability", None, 0.675),
        ("...same, weakly retrieved", 0.10, 0.675),
        ("...same, retrieved as the corpus actually does", 0.50, 0.675),
    ]
    rows = []
    for name, e, label in cases:
        combined = _combine_score(embedding_score=e, label_score=label)
        rows.append(
            {
                "case": name,
                "embedding": e,
                "label": label,
                "combined": round(combined, 4),
                "accepted": combined >= REF_THRESHOLD,
            }
        )
    return rows


# ---------------------------------------------------------------------------
# 3. End to end, through the real resolver
# ---------------------------------------------------------------------------


class _OneConceptFOLIO:
    """A two-node ontology: one branch root, one concept whose label the query matches."""

    def __init__(self, label: str) -> None:
        self._cls = type(
            "_C",
            (),
            {
                "iri": "r-x",
                "label": label,
                "sub_class_of": [],
                "definition": "",
                "alternative_labels": [],
            },
        )()

    def __contains__(self, iri: str) -> bool:
        return iri == "r-x"

    def __getitem__(self, iri: str):
        return self._cls

    @property
    def classes(self):
        return [self._cls]

    def get_objectives(self):
        return []

    def get_areas_of_law(self):
        return []

    def get_legal_authorities(self):
        return []

    def get_locations(self):
        return []

    def search_by_label(self, query: str, limit: int = 10):
        return [(self._cls, 1.0)]

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<_OneConceptFOLIO {self._cls.label!r}>"

    def search_by_prefix(self, text: str):
        return []


class _FixedEmbedding:
    """Returns the concept at a fixed cosine — or nothing at all."""

    def __init__(self, score: float | None, label: str) -> None:
        self._score = score
        self._label = label

    async def search(self, text: str, top_k: int = 10):
        from app.services.embedding.backends import SearchResult

        if self._score is None:
            return []
        return [
            SearchResult(iri="r-x", label=self._label, score=self._score,
                         metadata={"branch": "Objectives"})
        ]


E2E_QUERY = "Retaliation"
E2E_LABEL = "Retaliation Claim"


def end_to_end() -> list[dict]:
    """The same query, resolved three times, varying only how strongly embeddings retrieve it.

    This is the production ``resolve_concepts`` — no reconstruction, no stubs beyond the two
    offline doubles the harness already owns. The pair is chosen so the label score (0.736)
    clears the solo bar (0.7143): that is the band where the inversion is *visible* rather than
    merely present, because both sides of it straddle the accept decision.
    """
    from app.services.folio.concept_resolver import ConceptResolutionConfig, resolve_concepts

    folio = _OneConceptFOLIO(E2E_LABEL)
    config = ConceptResolutionConfig(enable_llm_stage=False)
    rows = []
    for name, score in (
        ("embedding stage returns nothing", None),
        ("embedding stage returns it at cosine 0.10", 0.10),
        ("embedding stage returns it at cosine 0.20", 0.20),
        ("embedding stage returns it at cosine 0.30", 0.30),
    ):
        results = asyncio.run(
            resolve_concepts(
                text=E2E_QUERY,
                folio=folio,
                embedding_service=_FixedEmbedding(score, E2E_LABEL),
                config=config,
                llm_model=None,
            )
        )
        rows.append(
            {
                "case": name,
                "embedding": score,
                "resolved": len(results),
                "confidence": results[0].confidence if results else None,
            }
        )
    return rows


# ---------------------------------------------------------------------------
# 4. Remedy invariants
# ---------------------------------------------------------------------------

_STEPS = [round(i / 20, 2) for i in range(21)]


def _rule(e, label, rule, penalty=REF_PENALTY):
    return sweep.combined_score(e, label, None, penalty=penalty, rule=rule)


def invariants(rule: str, penalty: float = REF_PENALTY) -> dict:
    """Four properties, checked by exhaustive evaluation on a 0.05 lattice.

    * ``evidence_monotone`` — adding a stage never LOWERS the score (the defect under study).
    * ``stage_monotone`` — raising any one stage score never lowers the combined score.
    * ``bounded`` — the result stays in [0, 1].
    * ``scale_preserved`` — an exact single-stage label match (0.99) still lands near the top of
      the scale rather than being rescaled into a different regime. Recorded as the score, so
      the reader can see the cost rather than a bare boolean.
    """
    evidence_ok = True
    worst_evidence_drop = 0.0
    for label in _STEPS:
        solo = _rule(None, label, rule, penalty)
        for e in _STEPS:
            drop = solo - _rule(e, label, rule, penalty)
            if drop > 1e-12:
                evidence_ok = False
                worst_evidence_drop = max(worst_evidence_drop, drop)

    stage_ok = True
    for label in _STEPS:
        prev = None
        for e in _STEPS:
            cur = _rule(e, label, rule, penalty)
            if prev is not None and cur + 1e-12 < prev:
                stage_ok = False
            prev = cur
    for e in _STEPS:
        prev = None
        for label in _STEPS:
            cur = _rule(e, label, rule, penalty)
            if prev is not None and cur + 1e-12 < prev:
                stage_ok = False
            prev = cur

    bounded = all(
        0.0 <= _rule(e, label, rule, penalty) <= 1.0 for e in _STEPS for label in _STEPS
    ) and all(0.0 <= _rule(None, label, rule, penalty) <= 1.0 for label in _STEPS)

    return {
        "rule": rule,
        "evidence_monotone": evidence_ok,
        "worst_evidence_drop": round(worst_evidence_drop, 4),
        "stage_monotone": stage_ok,
        "bounded": bounded,
        "exact_label_only": round(_rule(None, 0.99, rule, penalty), 4),
        "exact_both_stages": round(_rule(0.99, 0.99, rule, penalty), 4),
    }


def corpus_effect(rule: str, penalty: float, threshold: float) -> dict:
    """How many corpus candidates does this rule actually move, and across the bar?"""
    corpus = sweep._corpus()
    gold = sweep._gold()
    pools = sweep.build_pools(corpus, None)
    reference = sweep.evaluate_point(
        pools, penalty=sweep.REF_PENALTY, threshold=sweep.REF_THRESHOLD, rule="current"
    )
    accepted = sweep.evaluate_point(pools, penalty=penalty, threshold=threshold, rule=rule)
    metrics = sweep.score_point(accepted, gold, reference, corpus)

    moved = inversion_region = 0
    for mode, per_narrative in pools.items():
        for cands in per_narrative.values():
            for d in cands.values():
                e, label = d.get("embedding_score"), d.get("label_score")
                base = sweep.combined_score(e, label, None, penalty=penalty, rule="current")
                new = sweep.combined_score(e, label, None, penalty=penalty, rule=rule)
                if abs(new - base) > 1e-9:
                    moved += 1
                if e is not None and label is not None:
                    if (e + label) / 2 < penalty * max(e, label) - 1e-12:
                        inversion_region += 1
    return {
        "rule": rule,
        "penalty": penalty,
        "threshold": threshold,
        "candidates_rescored": moved,
        "candidates_in_inversion_region": inversion_region,
        "f1_healthy": metrics["healthy"]["f1"],
        "f1_degraded": metrics["degraded"]["f1"],
        "flips_accept": metrics["healthy"]["flips_accept"] + metrics["degraded"]["flips_accept"],
        "flips_reject": metrics["healthy"]["flips_reject"] + metrics["degraded"]["flips_reject"],
        "order_changes": metrics["healthy"]["order_changes"] + metrics["degraded"]["order_changes"],
        "canaries_green": metrics["canaries_green"],
    }


# ---------------------------------------------------------------------------


def main() -> int:
    algebra = inversion_algebra()
    cases = minimal_cases()
    e2e = end_to_end()

    lines = [
        "# The average-combine oddity — characterization and remedies",
        "",
        "_Generated by `migration/combine_lab.py`. Study only: nothing under `app/` is changed._",
        "",
        "## 1. The algebra",
        "",
        f"At the production operating point (penalty **{algebra['penalty']}**, threshold "
        f"**{algebra['threshold']}**), for a candidate the label stage scores `L`:",
        "",
        "| | score |",
        "|---|---|",
        "| not retrieved by the embedding stage | `penalty × L` |",
        "| retrieved at cosine `e` | `(e + L) / 2` — the two stages carry equal weight (0.3 / 0.3) |",
        "",
        f"* **Rank inversion** whenever `{algebra['rank_inversion_when']}`.",
        f"* **Accept inversion** — a candidate that would have been RETURNED unretrieved is "
        f"DROPPED once retrieved — whenever `{algebra['accept_inversion_when']}`.",
        "",
        f"The widest accept-inversion band sits at `L = {algebra['worst_case_L']}` (the solo "
        f"bar): every embedding cosine below **{algebra['worst_case_e_band']}** turns an "
        "accepted concept into a rejected one. That is not a corner: cosines in the low tenths "
        "are exactly what a broad-recall retrieval stage produces for a marginal candidate.",
        "",
        "## 2. Minimal cases (through the real `_combine_score`)",
        "",
        "| case | embedding | label | combined | accepted at 0.5 |",
        "|---|---|---|---|---|",
    ]
    for row in cases:
        lines.append(
            f"| {row['case']} | {row['embedding']} | {row['label']} | {row['combined']} | "
            f"{'yes' if row['accepted'] else '**no**'} |"
        )
    lines += [
        "",
        "## 3. End to end (through the real `resolve_concepts`)",
        "",
        f"One concept, one query (`\"{E2E_QUERY}\"` → *{E2E_LABEL}*, label score 0.736), four "
        "embedding stages that differ only in how strongly they retrieve it:",
        "",
        "| case | embedding | concepts resolved | confidence |",
        "|---|---|---|---|",
    ]
    for row in e2e:
        lines.append(
            f"| {row['case']} | {row['embedding']} | {row['resolved']} | {row['confidence']} |"
        )
    lines += [
        "",
        "A retrieval stage that finds the right concept — weakly — makes the system return "
        "**less** than a retrieval stage that finds nothing at all.",
        "",
        "## 4. Remedies",
        "",
        "| rule | evidence-monotone | worst drop | stage-monotone | bounded | label-only exact | both-stages exact |",
        "|---|---|---|---|---|---|---|",
    ]
    for rule in RULES:
        inv = invariants(rule)
        lines.append(
            f"| `{rule}` | {'yes' if inv['evidence_monotone'] else '**no**'} | "
            f"{inv['worst_evidence_drop']} | {'yes' if inv['stage_monotone'] else '**no**'} | "
            f"{'yes' if inv['bounded'] else 'no'} | {inv['exact_label_only']} | "
            f"{inv['exact_both_stages']} |"
        )
    lines += [
        "",
        "*evidence-monotone* = adding a stage never lowers the score. It is the property the "
        "status quo lacks, and the only one that matters for this defect; the others are there "
        "to show what a remedy costs elsewhere.",
        "",
        "### Corpus effect",
        "",
        "`presence` is also shown at a threshold rescaled to its axis (label-only exact tops out "
        "at 0.297, so 0.5 is meaningless for it); every other rule keeps the confidence scale.",
        "",
        "| operating point | rule | candidates rescored | in inversion region | F1 healthy | F1 degraded | flips + | flips − | order moves | canaries |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    arms = (
        [("production 0.7 / 0.5", rule, REF_PENALTY, REF_THRESHOLD) for rule in RULES]
        + [("production, rescaled", "presence", REF_PENALTY, 0.20)]
        + [("recommended 0.85 / 0.55", rule, 0.85, 0.55) for rule in RULES]
        + [("recommended, rescaled", "presence", 0.85, 0.22)]
    )
    for point, rule, p, t in arms:
        eff = corpus_effect(rule, p, t)
        lines.append(
            f"| {point} | `{rule}` | {eff['candidates_rescored']} | "
            f"{eff['candidates_in_inversion_region']} | {eff['f1_healthy']} | "
            f"{eff['f1_degraded']} | {eff['flips_accept']} | {eff['flips_reject']} | "
            f"{eff['order_changes']} | {'green' if eff['canaries_green'] else 'FAIL'} |"
        )

    CAPTURES_DIR.mkdir(parents=True, exist_ok=True)
    (CAPTURES_DIR / "combine-lab.md").write_text("\n".join(lines) + "\n")

    # The lab is also a characterization test: if the status quo ever stops inverting, this
    # whole document is stale and should be rewritten rather than quietly kept.
    status_quo = invariants("current")
    if status_quo["evidence_monotone"]:
        print("UNEXPECTED: _combine_score is now evidence-monotone; this analysis is stale")
        return 1
    print(f"wrote {CAPTURES_DIR / 'combine-lab.md'}")
    print(f"  status quo inverts by up to {status_quo['worst_evidence_drop']} of confidence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
