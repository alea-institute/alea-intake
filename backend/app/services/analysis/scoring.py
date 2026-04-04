"""Composite confidence scoring for fact-to-claim mappings (D-05).

Combines LLM mapping confidence, FOLIO ConceptResolver match strength,
and source fact confidence with org-configurable weights.
"""

from __future__ import annotations

from app.services.analysis.schemas import ConfidenceWeights


def compute_composite_confidence(
    llm_confidence: float,
    concept_confidence: float,
    fact_confidence: float,
    weights: ConfidenceWeights | None = None,
) -> float:
    """Compute a weighted composite confidence score.

    Args:
        llm_confidence: LLM mapping confidence (0.0-1.0).
        concept_confidence: FOLIO ConceptResolver match strength (0.0-1.0).
        fact_confidence: Source fact extraction confidence (0.0-1.0).
        weights: Optional custom weights. Defaults to (0.4, 0.3, 0.3).

    Returns:
        Composite confidence clamped to [0.0, 1.0], rounded to 4 decimal places.
    """
    w = weights or ConfidenceWeights()

    composite = (
        llm_confidence * w.llm_weight
        + concept_confidence * w.concept_weight
        + fact_confidence * w.fact_weight
    )

    # Clamp to [0.0, 1.0]
    composite = max(0.0, min(1.0, composite))

    return round(composite, 4)


def get_confidence_weights(config: dict | None) -> ConfidenceWeights:
    """Extract confidence weights from an org AnalysisConfig dict.

    Args:
        config: Org config dict, may contain a "confidence_weights" key
                with weight overrides.

    Returns:
        ConfidenceWeights with org overrides applied (or defaults).
    """
    if not config:
        return ConfidenceWeights()

    weights = ConfidenceWeights()
    if weight_overrides := config.get("confidence_weights"):
        for field in ("llm_weight", "concept_weight", "fact_weight"):
            if field in weight_overrides:
                setattr(weights, field, weight_overrides[field])

    return weights
