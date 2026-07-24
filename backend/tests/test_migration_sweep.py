"""Guards for the operating-point calibration study (``backend/migration/sweep.py``).

The study's whole claim to being evidence is that (a) its reconstruction of the resolver is
faithful, (b) it measures the *production* combine function rather than a lookalike, and
(c) it changes nothing. These tests assert all three, plus the integrity of the hand-written
gold labels the recommendation rests on.

They are tests OF THE HARNESS. Nothing here exercises ``app/`` behavior that the rest of the
suite does not already cover — see ``test_concept_resolver.py`` and ``test_folio_resolve_pin.py``
for that.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

MIGRATION = Path(__file__).resolve().parent.parent / "migration"

# ``sweep.py`` and ``combine_lab.py`` re-exec themselves under ``PYTHONHASHSEED=0`` when run as
# scripts (the migration harness's determinism pin). Setting the variable before import silences
# that guard so importing them here cannot restart the pytest process. Every assertion below is
# hash-order independent: stage scores are maxima over queries, and the study's ranking
# tie-break is the IRI.
os.environ.setdefault("PYTHONHASHSEED", "0")
sys.path.insert(0, str(MIGRATION))

import combine_lab  # noqa: E402
import sweep  # noqa: E402

from app.services.folio import concept_resolver as cr  # noqa: E402


@pytest.fixture(scope="module")
def corpus():
    return sweep._corpus()


@pytest.fixture(scope="module")
def gold():
    return sweep._gold()


@pytest.fixture(scope="module")
def pools(corpus):
    return sweep.build_pools(corpus, None)


# ---------------------------------------------------------------------------
# Fidelity
# ---------------------------------------------------------------------------


def test_reconstruction_equals_the_real_resolver(corpus, pools):
    """The sweep evaluates a cached candidate pool instead of re-running the resolver 200×.

    That shortcut is only legitimate because neither knob can change retrieval or stage
    scoring. This is the proof: at the production operating point the reconstruction must
    reproduce ``resolve_concepts`` exactly, in both embedding modes, on every narrative.
    """
    assert sweep.verify_reference(corpus, pools) == []


def test_current_rule_is_the_production_combine_function():
    """The status-quo arm of every sweep must BE ``_combine_score``, not a reimplementation."""
    for e, label, llm in [
        (0.8, 0.7, 0.9),
        (0.9, None, None),
        (None, 0.9, None),
        (None, None, 0.8),
        (0.6, 0.6, None),
        (None, None, None),
        (0.0, 0.0, 0.0),
    ]:
        assert sweep.combined_score(
            e, label, llm, penalty=cr.SINGLE_STAGE_PENALTY, rule="current"
        ) == cr._combine_score(embedding_score=e, label_score=label, llm_score=llm)


def test_reference_matches_the_signed_off_migration_capture(pools):
    """The study's reference point is the same behavior the delta report was signed off on."""
    capture = json.loads((MIGRATION / "captures" / "candidate.json").read_text())
    reference = sweep.evaluate_point(
        pools, penalty=sweep.REF_PENALTY, threshold=sweep.REF_THRESHOLD, rule="current"
    )
    for seam, mode in (("resolve", "healthy"), ("resolve_no_embed", "degraded")):
        for row in capture[seam]:
            captured = sorted((r["iri"], r["confidence"]) for r in row["top"])
            assert sorted(reference[mode][row["id"]]) == captured, f"{seam}/{row['id']}"


# ---------------------------------------------------------------------------
# The study changes nothing
# ---------------------------------------------------------------------------


def test_production_operating_point_is_untouched():
    """The knobs the study sweeps are still exactly where the migration left them."""
    assert cr.SINGLE_STAGE_PENALTY == 0.7
    assert cr.ConceptResolutionConfig().confidence_threshold == 0.5
    assert cr.EMBEDDING_WEIGHT == 0.3
    assert cr.LABEL_WEIGHT == 0.3
    assert cr.LLM_WEIGHT == 0.4


def test_sweeping_restores_every_patched_attribute(corpus):
    """In-process patching is how the sweep avoids editing ``app/``; it must leave no residue."""
    import folio_resolve

    before = (cr.SINGLE_STAGE_PENALTY, cr.compute_relevance_score, cr.expand_legal_terms)
    sweep.combined_score(0.4, 0.8, None, penalty=0.95, rule="current")
    sweep.build_pools(corpus, None, expansions=False)
    assert (cr.SINGLE_STAGE_PENALTY, cr.compute_relevance_score, cr.expand_legal_terms) == before
    assert cr.SINGLE_STAGE_PENALTY == 0.7
    assert cr.compute_relevance_score is folio_resolve.compute_relevance_score


def test_the_study_only_ever_writes_into_its_own_captures_directory():
    """A guard against the study quietly becoming a change: every write lands in migration/."""
    for path in (MIGRATION / "sweep.py", MIGRATION / "combine_lab.py"):
        for line in path.read_text().splitlines():
            if ".write_text(" in line:
                assert "CAPTURES_DIR" in line, f"{path.name}: writes outside captures/: {line}"


# ---------------------------------------------------------------------------
# Gold-label integrity — the recommendation rests on these labels
# ---------------------------------------------------------------------------


def test_gold_labels_cover_exactly_the_corpus_narratives(corpus, gold):
    assert set(gold["narratives"]) == {n["id"] for n in corpus["narratives"]}


def test_gold_labels_reference_real_concepts(corpus, gold):
    known = {row["iri"] for row in corpus["ontology"]}
    for nid, spec in gold["narratives"].items():
        good, ambiguous = set(spec["good"]), set(spec["ambiguous"])
        assert good <= known, f"{nid}: unknown IRI in good"
        assert ambiguous <= known, f"{nid}: unknown IRI in ambiguous"
        assert not (good & ambiguous), f"{nid}: an IRI is both good and ambiguous"


def test_gold_never_marks_a_branch_root_or_placeholder_good(corpus, gold):
    """Closed-world scoring depends on roots and placeholders counting as errors."""
    roots = {row["iri"] for row in corpus["ontology"] if row.get("parent") is None}
    for nid, spec in gold["narratives"].items():
        assert not (set(spec["good"]) & roots), f"{nid}: a branch root marked good"
        assert "r-sandbox" not in spec["good"], f"{nid}: the placeholder marked good"


def test_narratives_that_must_resolve_to_nothing_have_no_gold(corpus, gold):
    empty = {n["id"] for n in corpus["narratives"] if n["category"] in sweep.MUST_BE_EMPTY}
    for nid in empty:
        assert gold["narratives"][nid]["good"] == []
        assert gold["narratives"][nid]["ambiguous"] == []


# ---------------------------------------------------------------------------
# The combine-oddity characterization
# ---------------------------------------------------------------------------


def test_status_quo_combine_is_not_evidence_monotone():
    """Characterization: adding a weak stage can LOWER the score. If this ever fails, the
    study's remedy section is stale and must be rewritten, not silently kept."""
    status_quo = combine_lab.invariants("current")
    assert status_quo["evidence_monotone"] is False
    assert status_quo["worst_evidence_drop"] == pytest.approx(0.2)


def test_the_floor_remedy_restores_evidence_monotonicity():
    floor = combine_lab.invariants("floor")
    assert floor["evidence_monotone"] is True
    assert floor["stage_monotone"] is True
    assert floor["bounded"] is True
    # ...and it does not move the confidence scale: a solo exact label scores the same.
    assert floor["exact_label_only"] == combine_lab.invariants("current")["exact_label_only"]


def test_the_obvious_generalization_does_not_fix_it():
    """Grading the single-stage penalty by coverage is the intuitive fix and does NOT work."""
    coverage = combine_lab.invariants("coverage")
    assert coverage["evidence_monotone"] is False


def test_presence_weighting_fixes_it_but_rescales_the_axis():
    presence = combine_lab.invariants("presence")
    assert presence["evidence_monotone"] is True
    assert presence["exact_label_only"] < 0.35  # 0.5 would no longer mean anything


def test_the_inversion_is_reproducible_end_to_end():
    """Through the real ``resolve_concepts``: weak retrieval returns LESS than no retrieval."""
    rows = {row["embedding"]: row for row in combine_lab.end_to_end()}
    assert rows[None]["resolved"] == 1
    assert rows[0.10]["resolved"] == 0
    assert rows[0.30]["resolved"] == 1
