"""Anti-refork guard for the folio-resolve migration.

alea-intake used to own a hand-rolled FOLIO label scorer and a hand-curated geographic gate.
Both now come from the pinned, MIT-licensed `folio-resolve` library
(``folio-resolve/docs/migration/SCHEDULE.md`` row 4). The whole point of that migration is that
the copy is *gone* — so these tests assert **object identity** with the library, not merely
"the numbers look right". A future edit that quietly re-forks the scorer or the gate back into
this repo fails here, loudly.

They also pin the golden scores that the classified migration delta
(``backend/migration/DELTA-REPORT.md``) was signed off on, and the two architectural decisions
the migration made:

* ``PlaceNameGate`` **is** adopted for claim fitness (a legal claim is never a place or an agency)
* ``PlaceNameGate`` is **not** applied in the general resolver (jurisdictions and venues are
  legitimate resolution targets)
"""

from __future__ import annotations

import inspect

import folio_resolve
import pytest

from app.services.analysis import semantic_fit
from app.services.folio import concept_resolver, term_expansions


# ---------------------------------------------------------------------------
# Identity: the library is CONSUMED, not merely installed
# ---------------------------------------------------------------------------


def test_label_scorer_is_the_library_function():
    """The Stage-2 scorer is the library's object, not a local copy of it."""
    assert concept_resolver.compute_relevance_score is folio_resolve.compute_relevance_score
    assert concept_resolver.content_words is folio_resolve.content_words


def test_place_gate_is_the_library_gate():
    """The geographic test is backed by the library's PlaceNameGate."""
    assert isinstance(semantic_fit._PLACE_GATE, folio_resolve.PlaceNameGate)


def test_no_local_refork_of_the_label_scorer():
    """The deleted hand-rolled ratio must not reappear in concept_resolver."""
    source = inspect.getsource(concept_resolver)
    # The exact shape of the retired scorer: a set-intersection over whitespace splits,
    # normalized by the longer side, with flat substring/prefix constants.
    assert "match_ratio" not in source
    assert "set(query_lower.split()) & set(label_lower.split())" not in source


# ---------------------------------------------------------------------------
# Golden scores — the operating point the delta report was signed off on
# ---------------------------------------------------------------------------


class _Concept:
    """Minimal folio-python OWLClass stand-in."""

    def __init__(self, label: str, *, synonyms=None, preferred=None) -> None:
        self.label = label
        self.alternative_labels = synonyms or []
        if preferred is not None:
            self.preferred_label = preferred


@pytest.mark.parametrize(
    "query,label,expected",
    [
        # Exact match tops the scale (was a flat 0.9 substring constant).
        ("Arbitration Rules", "Arbitration Rules", 0.99),
        # Word-order invariance — the headline defect of the retired scorer.
        ("rules of arbitration", "Arbitration Rules", 0.88),
        # Prefix / morphology credit — the retired scorer scored this 0.0.
        ("arbitrating", "Arbitration Rules", 0.37),
        # Specificity penalty — a one-word query against a three-word label.
        ("custody", "Child Custody Determination", 0.675),
        # No shared content: still zero.
        ("wrongful termination", "Macedonia", 0.0),
        # An empty label never produces a candidate.
        ("anything", "", 0.0),
    ],
)
def test_golden_label_scores(query, label, expected):
    assert concept_resolver._label_match_score(query, _Concept(label)) == pytest.approx(expected)


def test_label_scorer_survives_non_string_attributes():
    """folio-python may return None, and test doubles return mocks, for optional attributes."""

    class _Sloppy:
        label = "Retaliation Claim"
        preferred_label = None
        alternative_labels = None

    assert concept_resolver._label_match_score("retaliation", _Sloppy()) > 0.5


def test_alternative_labels_count_as_label_evidence():
    """Synonyms are label evidence — Stage 2 is the label stage."""
    bare = concept_resolver._label_match_score("dissolution of marriage", _Concept("Divorce"))
    with_syn = concept_resolver._label_match_score(
        "dissolution of marriage", _Concept("Divorce", synonyms=["Dissolution of Marriage"])
    )
    assert with_syn > bare


def test_definition_alone_never_produces_a_label_hit():
    """Definitional similarity is Stage 1's job; Stage 2 must not manufacture label matches."""

    class _WithDefinition:
        label = "Living"
        alternative_labels = []
        definition = "A claim that a rented dwelling was unfit for habitability and occupancy"

    assert concept_resolver._label_match_score("habitability", _WithDefinition()) == 0.0


# ---------------------------------------------------------------------------
# PlaceNameGate: adopted for claim fitness, NOT for general resolution
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "label,branch",
    [
        ("Rize", "Location"),                    # place by branch (the BUG-21 original)
        ("Slovenia", ""),                        # place by the library's curated token set
        ("Department of Labor", "Governmental Body"),  # agency — NEW under the library gate
        ("Housing Authority", "Governmental Body"),
        ("Europe", None),                        # continent — the local marker backstop
        ("City of Exampleton", "Unknown"),       # "City of X" — the local marker backstop
    ],
)
def test_claims_never_map_to_places_or_agencies(label, branch):
    assert semantic_fit.is_geographic_concept(label, branch) is True
    assert semantic_fit.deterministic_unfit_reason(label, branch) == "geographic_concept"


@pytest.mark.parametrize(
    "label,branch",
    [
        ("Retaliation Claim", "Objectives"),
        ("Breach of Warranty of Habitability", "Objectives"),
        ("Fair Debt Collection Practices Act", "Legal Authorities"),
        ("Eviction Notice", "Document-Artifact"),
        ("Mediation Service", "Service"),
    ],
)
def test_good_claim_mappings_are_not_over_rejected(label, branch):
    assert semantic_fit.is_geographic_concept(label, branch) is False
    assert semantic_fit.deterministic_unfit_reason(label, branch) is None


def test_place_gate_is_not_applied_in_the_general_resolver():
    """resolve_concepts resolves jurisdictions and venues on purpose.

    The claim-fitness gate must not leak into it — mirrored by the migration harness's
    PLACES-RESOLVABLE canary. Asserted structurally: the resolver module neither imports the
    gate nor consults the semantic-fit geographic test.
    """
    source = inspect.getsource(concept_resolver)
    assert "PlaceNameGate" not in source
    assert "is_geographic_concept" not in source


# ---------------------------------------------------------------------------
# Consumer-specific seams stay local
# ---------------------------------------------------------------------------


def test_consumer_expansions_are_not_the_library_expansions():
    """Lay-language expansion ("fired" -> "wrongful termination") is alea's own vocabulary.

    The library's LEGAL_TERM_EXPANSIONS solves the opposite problem (legal content word ->
    FOLIO label suffix). Collapsing them would break intake narratives.
    """
    assert term_expansions.LEGAL_TERM_EXPANSIONS is not folio_resolve.LEGAL_TERM_EXPANSIONS
    assert "fired" in term_expansions.LEGAL_TERM_EXPANSIONS
    assert "fired" not in folio_resolve.LEGAL_TERM_EXPANSIONS


def test_consumer_stopwords_are_not_the_library_stopwords():
    """Two vocabularies, two jobs: query construction vs scoring."""
    assert term_expansions.SEARCH_STOPWORDS is not folio_resolve.SEARCH_STOPWORDS
    # alea drops first/second-person pronouns so a narrative becomes a usable query.
    assert {"i", "my", "we", "you"} <= term_expansions.SEARCH_STOPWORDS
    # The library drops legal filler that would inflate overlap against FOLIO labels.
    assert {"law", "legal", "type"} <= folio_resolve.SEARCH_STOPWORDS


def test_combine_policy_stays_local():
    """The 3-stage weighted combine is alea's cascade policy; the library has no equivalent."""
    assert concept_resolver.EMBEDDING_WEIGHT == 0.3
    assert concept_resolver.LABEL_WEIGHT == 0.3
    assert concept_resolver.LLM_WEIGHT == 0.4
    assert concept_resolver.SINGLE_STAGE_PENALTY == 0.7
