"""Tests for semantic-fit validation of claim -> FOLIO concept mappings (BUG-21)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.analysis.semantic_fit import (
    FitItem,
    SemanticFitValidator,
    deterministic_unfit_reason,
    is_geographic_concept,
)


# ---------------------------------------------------------------------------
# Deterministic tier
# ---------------------------------------------------------------------------


def test_geographic_concept_by_branch():
    """A Location-branch concept is geographic regardless of label."""
    assert is_geographic_concept("Rize", "Location")
    assert is_geographic_concept("Anytown", "Location")


def test_geographic_concept_by_label():
    """Known geographic labels are caught even without branch metadata."""
    assert is_geographic_concept("Europe", None)
    assert is_geographic_concept("Macedonia", "")
    assert is_geographic_concept("Republic of Example", None)


def test_non_geographic_legal_concept():
    """A legal concept in Area of Law is not geographic."""
    assert not is_geographic_concept("Breach of Warranty of Habitability", "Area of Law")
    assert not is_geographic_concept("Retaliation", "Area of Law")


@pytest.mark.parametrize(
    "label,branch,expected",
    [
        ("Rize", "Location", "geographic_concept"),
        ("Europe", None, "geographic_concept"),
        ("ZZZ - SANDBOX", "Area of Law", "placeholder_concept"),
        ("Something", "Unknown", "unfit_branch"),
        ("Something", "", "unfit_branch"),
        ("Breach of Contract", "Area of Law", None),
    ],
)
def test_deterministic_unfit_reason(label, branch, expected):
    assert deterministic_unfit_reason(label, branch) == expected


async def test_validator_drops_geographic_mapping():
    """A geographic mapping is rejected with the IRI dropped and confidence capped."""
    items = [
        FitItem(
            key="unauthorized employment",
            claim_name="Unauthorized Employment",
            concept_label="Rize",
            branch="Location",
            confidence=0.85,
        )
    ]
    validator = SemanticFitValidator(llm_service=None)
    verdicts = await validator.validate("immigration matter", items)

    v = verdicts["unauthorized employment"]
    assert v.fits is False
    assert v.drop_iri is True
    assert v.adjusted_confidence <= 0.4
    assert v.reason == "geographic_concept"


async def test_validator_no_llm_keeps_fit_branch():
    """Without an LLM, a fit-branch mapping is left untouched (no verdict)."""
    items = [
        FitItem(
            key="retaliation",
            claim_name="Retaliation",
            concept_label="Retaliatory Eviction",
            branch="Area of Law",
            confidence=0.8,
        )
    ]
    validator = SemanticFitValidator(llm_service=None)
    verdicts = await validator.validate("landlord tenant matter", items)
    assert "retaliation" not in verdicts  # survived; no change needed


# ---------------------------------------------------------------------------
# LLM tier
# ---------------------------------------------------------------------------


async def test_validator_llm_rejects_context_mismatch():
    """The LLM flags a same-branch but context-wrong mapping and drops the IRI."""
    from app.services.analysis.semantic_fit import _FitDecision, _FitResponse

    llm = SimpleNamespace(
        json_async=AsyncMock(
            return_value=_FitResponse(
                decisions=[
                    _FitDecision(
                        claim_name="Rent Withholding",
                        fits=False,
                        adjusted_confidence=0.2,
                        reason="Insurance Claims is unrelated to rent withholding",
                    )
                ]
            )
        )
    )
    items = [
        FitItem(
            key="rent withholding",
            claim_name="Rent Withholding",
            concept_label="Insurance Claims",
            branch="Area of Law",
            confidence=0.9,
        )
    ]
    validator = SemanticFitValidator(llm_service=llm)
    verdicts = await validator.validate("tenant withheld rent for repairs", items)

    v = verdicts["rent withholding"]
    assert v.fits is False
    assert v.drop_iri is True
    assert v.adjusted_confidence <= 0.4


async def test_validator_llm_failure_degrades_to_deterministic():
    """If the LLM call raises, the deterministic verdicts still apply."""
    llm = SimpleNamespace(json_async=AsyncMock(side_effect=RuntimeError("boom")))
    items = [
        FitItem(
            key="macedonia",
            claim_name="Macedonia",
            concept_label="Macedonia",
            branch="Location",
            confidence=0.7,
        ),
        FitItem(
            key="breach",
            claim_name="Breach of Contract",
            concept_label="Breach of Contract",
            branch="Area of Law",
            confidence=0.8,
        ),
    ]
    validator = SemanticFitValidator(llm_service=llm)
    verdicts = await validator.validate("some matter", items)

    # Geographic dropped deterministically; fit-branch item unaffected.
    assert verdicts["macedonia"].drop_iri is True
    assert "breach" not in verdicts
