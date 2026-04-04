"""Pydantic schemas and dataclasses for the analysis pipeline.

Note: This file provides the convergence and confidence dataclasses needed
by convergence.py and scoring.py. Plan 01 may extend this file with
additional Pydantic schemas for LLM I/O and analysis configuration.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ConvergenceWeights:
    """Default weights for convergence signals. Must sum to ~1.0."""

    coverage: float = 0.30
    confidence_plateau: float = 0.20
    iteration_cap: float = 0.10
    user_fatigue: float = 0.15
    diminishing_gaps: float = 0.25


@dataclass
class ConvergenceSignals:
    """Input signals for convergence evaluation."""

    coverage_pct: float  # 0.0-1.0: fraction of claim elements with supporting facts
    confidence_delta: float  # Change in composite confidence from previous iteration
    iteration_number: int  # Current iteration (1-based)
    max_iterations: int  # Hard cap
    skip_rate: float  # Questions skipped / questions asked (0.0-1.0)
    avg_response_time_sec: float  # Average consumer response time
    new_gaps_count: int  # Gaps discovered this iteration
    previous_gaps_count: int  # Gaps that existed before this iteration


@dataclass
class ConfidenceWeights:
    """Weights for composite confidence scoring (D-05)."""

    llm_weight: float = 0.4
    concept_weight: float = 0.3
    fact_weight: float = 0.3
