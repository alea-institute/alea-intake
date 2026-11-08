"""Guards for the operating-point calibration study (``backend/migration/sweep.py``).

The historical weighted-average arm preserves the signed-off baseline; the adopted floor
arm must match production. Tests also pin gold-label integrity, the predicted acceptance
deltas, and the study's lack of persistent changes to production configuration.
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
    scoring. This is the proof: at the adopted production operating point the reconstruction must
    reproduce ``resolve_concepts`` exactly, in both embedding modes, on every narrative.
    """
    assert sweep.verify_reference(corpus, pools) == []


def test_floor_rule_matches_the_production_combine_function():
    """The adopted floor rule must reproduce the production combine function."""
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
            e, label, llm, penalty=cr.SINGLE_STAGE_PENALTY, rule="floor"
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


def test_production_operating_point_is_adopted():
    """The adopted calibration keeps the stage weights unchanged."""
    assert cr.SINGLE_STAGE_PENALTY == 0.85
    assert cr.ConceptResolutionConfig().confidence_threshold == 0.55
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
    assert cr.SINGLE_STAGE_PENALTY == 0.85
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


def test_the_inversion_is_fixed_end_to_end():
    """Through the real resolver, weak retrieval no longer suppresses the label match."""
    rows = {row["embedding"]: row for row in combine_lab.end_to_end()}
    assert rows[None]["resolved"] == 1
    assert rows[0.10]["resolved"] == 1
    assert rows[0.30]["resolved"] == 1


@pytest.mark.parametrize("mode,seam,fails", [("healthy", "resolve", False), ("degraded", "resolve_no_embed", True)])
def test_adopted_resolver_changes_only_predicted_golden_concepts(corpus, mode, seam, fails):
    import asyncio
    import harness

    capture = json.loads((MIGRATION / "captures" / "candidate.json").read_text())
    expected = {row["id"]: {r["iri"] for r in row["top"]} for row in capture[seam]}
    if mode == "healthy":
        for nid in ("n-exact-label", "n-word-order-2"):
            expected[nid] -= {"r-premises-liability", "r-wrongful-termination"}
    else:
        expected["n-word-order-2"].add("r-retaliation")
        expected["n-expansion-debt"].add("r-fair-debt-act")
        expected["n-homonym-habitability"].add("r-habitability")
    folio = harness._FakeFOLIO(corpus["ontology"])
    embedding = harness._FakeEmbeddingService(corpus["ontology"], fail=fails)
    for item in corpus["narratives"]:
        actual = asyncio.run(cr.resolve_concepts(
            item["text"], folio, embedding,
            config=cr.ConceptResolutionConfig(enable_llm_stage=False),
        ))
        assert {r.iri for r in actual} == expected[item["id"]], item["id"]


def test_empty_vocabulary_keeps_filtered_narrative_query(corpus):
    from app.services.folio import term_expansions as te

    before = te.LEGAL_TERM_EXPANSIONS
    pools = sweep.build_pools(corpus, None, vocabulary={})
    accepted = sweep.evaluate_point(pools, penalty=0.85, threshold=0.55, rule="floor")
    assert te.LEGAL_TERM_EXPANSIONS is before
    assert {iri for iri, _ in accepted["healthy"]["n-expansion-fired"]} == set()
    assert {iri for iri, _ in accepted["degraded"]["n-exact-label"]} == {"r-retaliation"}

    # A long filler prefix hides the label from fuzzy retrieval until filtering.
    narrative = {"id": "filtered", "text": "I was am " * 15 + "Retaliation Claim"}
    filtered_corpus = {**corpus, "narratives": [narrative]}
    retained = sweep.build_pools(filtered_corpus, None, vocabulary={})
    disabled = sweep.build_pools(filtered_corpus, None, expansions=False)
    for mode in ("healthy", "degraded"):
        assert {iri for iri, _ in sweep.evaluate_point(
            retained, penalty=0.85, threshold=0.55, rule="floor"
        )[mode]["filtered"]} == {"r-retaliation"}
        assert sweep.evaluate_point(
            disabled, penalty=0.85, threshold=0.55, rule="floor"
        )[mode]["filtered"] == []


def test_expansion_study_attributes_claim_false_positives(corpus, gold, monkeypatch, capsys):
    from app.services.folio import term_expansions as te

    before = te.LEGAL_TERM_EXPANSIONS
    monkeypatch.setattr(sys, "argv", ["sweep.py", "--expansion-study"])
    assert sweep.main() == 0
    study = json.loads(capsys.readouterr().out)
    assert te.LEGAL_TERM_EXPANSIONS is before
    assert study["operating_point"] == {"penalty": 0.85, "threshold": 0.55, "rule": "floor"}
    baseline = study["arms"][0]
    assert baseline["name"] == "adopted"
    assert baseline["metrics"]["healthy"]["tp"] == 20
    assert baseline["metrics"]["healthy"]["fp"] == 6
    claim = next(a for a in study["arms"] if a["name"] == "without-trigger:claim")
    removed = claim["metrics"]["healthy"]["flips_reject_rows"]
    assert {"narrative": "n-exact-label", "iri": "r-insurance-claims"} in removed
    assert {"narrative": "n-word-order-2", "iri": "r-insurance-claims"} in removed
    phrase = next(a for a in study["arms"] if a["name"] == "without-phrase:claim:insurance claim")
    assert {"narrative": "n-exact-label", "iri": "r-insurance-claims"} in phrase["metrics"]["healthy"]["flips_reject_rows"]
    assert len(study["trigger_coverage"]) == len(before)
    assert {"narrative": "n-word-order-2", "iri": "r-lease-agreement"} in phrase["metrics"]["healthy"]["flips_accept_rows"]
    fired = next(a for a in study["arms"] if a["name"] == "without-phrase:fired:wrongful termination")
    rent = next(a for a in study["arms"] if a["name"] == "without-phrase:rent:housing")
    for mode in ("healthy", "degraded"):
        assert fired["metrics"][mode]["tp"] == 19
        assert {"narrative": "n-expansion-fired", "iri": "r-wrongful-termination"} in fired["metrics"][mode]["flips_reject_rows"]
        assert rent["metrics"][mode]["fp"] == 4
        assert rent["metrics"][mode]["tp"] == 20
