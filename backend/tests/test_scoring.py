"""Tests for composite confidence scoring function."""

from __future__ import annotations

import pytest

from app.services.analysis.scoring import (
    compute_composite_confidence,
    get_confidence_weights,
)
from app.services.analysis.schemas import ConfidenceWeights


# ---------------------------------------------------------------------------
# Default weights
# ---------------------------------------------------------------------------

class TestDefaultWeights:
    """Default weights (0.4 LLM, 0.3 concept, 0.3 fact) produce correct composite."""

    def test_known_computation(self):
        """compute_composite_confidence(0.8, 0.6, 0.9) = 0.8*0.4 + 0.6*0.3 + 0.9*0.3 = 0.77."""
        result = compute_composite_confidence(0.8, 0.6, 0.9)
        assert result == 0.77

    def test_all_zero_returns_zero(self):
        """All-zero inputs return 0.0."""
        result = compute_composite_confidence(0.0, 0.0, 0.0)
        assert result == 0.0

    def test_all_one_returns_one(self):
        """All-one inputs return 1.0."""
        result = compute_composite_confidence(1.0, 1.0, 1.0)
        assert result == 1.0

    def test_symmetric_inputs(self):
        """Equal inputs produce same value as input (weights sum to 1.0)."""
        result = compute_composite_confidence(0.5, 0.5, 0.5)
        assert result == 0.5


# ---------------------------------------------------------------------------
# Custom weights
# ---------------------------------------------------------------------------

class TestCustomWeights:
    """Custom ConfidenceWeights override defaults."""

    def test_custom_llm_heavy(self):
        """LLM-heavy weights: llm=0.8, concept=0.1, fact=0.1."""
        weights = ConfidenceWeights(llm_weight=0.8, concept_weight=0.1, fact_weight=0.1)
        result = compute_composite_confidence(1.0, 0.0, 0.0, weights=weights)
        assert result == 0.8

    def test_custom_equal_weights(self):
        """Equal weights: each 1/3."""
        weights = ConfidenceWeights(
            llm_weight=1.0 / 3,
            concept_weight=1.0 / 3,
            fact_weight=1.0 / 3,
        )
        result = compute_composite_confidence(0.9, 0.6, 0.3, weights=weights)
        # (0.9 + 0.6 + 0.3) / 3 = 0.6, but floating point: round(1/3*1.8, 4)
        assert abs(result - 0.6) < 0.01


# ---------------------------------------------------------------------------
# Clamping
# ---------------------------------------------------------------------------

class TestClamping:
    """Result is clamped to [0.0, 1.0]."""

    def test_clamp_above_one(self):
        """Weights that could produce >1.0 are clamped."""
        weights = ConfidenceWeights(llm_weight=1.0, concept_weight=1.0, fact_weight=1.0)
        result = compute_composite_confidence(1.0, 1.0, 1.0, weights=weights)
        assert result == 1.0

    def test_clamp_below_zero(self):
        """Negative inputs are clamped to 0.0."""
        # Edge case: negative confidence should clamp
        result = compute_composite_confidence(-0.5, -0.5, -0.5)
        assert result == 0.0


# ---------------------------------------------------------------------------
# Parametrized known values
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "llm, concept, fact, expected",
    [
        (1.0, 1.0, 1.0, 1.0),
        (0.0, 0.0, 0.0, 0.0),
        (0.8, 0.6, 0.9, 0.77),
        (0.5, 0.5, 0.5, 0.5),
        (1.0, 0.0, 0.0, 0.4),
        (0.0, 1.0, 0.0, 0.3),
        (0.0, 0.0, 1.0, 0.3),
    ],
)
def test_parametrized_defaults(llm, concept, fact, expected):
    """Verify known input/output pairs with default weights."""
    result = compute_composite_confidence(llm, concept, fact)
    assert result == expected


# ---------------------------------------------------------------------------
# get_confidence_weights helper
# ---------------------------------------------------------------------------

class TestGetConfidenceWeights:
    """get_confidence_weights reads weights from an org AnalysisConfig dict."""

    def test_from_config_with_weights(self):
        config = {
            "confidence_weights": {
                "llm_weight": 0.5,
                "concept_weight": 0.25,
                "fact_weight": 0.25,
            }
        }
        weights = get_confidence_weights(config)
        assert weights.llm_weight == 0.5
        assert weights.concept_weight == 0.25
        assert weights.fact_weight == 0.25

    def test_from_config_none_returns_defaults(self):
        weights = get_confidence_weights(None)
        assert weights.llm_weight == 0.4
        assert weights.concept_weight == 0.3
        assert weights.fact_weight == 0.3

    def test_from_config_empty_returns_defaults(self):
        weights = get_confidence_weights({})
        assert weights.llm_weight == 0.4

    def test_from_config_partial_weights(self):
        config = {"confidence_weights": {"llm_weight": 0.6}}
        weights = get_confidence_weights(config)
        assert weights.llm_weight == 0.6
        assert weights.concept_weight == 0.3  # default retained
