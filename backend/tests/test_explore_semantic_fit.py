"""BUG-22: the exploration lane must route discovered claim->FOLIO mappings
through the SemanticFitValidator (RUB-05 semantic-fit), the same guard
issue_spot uses. Regression: "Legal Representation"@0.90 -> IRI resolving to a
North Macedonia municipality ("Resen", a Location-branch geographic node)
surfaced as an urgent claim because the exploration lane bypassed the validator.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.services.analysis.stages.explore import ExploreStage

pytestmark = pytest.mark.asyncio


def _stage(llm=None, folio=object()):
    return ExploreStage(
        llm_service=llm,
        db_session=None,
        folio=folio,
        embedding_service=None,
    )


async def test_geographic_mapping_iri_dropped_and_confidence_capped():
    """A discovered claim resolving to a Location-branch node loses its IRI."""
    stage = _stage(llm=None)  # no LLM -> deterministic tier only
    discovered = [
        {"claim_name": "Legal Representation", "folio_iri": "https://folio/Resen",
         "confidence": 0.90, "source_layer": "cheap_llm"},
    ]
    facts = [SimpleNamespace(assertion_text="Client needs a lawyer for a custody case.")]

    with patch(
        "app.services.folio.folio_service.get_owl_class",
        return_value=SimpleNamespace(label="Resen"),
    ), patch(
        "app.services.folio.concept_resolver._determine_branch",
        return_value="Location",
    ):
        verdicts = await stage._validate_discovered_mappings(discovered, facts)

    v = verdicts.get("legal representation")
    assert v is not None, "geographic mapping should produce a verdict"
    assert v.drop_iri is True
    assert v.adjusted_confidence <= 0.4  # false-confidence ceiling


async def test_iri_less_claim_is_not_validated():
    """A discovered claim with no IRI has nothing to drop -> no verdict."""
    stage = _stage(llm=None)
    discovered = [
        {"claim_name": "Some Claim", "folio_iri": None, "confidence": 0.6,
         "source_layer": "expensive_llm"},
    ]
    verdicts = await stage._validate_discovered_mappings(discovered, [])
    assert verdicts == {}


async def test_no_folio_is_graceful_noop():
    """With FOLIO unavailable the validator is a no-op (never breaks exploration)."""
    stage = _stage(llm=None, folio=None)
    discovered = [
        {"claim_name": "X", "folio_iri": "https://folio/Whatever", "confidence": 0.8},
    ]
    verdicts = await stage._validate_discovered_mappings(discovered, [])
    assert verdicts == {}


async def test_good_mapping_survives_deterministic_tier():
    """A non-geographic, non-placeholder mapping on a legal branch is not dropped
    by the deterministic tier (no LLM -> no verdict means keep as-is)."""
    stage = _stage(llm=None)
    discovered = [
        {"claim_name": "Warranty of Habitability",
         "folio_iri": "https://folio/Habitability", "confidence": 0.85,
         "source_layer": "folio_adjacency"},
    ]
    facts = [SimpleNamespace(assertion_text="There is black mold and no heat.")]
    with patch(
        "app.services.folio.folio_service.get_owl_class",
        return_value=SimpleNamespace(label="Warranty of Habitability"),
    ), patch(
        "app.services.folio.concept_resolver._determine_branch",
        return_value="Area of Law",
    ):
        verdicts = await stage._validate_discovered_mappings(discovered, facts)
    # Deterministic tier keeps it; with no LLM there is no recalibration verdict.
    assert "warranty of habitability" not in verdicts
