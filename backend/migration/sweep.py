#!/usr/bin/env python3
"""Operating-point sweep for the alea-intake concept-resolution cascade.

**This is a STUDY tool. It changes nothing.** It reads ``migration/corpus.json`` (the same
synthetic corpus the migration harness uses) plus ``migration/sweep_gold.json`` (concept-level
labels owned by this study), then measures what *would* happen at other operating points:

* ``SINGLE_STAGE_PENALTY``   — ``concept_resolver.SINGLE_STAGE_PENALTY`` (production: 0.7)
* ``confidence_threshold``   — ``ConceptResolutionConfig.confidence_threshold`` (production: 0.5)
* ``specificity_penalty``    — folio-resolve ≥ 0.3.0's optional scorer knob (production: 1.0,
                               i.e. the call site does not pass it at all)
* the **combine rule** itself — the status quo weighted average and three candidate remedies
  for the "a weak embedding hit is worse than no embedding hit" inversion recorded in
  ``migration/README.md``

Same rules as ``harness.py``: ``PYTHONHASHSEED=0``, $0 LLM spend, no network, no database, no
ontology download. Nothing under ``app/`` is edited; the penalty is swept by setting the module
attribute **inside this process only**, and the specificity knob by wrapping the scorer at the
resolver's call site, also in-process. ``verify_reference()`` proves the reconstruction is
faithful before any of that happens.

Why a reconstruction instead of N full ``resolve_concepts`` runs: neither knob can change which
candidates the two stages *retrieve* or what they *score* — ``SINGLE_STAGE_PENALTY`` and
``confidence_threshold`` are consumed strictly downstream, in ``_combine_and_rank``. So the
candidate pool is built once per (specificity, embedding-mode) pair through the real stage
functions, and every grid point is then evaluated over that pool using the real
``_combine_score``. ``--verify`` re-runs the true ``resolve_concepts`` at the reference point and
asserts equality, which is what makes the shortcut legitimate.

Usage::

    .venv/bin/python migration/sweep.py                 # full sweep -> captures/sweep.json + .md
    .venv/bin/python migration/sweep.py --no-spec-axis  # skip the folio-resolve >= 0.3.0 axis
    .venv/bin/python migration/sweep.py --verify        # fidelity check only
"""

from __future__ import annotations

import argparse
import asyncio
import functools
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

# Same determinism pin as harness.py: folio-resolve iterates sets internally, so tie-breaks
# among equally scored candidates move between processes under PEP 456 hash randomization.
if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execv(sys.executable, [sys.executable, *sys.argv])

MIGRATION = Path(__file__).resolve().parent
BACKEND = MIGRATION.parent
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(MIGRATION))

import logging  # noqa: E402

logging.disable(logging.CRITICAL)

CORPUS_PATH = MIGRATION / "corpus.json"
GOLD_PATH = MIGRATION / "sweep_gold.json"
CAPTURES_DIR = MIGRATION / "captures"

# The sibling folio-resolve checkout, if one exists next to this repo. Used ONLY to read the
# optional ``specificity_penalty`` knob added in v0.3.0; the committed pin
# (``folio-resolve>=0.1.0``) and the installed wheel are never touched.
LOCAL_LIBRARY_SRC = BACKEND.parent.parent / "folio-resolve" / "src"

# --- the grid -------------------------------------------------------------
PENALTY_GRID = (0.5, 0.6, 0.7, 0.8, 0.9, 1.0)
THRESHOLD_GRID = (0.35, 0.40, 0.45, 0.50, 0.55, 0.60)
# Second pass around the region the coarse grid points at.
REFINE_PENALTY_GRID = (0.75, 0.80, 0.85, 0.90)
REFINE_THRESHOLD_GRID = (0.50, 0.525, 0.55, 0.575, 0.60)
SPEC_GRID = (0.0, 0.3, 0.5, 0.7, 1.0)
COMBINE_RULES = ("current", "floor", "presence", "coverage")

REF_PENALTY = 0.7
REF_THRESHOLD = 0.5
REF_SPEC = 1.0
REF_RULE = "current"

# Narrative-category semantics, mirrored from compare.py so the canaries mean the same thing.
RECALL_SENSITIVE = {"exact", "word_order", "expansion", "sub_phrase", "compound", "prefix"}
MUST_BE_EMPTY = {"stopword_only", "empty", "nonsense"}

MAX_EMBEDDING_CANDIDATES = 20
MAX_LABEL_RESULTS = 10


def _corpus() -> dict[str, Any]:
    return json.loads(CORPUS_PATH.read_text())


def _gold() -> dict[str, Any]:
    return json.loads(GOLD_PATH.read_text())


# ---------------------------------------------------------------------------
# Candidate pools (built through the real stage functions)
# ---------------------------------------------------------------------------


def _spec_patch(spec: float | None):
    """Wrap the resolver's scorer so it forwards ``specificity_penalty``.

    ``None`` means "leave the call site exactly as production has it" — no kwarg at all, which
    is also what folio-resolve 0.1.0 (the currently pinned wheel) supports. A float requires a
    library that accepts the keyword; ``spec_axis_available()`` checks that first.
    """
    from app.services.folio import concept_resolver as cr

    if spec is None:
        return lambda: None
    original = cr.compute_relevance_score
    cr.compute_relevance_score = functools.partial(original, specificity_penalty=spec)
    return lambda: setattr(cr, "compute_relevance_score", original)


async def _pool_for(text: str, folio, embedding, config) -> dict[str, dict]:
    from app.services.folio import concept_resolver as cr

    candidates: dict[str, dict] = {}
    if not text or not text.strip() or cr._is_stopword_only(text):
        return candidates
    expanded = cr.expand_legal_terms(text)
    try:
        await cr._stage_embedding(text, expanded, embedding, config, candidates)
    except Exception:
        pass  # BUG-9 cascade: the label stage carries on
    await cr._stage_label_prefix(text, expanded, folio, config, candidates)
    return candidates


def build_pools(
    corpus: dict, spec: float | None, *, expansions: bool = True
) -> dict[str, dict[str, dict[str, dict]]]:
    """Retrieve + score every candidate once per embedding mode.

    Returns ``{mode: {narrative_id: {iri: {label, embedding_score, label_score}}}}``.

    ``expansions=False`` runs the same two stages with alea's lay-language query expansion
    switched off. That is not a proposal — it is the ablation that answers "is this false
    positive the operating point's fault or the expansion vocabulary's?".
    """
    import harness
    from app.services.folio import concept_resolver as cr
    from app.services.folio.concept_resolver import ConceptResolutionConfig

    undo = _spec_patch(spec)
    saved_expand = cr.expand_legal_terms
    if not expansions:
        cr.expand_legal_terms = lambda text: []
    try:
        config = ConceptResolutionConfig(
            max_embedding_candidates=MAX_EMBEDDING_CANDIDATES,
            max_label_results=MAX_LABEL_RESULTS,
            enable_llm_stage=False,
        )
        pools: dict[str, dict[str, dict[str, dict]]] = {}
        for mode, fails in (("healthy", False), ("degraded", True)):
            folio = harness._FakeFOLIO(corpus["ontology"])
            embedding = harness._FakeEmbeddingService(corpus["ontology"], fail=fails)
            per_narrative: dict[str, dict[str, dict]] = {}
            for item in corpus["narratives"]:
                cands = asyncio.run(_pool_for(item["text"], folio, embedding, config))
                per_narrative[item["id"]] = {
                    iri: {
                        "label": d.get("label", ""),
                        "embedding_score": d.get("embedding_score"),
                        "label_score": d.get("label_score"),
                    }
                    for iri, d in cands.items()
                }
            pools[mode] = per_narrative
        return pools
    finally:
        cr.expand_legal_terms = saved_expand
        undo()


# ---------------------------------------------------------------------------
# Combine rules — the status quo plus the candidate remedies (STUDY ONLY)
# ---------------------------------------------------------------------------

EMBEDDING_WEIGHT = 0.3
LABEL_WEIGHT = 0.3
LLM_WEIGHT = 0.4


def combined_score(
    embedding_score: float | None,
    label_score: float | None,
    llm_score: float | None,
    *,
    penalty: float,
    rule: str = "current",
) -> float:
    """Score one candidate under ``rule``.

    ``current`` delegates to the production ``_combine_score`` with the module's penalty
    constant temporarily set to ``penalty`` — so the status quo arm of every sweep is the real
    function, not a lookalike. The remedies are implemented here and here only.

    * ``current``   — weighted average over the stages that fired; ×penalty if only one did.
    * ``floor``     — *penalty-then-floor*: ``max(current, penalty × best single stage)``. A
                      candidate can never score below what its strongest stage alone would give
                      it, so a weak corroborating hit can no longer demote it.
    * ``presence``  — *presence-weighted average*: missing stages contribute 0 over the FULL
                      weight, ``0.3e + 0.3l + 0.4llm``. Strictly evidence-monotone, but it
                      rescales the whole confidence axis (label-only tops out at 0.297).
    * ``coverage``  — *graded penalty*: weighted average over present stages ×
                      ``penalty ** (missing_weight / total_weight)`` — the smooth
                      generalization of the flat single-stage penalty. Included because the
                      obvious generalization does NOT fix the inversion; see the study doc.
    """
    from app.services.folio import concept_resolver as cr

    if rule == "current":
        saved = cr.SINGLE_STAGE_PENALTY
        cr.SINGLE_STAGE_PENALTY = penalty
        try:
            return cr._combine_score(
                embedding_score=embedding_score,
                label_score=label_score,
                llm_score=llm_score,
            )
        finally:
            cr.SINGLE_STAGE_PENALTY = saved

    stages = [
        (s, w)
        for s, w in (
            (embedding_score, EMBEDDING_WEIGHT),
            (label_score, LABEL_WEIGHT),
            (llm_score, LLM_WEIGHT),
        )
        if s is not None
    ]
    if not stages:
        return 0.0
    present_weight = sum(w for _, w in stages)
    total_weight = EMBEDDING_WEIGHT + LABEL_WEIGHT + LLM_WEIGHT
    avg = sum(s * w for s, w in stages) / present_weight

    if rule == "floor":
        base = avg * penalty if len(stages) == 1 else avg
        return max(base, penalty * max(s for s, _ in stages))
    if rule == "presence":
        return sum(s * w for s, w in stages) / total_weight
    if rule == "coverage":
        missing_fraction = (total_weight - present_weight) / total_weight
        return avg * (penalty**missing_fraction)
    raise ValueError(f"unknown combine rule: {rule!r}")


# ---------------------------------------------------------------------------
# Evaluation of one operating point
# ---------------------------------------------------------------------------


def evaluate_point(
    pools: dict[str, dict[str, dict[str, dict]]],
    *,
    penalty: float,
    threshold: float,
    rule: str = "current",
) -> dict[str, dict[str, list[tuple[str, float]]]]:
    """Accepted concepts per mode/narrative, ranked exactly as ``_combine_and_rank`` ranks."""
    out: dict[str, dict[str, list[tuple[str, float]]]] = {}
    for mode, per_narrative in pools.items():
        accepted: dict[str, list[tuple[str, float]]] = {}
        for nid, cands in per_narrative.items():
            rows: list[tuple[str, float]] = []
            for iri, d in cands.items():
                score = combined_score(
                    d.get("embedding_score"),
                    d.get("label_score"),
                    d.get("llm_score"),
                    penalty=penalty,
                    rule=rule,
                )
                if score >= threshold:
                    rows.append((iri, round(score, 4)))
            # Production sorts by confidence descending; IRI is the harness's stable tie-break.
            rows.sort(key=lambda r: (-r[1], r[0]))
            accepted[nid] = rows
        out[mode] = accepted
    return out


def score_point(
    accepted: dict[str, dict[str, list[tuple[str, float]]]],
    gold: dict[str, Any],
    reference: dict[str, dict[str, list[tuple[str, float]]]] | None,
    corpus: dict,
    *,
    detail: bool = False,
) -> dict[str, Any]:
    """Precision/recall against the concept-level gold, flips + rank moves vs the reference.

    ``detail`` keeps the per-concept row lists (which concepts were missed, which flipped).
    They are what makes a recommendation auditable, and they are also ~10 KB per grid point —
    so the coarse arms of the sweep keep counts only and the arms a human actually reads
    (reference, refinement pass, ablation) keep everything.
    """
    categories = {n["id"]: n["category"] for n in corpus["narratives"]}
    labels = gold["narratives"]
    result: dict[str, Any] = {}

    for mode, per_narrative in accepted.items():
        tp = fp = fn = ambiguous_accepted = 0
        missed: list[dict] = []
        false_positives: list[dict] = []
        for nid, rows in per_narrative.items():
            # Closed world: the mini-ontology is 41 hand-written nodes, so every narrative's
            # correct mappings can be enumerated. Anything accepted that is neither ``good``
            # nor explicitly ``ambiguous`` is a false positive — including branch roots and the
            # sandbox placeholder, which are never a valid resolution for anything.
            good = set(labels.get(nid, {}).get("good", []))
            ambiguous = set(labels.get(nid, {}).get("ambiguous", []))
            got = {iri for iri, _ in rows}
            bad = got - good - ambiguous
            tp += len(got & good)
            fp += len(bad)
            fn += len(good - got)
            ambiguous_accepted += len(got & ambiguous)
            missed += [{"narrative": nid, "iri": i} for i in sorted(good - got)]
            false_positives += [{"narrative": nid, "iri": i} for i in sorted(bad)]
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        result[mode] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "ambiguous_accepted": ambiguous_accepted,
            "accepted_total": sum(len(r) for r in per_narrative.values()),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        }
        if detail:
            result[mode]["missed"] = missed
            result[mode]["false_positives"] = false_positives

        if reference is not None:
            ref = reference[mode]
            gained = lost = top1 = order = 0
            gained_rows: list[dict] = []
            lost_rows: list[dict] = []
            for nid, rows in per_narrative.items():
                got = {iri for iri, _ in rows}
                was = {iri for iri, _ in ref.get(nid, [])}
                gained += len(got - was)
                lost += len(was - got)
                gained_rows += [{"narrative": nid, "iri": i} for i in sorted(got - was)]
                lost_rows += [{"narrative": nid, "iri": i} for i in sorted(was - got)]
                a = rows[0][0] if rows else None
                b = ref.get(nid, [{}])[0][0] if ref.get(nid) else None
                if a != b:
                    top1 += 1
                if [i for i, _ in rows] != [i for i, _ in ref.get(nid, [])]:
                    order += 1
            result[mode].update(
                {
                    "flips_accept": gained,
                    "flips_reject": lost,
                    "top1_changes": top1,
                    "order_changes": order,
                }
            )
            if detail:
                result[mode]["flips_accept_rows"] = gained_rows
                result[mode]["flips_reject_rows"] = lost_rows

    # Canaries. PLACE-REJECTED lives in the claim-fitness seam, which neither knob touches, so
    # it is asserted once (in verify_reference) rather than per grid point.
    failures: list[str] = []
    healthy = accepted["healthy"]
    degraded = accepted["degraded"]
    ref_healthy = (reference or {}).get("healthy", {})
    ref_degraded = (reference or {}).get("degraded", {})
    for nid, rows in healthy.items():
        cat = categories.get(nid, "")
        if cat in MUST_BE_EMPTY and rows:
            failures.append(f"EMPTY-STAYS-EMPTY: {nid} resolved {len(rows)} concept(s)")
        if cat == "place" and not rows and ref_healthy.get(nid):
            failures.append(f"PLACES-RESOLVABLE: {nid} lost every concept")
        if cat in RECALL_SENSITIVE and not rows and ref_healthy.get(nid):
            failures.append(f"NO-RECALL-LOSS: {nid} fell to zero concepts")
    for nid, rows in degraded.items():
        if categories.get(nid) in RECALL_SENSITIVE and not rows and ref_degraded.get(nid):
            failures.append(f"EMBED-DEGRADE: {nid} resolved nothing with embeddings down")

    result["canary_failures"] = failures
    result["canaries_green"] = not failures
    result["f1_mean"] = round((result["healthy"]["f1"] + result["degraded"]["f1"]) / 2, 4)
    return result


def event_tables(pools: dict, gold: dict) -> dict[str, list[dict]]:
    """The two bars, as ordered lists of the decisions they make.

    The accept test factorizes. A candidate found by ONE stage clears the bar iff
    ``score ≥ threshold / penalty`` — call that the **solo bar**; a candidate found by two
    stages clears it iff their weighted average ``≥ threshold`` — the **corroborated bar**.
    So the whole operating point is two numbers, and each one is fully described by the
    ordered list of concepts it lets in or keeps out. This is that list, tagged with the gold
    judgment, which is what makes a recommendation auditable rather than an F1 beauty contest.
    """
    labels = gold["narratives"]

    def _tag(nid: str, iri: str) -> str:
        spec = labels.get(nid, {})
        if iri in spec.get("good", []):
            return "good"
        if iri in spec.get("ambiguous", []):
            return "ambiguous"
        return "bad"

    solo: list[dict] = []
    corroborated: list[dict] = []
    for mode, per_narrative in pools.items():
        for nid, cands in per_narrative.items():
            for iri, d in cands.items():
                e, lab = d.get("embedding_score"), d.get("label_score")
                present = [s for s in (e, lab) if s is not None]
                if len(present) == 1:
                    solo.append(
                        {
                            "mode": mode,
                            "narrative": nid,
                            "iri": iri,
                            "label": d["label"],
                            "score": round(present[0], 4),
                            "gold": _tag(nid, iri),
                        }
                    )
                elif len(present) == 2:
                    corroborated.append(
                        {
                            "mode": mode,
                            "narrative": nid,
                            "iri": iri,
                            "label": d["label"],
                            "score": round((e + lab) / 2, 4),
                            "gold": _tag(nid, iri),
                        }
                    )
    solo.sort(key=lambda r: (-r["score"], r["narrative"], r["iri"]))
    corroborated.sort(key=lambda r: (-r["score"], r["narrative"], r["iri"]))
    return {"solo": solo, "corroborated": corroborated}


# ---------------------------------------------------------------------------
# Fidelity: the reconstruction must equal the real resolver
# ---------------------------------------------------------------------------


def verify_reference(corpus: dict, pools: dict) -> list[str]:
    """Assert the pool reconstruction reproduces ``resolve_concepts`` at the reference point.

    Also re-asserts the claim-fitness canary (PLACE-REJECTED), which the sweep knobs cannot
    move but which must be shown green for the study to mean anything.
    """
    import harness
    from app.services.analysis.semantic_fit import FitItem, SemanticFitValidator
    from app.services.folio.concept_resolver import ConceptResolutionConfig, resolve_concepts

    problems: list[str] = []
    reconstructed = evaluate_point(
        pools, penalty=REF_PENALTY, threshold=REF_THRESHOLD, rule=REF_RULE
    )
    config = ConceptResolutionConfig(
        max_embedding_candidates=MAX_EMBEDDING_CANDIDATES,
        max_label_results=MAX_LABEL_RESULTS,
        confidence_threshold=REF_THRESHOLD,
        enable_llm_stage=False,
    )
    for mode, fails in (("healthy", False), ("degraded", True)):
        folio = harness._FakeFOLIO(corpus["ontology"])
        embedding = harness._FakeEmbeddingService(corpus["ontology"], fail=fails)
        for item in corpus["narratives"]:
            real = asyncio.run(
                resolve_concepts(
                    text=item["text"],
                    folio=folio,
                    embedding_service=embedding,
                    config=config,
                    llm_model=None,
                )
            )
            real_rows = sorted((r.iri, r.confidence) for r in real)
            recon_rows = sorted(reconstructed[mode][item["id"]])
            if real_rows != recon_rows:
                problems.append(
                    f"FIDELITY {mode}/{item['id']}: real={real_rows} reconstructed={recon_rows}"
                )

    validator = SemanticFitValidator(llm_service=None)
    verdicts = validator.apply_deterministic(
        [
            FitItem(
                key=row["id"],
                claim_name=row["claim_name"],
                concept_label=row["label"],
                branch=row["branch"] or "",
                confidence=row["confidence"],
            )
            for row in corpus["fit"]
        ]
    )
    for row in corpus["fit"]:
        rejected = verdicts.get(row["id"]) is not None
        if rejected != row["expect_reject"]:
            problems.append(
                f"PLACE-REJECTED {row['id']}: rejected={rejected} expected={row['expect_reject']}"
            )
    return problems


# ---------------------------------------------------------------------------
# The specificity axis (folio-resolve >= 0.3.0 only)
# ---------------------------------------------------------------------------


def spec_axis_available() -> tuple[bool, str]:
    """Is a library that accepts ``specificity_penalty`` importable WITHOUT moving the pin?

    The committed dependency is ``folio-resolve>=0.1.0``; the installed wheel is whatever the
    lock resolved. If the installed one already takes the keyword, use it in-process. Otherwise
    fall back to the sibling source checkout, which the pin already permits (it is a >= range)
    and which this sweep only ever reads.
    """
    import inspect

    import folio_resolve

    if "specificity_penalty" in inspect.signature(folio_resolve.compute_relevance_score).parameters:
        return True, f"installed folio-resolve {folio_resolve.__version__}"
    if (LOCAL_LIBRARY_SRC / "folio_resolve" / "scoring.py").exists():
        text = (LOCAL_LIBRARY_SRC / "folio_resolve" / "scoring.py").read_text()
        if "specificity_penalty" in text:
            return True, f"sibling checkout at {LOCAL_LIBRARY_SRC}"
    return False, (
        f"installed folio-resolve {folio_resolve.__version__} has no specificity_penalty "
        "and no sibling checkout provides one"
    )


def pools_via_subprocess(spec: float) -> dict:
    """Build a pool under the sibling checkout, in a child process with PYTHONPATH set.

    Keeps the parent process on the *installed*, pinned library — the sweep's main grid and the
    fidelity check must run against exactly what production imports.
    """
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = "0"
    env["PYTHONPATH"] = os.pathsep.join(
        [str(LOCAL_LIBRARY_SRC), env.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)
    out = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--dump-pools", "--spec", str(spec)],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return json.loads(out.stdout)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def _grid_table(rows: list[dict], key: str, title: str) -> list[str]:
    lines = [f"**{title}**", "", "| penalty \\ threshold | " + " | ".join(
        f"{t:.2f}" for t in THRESHOLD_GRID) + " |",
        "|---" * (len(THRESHOLD_GRID) + 1) + "|"]
    for p in PENALTY_GRID:
        cells = []
        for t in THRESHOLD_GRID:
            row = next(r for r in rows if r["penalty"] == p and r["threshold"] == t)
            value = row
            for part in key.split("."):
                value = value[part]
            mark = "" if row["metrics"]["canaries_green"] else " ⚠"
            cells.append(f"{value}{mark}")
        lines.append(f"| **{p:.1f}** | " + " | ".join(cells) + " |")
    lines.append("")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="sweep", help="capture stem under migration/captures/")
    parser.add_argument("--verify", action="store_true", help="fidelity check only")
    parser.add_argument("--no-spec-axis", action="store_true")
    parser.add_argument("--dump-pools", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--spec", type=float, default=None, help=argparse.SUPPRESS)
    args = parser.parse_args()

    corpus = _corpus()

    if args.dump_pools:  # child-process mode for the specificity axis
        print(json.dumps(build_pools(corpus, args.spec)))
        return 0

    gold = _gold()
    pools = build_pools(corpus, None)

    problems = verify_reference(corpus, pools)
    if problems:
        for p in problems:
            print(f"FATAL: {p}")
        return 2
    print("fidelity: reconstruction == resolve_concepts at the reference point ✅")
    print("canary PLACE-REJECTED (knob-independent, claim-fitness seam) ✅")
    if args.verify:
        return 0

    reference = evaluate_point(
        pools, penalty=REF_PENALTY, threshold=REF_THRESHOLD, rule=REF_RULE
    )
    ref_metrics = score_point(reference, gold, reference, corpus, detail=True)

    # --- main grid: penalty x threshold, status-quo combine, production scorer ---
    grid: list[dict] = []
    for p in PENALTY_GRID:
        for t in THRESHOLD_GRID:
            accepted = evaluate_point(pools, penalty=p, threshold=t, rule=REF_RULE)
            grid.append(
                {
                    "penalty": p,
                    "threshold": t,
                    "rule": REF_RULE,
                    "metrics": score_point(accepted, gold, reference, corpus),
                }
            )

    # --- refinement pass around the region the coarse grid points at ---
    refine: list[dict] = []
    for p in REFINE_PENALTY_GRID:
        for t in REFINE_THRESHOLD_GRID:
            accepted = evaluate_point(pools, penalty=p, threshold=t, rule=REF_RULE)
            refine.append(
                {
                    "penalty": p,
                    "threshold": t,
                    "solo_bar": round(t / p, 4),
                    "rule": REF_RULE,
                    "metrics": score_point(accepted, gold, reference, corpus, detail=True),
                }
            )

    # --- combine-rule arm: every rule over the same grid ---
    rule_grid: list[dict] = []
    for rule in COMBINE_RULES:
        for p in PENALTY_GRID:
            for t in THRESHOLD_GRID:
                accepted = evaluate_point(pools, penalty=p, threshold=t, rule=rule)
                rule_grid.append(
                    {
                        "penalty": p,
                        "threshold": t,
                        "rule": rule,
                        "metrics": score_point(accepted, gold, reference, corpus),
                    }
                )
    # The presence rule rescales the axis, so it also gets a threshold range of its own.
    presence_grid: list[dict] = []
    for t in (0.15, 0.20, 0.25, 0.30, 0.35, 0.40):
        accepted = evaluate_point(pools, penalty=REF_PENALTY, threshold=t, rule="presence")
        presence_grid.append(
            {
                "penalty": REF_PENALTY,
                "threshold": t,
                "rule": "presence",
                "metrics": score_point(accepted, gold, reference, corpus),
            }
        )

    # --- ablation: how much of the residual error is the operating point's at all? ---
    ablation_pools = build_pools(corpus, None, expansions=False)
    ablation: list[dict] = []
    for name, p, t in (("production", REF_PENALTY, REF_THRESHOLD), ("recommended", 0.85, 0.55)):
        for expand, pool in (("on", pools), ("off", ablation_pools)):
            accepted = evaluate_point(pool, penalty=p, threshold=t, rule=REF_RULE)
            ablation.append(
                {
                    "point": name,
                    "expansions": expand,
                    "penalty": p,
                    "threshold": t,
                    "metrics": score_point(accepted, gold, reference, corpus, detail=True),
                }
            )

    # --- specificity axis ---
    spec_rows: list[dict] = []
    spec_note = ""
    spec_identity = None
    if not args.no_spec_axis:
        available, why = spec_axis_available()
        spec_note = why
        if available:
            spec_pools = {s: pools_via_subprocess(s) for s in SPEC_GRID}
            # Bit-identity guard: at specificity_penalty=1.0 the library must reproduce the
            # pinned wheel exactly, or the axis is confounded by other version differences.
            spec_identity = spec_pools[1.0] == pools
            # Run the axis at the production penalty AND at the refinement pass's, so the
            # question "does damping the scorer's specificity penalty still buy anything once
            # the two bars have moved?" gets an answer rather than an extrapolation.
            for s in SPEC_GRID:
                for p in (REF_PENALTY, 0.85):
                    for t in THRESHOLD_GRID:
                        accepted = evaluate_point(
                            spec_pools[s], penalty=p, threshold=t, rule=REF_RULE
                        )
                        spec_rows.append(
                            {
                                "specificity_penalty": s,
                                "penalty": p,
                                "threshold": t,
                                "rule": REF_RULE,
                                "metrics": score_point(accepted, gold, reference, corpus),
                            }
                        )
        else:
            spec_note = f"SKIPPED — {why}"

    payload = {
        "reference": {
            "penalty": REF_PENALTY,
            "threshold": REF_THRESHOLD,
            "specificity_penalty": REF_SPEC,
            "rule": REF_RULE,
            "metrics": ref_metrics,
        },
        "grid": grid,
        "refine": refine,
        "events": event_tables(pools, gold),
        "expansion_ablation": ablation,
        "rule_grid": rule_grid,
        "presence_grid": presence_grid,
        "spec_axis": {
            "note": spec_note,
            "bit_identical_at_1.0": spec_identity,
            "rows": spec_rows,
        },
    }
    CAPTURES_DIR.mkdir(parents=True, exist_ok=True)
    (CAPTURES_DIR / f"{args.out}.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    # --- markdown tables (pasted into CALIBRATION-STUDY-*.md) ---
    lines = [
        "# Operating-point sweep — raw tables",
        "",
        f"Reference (production): penalty **{REF_PENALTY}**, threshold **{REF_THRESHOLD}**, "
        f"specificity **{REF_SPEC}**, rule **{REF_RULE}**.",
        "",
        f"- healthy: P {ref_metrics['healthy']['precision']} / R {ref_metrics['healthy']['recall']}"
        f" / F1 {ref_metrics['healthy']['f1']}",
        f"- degraded: P {ref_metrics['degraded']['precision']} / R "
        f"{ref_metrics['degraded']['recall']} / F1 {ref_metrics['degraded']['f1']}",
        "",
    ]
    lines += _grid_table(grid, "metrics.f1_mean", "Mean F1 (healthy, degraded) — status-quo combine")
    lines += _grid_table(grid, "metrics.healthy.f1", "F1, embeddings healthy")
    lines += _grid_table(grid, "metrics.degraded.f1", "F1, embeddings down (BUG-9 cascade)")
    lines += _grid_table(grid, "metrics.healthy.precision", "Precision, embeddings healthy")
    lines += _grid_table(grid, "metrics.healthy.recall", "Recall, embeddings healthy")
    lines += _grid_table(grid, "metrics.degraded.flips_accept", "Accept flips vs reference (degraded)")
    lines += _grid_table(grid, "metrics.degraded.flips_reject", "Reject flips vs reference (degraded)")

    lines += ["", "## Refinement pass", "",
              "| penalty | threshold | solo bar (t/p) | F1 healthy | F1 degraded | mean F1 | "
              "P healthy | P degraded | flips + | flips − | canaries |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
    for row in refine:
        m = row["metrics"]
        lines.append(
            f"| {row['penalty']} | {row['threshold']} | {row['solo_bar']} | {m['healthy']['f1']} | "
            f"{m['degraded']['f1']} | {m['f1_mean']} | {m['healthy']['precision']} | "
            f"{m['degraded']['precision']} | "
            f"{m['healthy']['flips_accept'] + m['degraded']['flips_accept']} | "
            f"{m['healthy']['flips_reject'] + m['degraded']['flips_reject']} | "
            f"{'green' if m['canaries_green'] else 'FAIL'} |"
        )

    events = payload["events"]
    lines += ["", "## What each bar decides", "",
              "The accept test factorizes: a one-stage candidate needs `score ≥ threshold / "
              "penalty` (**solo bar**), a two-stage candidate needs `mean(stages) ≥ threshold` "
              "(**corroborated bar**). Every candidate within ±0.15 of the production bars, "
              "tagged with the study's gold judgment:", ""]
    lines += ["### Solo bar (production: 0.5 / 0.7 = 0.7143)", "",
              "| score | gold | narrative | concept | mode |", "|---|---|---|---|---|"]
    for row in events["solo"]:
        if 0.55 <= row["score"] <= 0.90:
            lines.append(
                f"| {row['score']} | {row['gold']} | {row['narrative']} | {row['label']} | "
                f"{row['mode']} |"
            )
    lines += ["", "### Corroborated bar (production: 0.50)", "",
              "| score | gold | narrative | concept | mode |", "|---|---|---|---|---|"]
    for row in events["corroborated"]:
        if 0.40 <= row["score"] <= 0.65:
            lines.append(
                f"| {row['score']} | {row['gold']} | {row['narrative']} | {row['label']} | "
                f"{row['mode']} |"
            )

    lines += ["", "## Ablation — is the residual error even the operating point's to fix?", "",
              "The same two operating points, with alea's lay-language query expansion on and "
              "off. Expansion is a *recall* device; this measures what it costs in precision.",
              "",
              "| point | expansions | P healthy | R healthy | F1 healthy | P degraded | R degraded | F1 degraded |",
              "|---|---|---|---|---|---|---|---|"]
    for row in ablation:
        m = row["metrics"]
        lines.append(
            f"| {row['point']} ({row['penalty']}/{row['threshold']}) | {row['expansions']} | "
            f"{m['healthy']['precision']} | {m['healthy']['recall']} | {m['healthy']['f1']} | "
            f"{m['degraded']['precision']} | {m['degraded']['recall']} | {m['degraded']['f1']} |"
        )

    lines += ["", "## Combine rules", "",
              "| rule | penalty | threshold | F1 healthy | F1 degraded | mean F1 | flips + | flips − | canaries |",
              "|---|---|---|---|---|---|---|---|---|"]
    for row in rule_grid + presence_grid:
        m = row["metrics"]
        lines.append(
            f"| {row['rule']} | {row['penalty']} | {row['threshold']} | {m['healthy']['f1']} | "
            f"{m['degraded']['f1']} | {m['f1_mean']} | "
            f"{m['healthy']['flips_accept'] + m['degraded']['flips_accept']} | "
            f"{m['healthy']['flips_reject'] + m['degraded']['flips_reject']} | "
            f"{'green' if m['canaries_green'] else 'FAIL'} |"
        )

    if spec_rows:
        lines += ["", "## Specificity axis", "", f"_{spec_note}; "
                  f"bit-identical to the pinned wheel at 1.0: {spec_identity}_", "",
                  "| specificity | penalty | threshold | F1 healthy | F1 degraded | mean F1 | flips + | flips − |",
                  "|---|---|---|---|---|---|---|---|"]
        for row in spec_rows:
            m = row["metrics"]
            lines.append(
                f"| {row['specificity_penalty']} | {row['penalty']} | {row['threshold']} | {m['healthy']['f1']} | "
                f"{m['degraded']['f1']} | {m['f1_mean']} | "
                f"{m['healthy']['flips_accept'] + m['degraded']['flips_accept']} | "
                f"{m['healthy']['flips_reject'] + m['degraded']['flips_reject']} |"
            )
    elif spec_note:
        lines += ["", "## Specificity axis", "", f"_{spec_note}_"]

    (CAPTURES_DIR / f"{args.out}-tables.md").write_text("\n".join(lines) + "\n")

    best = max(grid, key=lambda r: (r["metrics"]["canaries_green"], r["metrics"]["f1_mean"]))
    print(f"grid points: {len(grid)} (+{len(rule_grid)} rule, +{len(spec_rows)} specificity)")
    print(
        f"reference   mean F1 {ref_metrics['f1_mean']} "
        f"(healthy {ref_metrics['healthy']['f1']}, degraded {ref_metrics['degraded']['f1']})"
    )
    print(
        f"best (p,t)  penalty={best['penalty']} threshold={best['threshold']} "
        f"mean F1 {best['metrics']['f1_mean']}"
    )
    print(f"wrote {CAPTURES_DIR / (args.out + '.json')} and {args.out}-tables.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
