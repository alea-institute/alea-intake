"""Multi-signal convergence evaluator for the analysis loop.

Implements D-13 (five weighted signals), D-14 (hard iteration cap),
and hysteresis to prevent oscillation once convergence is reached.
"""

from __future__ import annotations

from app.services.analysis.schemas import ConvergenceSignals, ConvergenceWeights


class ConvergenceEvaluator:
    """Evaluates whether the analysis loop should terminate.

    Uses five weighted signals:
      - coverage: fraction of claim elements with supporting facts
      - confidence_plateau: scores stopped improving across iterations
      - iteration_cap: approaching max iterations
      - user_fatigue: consumer skip rate / disengagement
      - diminishing_gaps: fewer new gaps discovered per iteration

    Hard iteration cap always terminates regardless of signals.
    Hysteresis prevents oscillation once convergence is reached.
    """

    def __init__(
        self,
        weights: ConvergenceWeights | None = None,
        threshold: float = 0.75,
        hysteresis_margin: float = 0.1,
    ) -> None:
        self.weights = weights or ConvergenceWeights()
        self.threshold = threshold
        self.hysteresis_margin = hysteresis_margin
        self._previously_converged = False

    def evaluate(self, signals: ConvergenceSignals) -> tuple[bool, float]:
        """Evaluate convergence from current signals.

        Returns:
            (converged, score) where converged is True if the loop should stop
            and score is the weighted composite in [0.0, 1.0].
        """
        # Hard cap always terminates (D-14)
        if signals.iteration_number >= signals.max_iterations:
            self._previously_converged = True
            return True, 1.0

        # Compute per-signal scores (each 0.0-1.0)
        scores = {
            "coverage": signals.coverage_pct,
            "confidence_plateau": (
                1.0 - min(abs(signals.confidence_delta), 0.1) / 0.1
            ),
            "iteration_cap": signals.iteration_number / signals.max_iterations,
            "user_fatigue": min(signals.skip_rate * 2, 1.0),
            "diminishing_gaps": (
                1.0 - (signals.new_gaps_count / max(signals.previous_gaps_count, 1))
                if signals.previous_gaps_count > 0
                else 0.5
            ),
        }

        # Weighted sum
        combined = sum(
            scores[k] * getattr(self.weights, k) for k in scores
        )
        combined = round(combined, 4)

        # Apply hysteresis: once converged, lower the threshold so small
        # regressions don't cause oscillation
        effective_threshold = self.threshold
        if self._previously_converged:
            effective_threshold = self.threshold - self.hysteresis_margin

        converged = combined >= effective_threshold
        self._previously_converged = converged

        return converged, combined

    @classmethod
    def from_org_config(cls, config: dict) -> ConvergenceEvaluator:
        """Create an evaluator from an org AnalysisConfig dict.

        Expected keys:
          - convergence_weights: dict with weight overrides
          - convergence_threshold: float override for threshold
          - hysteresis_margin: float override for hysteresis
        """
        weights = ConvergenceWeights()
        if weight_overrides := config.get("convergence_weights"):
            for field in (
                "coverage",
                "confidence_plateau",
                "iteration_cap",
                "user_fatigue",
                "diminishing_gaps",
            ):
                if field in weight_overrides:
                    setattr(weights, field, weight_overrides[field])

        threshold = config.get("convergence_threshold", 0.75)
        hysteresis = config.get("hysteresis_margin", 0.1)

        return cls(weights=weights, threshold=threshold, hysteresis_margin=hysteresis)
