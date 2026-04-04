"""Tests for ConvergenceEvaluator with multi-signal convergence logic."""

from __future__ import annotations

import pytest

from app.services.analysis.convergence import ConvergenceEvaluator
from app.services.analysis.schemas import ConvergenceSignals, ConvergenceWeights


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _signals(**overrides) -> ConvergenceSignals:
    """Build a ConvergenceSignals with sensible defaults, overridden by kwargs."""
    defaults = dict(
        coverage_pct=0.5,
        confidence_delta=0.05,
        iteration_number=3,
        max_iterations=10,
        skip_rate=0.1,
        avg_response_time_sec=15.0,
        new_gaps_count=2,
        previous_gaps_count=5,
    )
    defaults.update(overrides)
    return ConvergenceSignals(**defaults)


# ---------------------------------------------------------------------------
# Hard cap tests
# ---------------------------------------------------------------------------

class TestHardCap:
    """Hard iteration cap always terminates regardless of other signals."""

    def test_hard_cap_exact(self):
        """iteration_number == max_iterations => converged with score 1.0."""
        ev = ConvergenceEvaluator()
        sig = _signals(iteration_number=10, max_iterations=10)
        converged, score = ev.evaluate(sig)
        assert converged is True
        assert score == 1.0

    def test_hard_cap_exceeded(self):
        """iteration_number > max_iterations => converged with score 1.0."""
        ev = ConvergenceEvaluator()
        sig = _signals(iteration_number=15, max_iterations=10)
        converged, score = ev.evaluate(sig)
        assert converged is True
        assert score == 1.0


# ---------------------------------------------------------------------------
# Signal combination tests
# ---------------------------------------------------------------------------

class TestSignalCombination:
    """Weighted signal combination produces expected convergence decisions."""

    def test_all_signals_zero_does_not_converge(self):
        """All signals at 0.0 with iteration_number=1 => not converged, low score."""
        ev = ConvergenceEvaluator()
        sig = ConvergenceSignals(
            coverage_pct=0.0,
            confidence_delta=0.1,  # max delta => plateau score = 0.0
            iteration_number=1,
            max_iterations=10,
            skip_rate=0.0,
            avg_response_time_sec=5.0,
            new_gaps_count=10,
            previous_gaps_count=10,  # new==prev => diminishing = 0.0
        )
        converged, score = ev.evaluate(sig)
        assert converged is False
        assert score < 0.75

    def test_all_signals_max_converges(self):
        """All signals at maximum => converged, high score."""
        ev = ConvergenceEvaluator()
        sig = ConvergenceSignals(
            coverage_pct=1.0,
            confidence_delta=0.0,  # perfect plateau
            iteration_number=9,
            max_iterations=10,
            skip_rate=1.0,
            avg_response_time_sec=60.0,
            new_gaps_count=0,
            previous_gaps_count=10,  # no new gaps => diminishing = 1.0
        )
        converged, score = ev.evaluate(sig)
        assert converged is True
        assert score >= 0.75

    def test_high_coverage_low_others_may_converge(self):
        """High coverage (0.95) can push weighted total over threshold even with weak other signals."""
        # With coverage weight=0.3 and coverage=0.95, coverage contributes 0.285
        # Need other signals to push total above 0.75
        ev = ConvergenceEvaluator()
        sig = ConvergenceSignals(
            coverage_pct=0.95,
            confidence_delta=0.02,  # plateau = 0.8
            iteration_number=7,
            max_iterations=10,  # iteration_cap = 0.7
            skip_rate=0.3,  # fatigue = 0.6
            avg_response_time_sec=30.0,
            new_gaps_count=1,
            previous_gaps_count=5,  # diminishing = 0.8
        )
        converged, score = ev.evaluate(sig)
        # coverage: 0.95*0.30 = 0.285
        # plateau: 0.8*0.20 = 0.16
        # iter_cap: 0.7*0.10 = 0.07
        # fatigue: 0.6*0.15 = 0.09
        # diminishing: 0.8*0.25 = 0.20
        # total = 0.805
        assert converged is True
        assert score >= 0.75

    def test_user_fatigue_contributes(self):
        """High skip_rate contributes meaningfully to convergence score."""
        ev = ConvergenceEvaluator()
        low_fatigue = _signals(skip_rate=0.0)
        high_fatigue = _signals(skip_rate=0.8)

        _, score_low = ev.evaluate(low_fatigue)
        _, score_high = ev.evaluate(high_fatigue)
        assert score_high > score_low

    def test_diminishing_gaps_scores_high_when_no_new_gaps(self):
        """0 new gaps vs 10 previous => diminishing_gaps signal = 1.0."""
        ev = ConvergenceEvaluator()
        sig = _signals(new_gaps_count=0, previous_gaps_count=10)
        # diminishing = 1.0 - 0/10 = 1.0
        # With default weight 0.25, this contributes 0.25 to the total
        converged, score = ev.evaluate(sig)
        # We just verify the signal is contributing positively
        sig_with_gaps = _signals(new_gaps_count=10, previous_gaps_count=10)
        _, score_with_gaps = ev.evaluate(sig_with_gaps)
        assert score > score_with_gaps


# ---------------------------------------------------------------------------
# Custom weights and threshold
# ---------------------------------------------------------------------------

class TestCustomWeights:
    """Org-configurable weights override defaults."""

    def test_custom_weights_coverage_dominant(self):
        """coverage=0.8 makes coverage the dominant signal."""
        weights = ConvergenceWeights(
            coverage=0.8,
            confidence_plateau=0.05,
            iteration_cap=0.05,
            user_fatigue=0.05,
            diminishing_gaps=0.05,
        )
        ev = ConvergenceEvaluator(weights=weights)
        sig = _signals(coverage_pct=0.95)  # High coverage
        converged, score = ev.evaluate(sig)
        # coverage alone: 0.95 * 0.8 = 0.76 -- should dominate
        assert converged is True
        assert score >= 0.75

    def test_custom_threshold_lower(self):
        """Threshold of 0.5 makes convergence easier."""
        ev = ConvergenceEvaluator(threshold=0.5)
        sig = _signals(
            coverage_pct=0.6,
            confidence_delta=0.05,
            iteration_number=3,
            max_iterations=10,
            skip_rate=0.2,
            new_gaps_count=2,
            previous_gaps_count=5,
        )
        converged, score = ev.evaluate(sig)
        assert converged is True
        assert score >= 0.5


# ---------------------------------------------------------------------------
# Hysteresis
# ---------------------------------------------------------------------------

class TestHysteresis:
    """Once convergence threshold is crossed, hysteresis prevents oscillation."""

    def test_hysteresis_sticky_convergence(self):
        """After converging, small drop doesn't un-converge due to hysteresis."""
        ev = ConvergenceEvaluator(threshold=0.75, hysteresis_margin=0.1)

        # First call: converge with high score
        sig_high = ConvergenceSignals(
            coverage_pct=1.0,
            confidence_delta=0.0,
            iteration_number=8,
            max_iterations=10,
            skip_rate=0.5,
            avg_response_time_sec=30.0,
            new_gaps_count=0,
            previous_gaps_count=5,
        )
        converged1, score1 = ev.evaluate(sig_high)
        assert converged1 is True

        # Second call: slightly lower score that would normally not converge
        # but hysteresis keeps it converged (effective threshold = 0.75 - 0.1 = 0.65)
        # coverage=0.8 => 0.24, plateau(0.02)=0.8 => 0.16, iter_cap=0.9 => 0.09,
        # fatigue=0.4 => 0.06, diminishing(1/5=0.2 => 0.8) => 0.20  total=0.75
        # But with lower coverage=0.75: 0.225+0.16+0.09+0.06+0.20 = 0.735
        # which is < 0.75 (normal threshold) but >= 0.65 (hysteresis threshold)
        sig_lower = ConvergenceSignals(
            coverage_pct=0.75,
            confidence_delta=0.02,
            iteration_number=9,
            max_iterations=10,
            skip_rate=0.2,
            avg_response_time_sec=15.0,
            new_gaps_count=1,
            previous_gaps_count=5,
        )
        converged2, score2 = ev.evaluate(sig_lower)
        # Score ~0.735: below 0.75 but above 0.65 (hysteresis-adjusted)
        assert converged2 is True

    def test_hysteresis_large_drop_unconverges(self):
        """A big enough drop overcomes hysteresis and un-converges."""
        ev = ConvergenceEvaluator(threshold=0.75, hysteresis_margin=0.1)

        # First: converge
        sig_high = ConvergenceSignals(
            coverage_pct=1.0,
            confidence_delta=0.0,
            iteration_number=8,
            max_iterations=10,
            skip_rate=0.5,
            avg_response_time_sec=30.0,
            new_gaps_count=0,
            previous_gaps_count=5,
        )
        converged1, _ = ev.evaluate(sig_high)
        assert converged1 is True

        # Second: drop significantly below effective threshold (0.65)
        sig_crash = ConvergenceSignals(
            coverage_pct=0.2,
            confidence_delta=0.1,
            iteration_number=9,
            max_iterations=10,
            skip_rate=0.0,
            avg_response_time_sec=5.0,
            new_gaps_count=8,
            previous_gaps_count=5,
        )
        converged2, score2 = ev.evaluate(sig_crash)
        assert converged2 is False
        assert score2 < 0.65


# ---------------------------------------------------------------------------
# from_org_config
# ---------------------------------------------------------------------------

class TestFromOrgConfig:
    """from_org_config classmethod creates evaluator from AnalysisConfig dict."""

    def test_from_org_config_with_weights(self):
        config = {
            "convergence_weights": {
                "coverage": 0.5,
                "confidence_plateau": 0.1,
                "iteration_cap": 0.1,
                "user_fatigue": 0.1,
                "diminishing_gaps": 0.2,
            },
            "convergence_threshold": 0.6,
        }
        ev = ConvergenceEvaluator.from_org_config(config)
        assert ev.weights.coverage == 0.5
        assert ev.threshold == 0.6

    def test_from_org_config_empty_uses_defaults(self):
        ev = ConvergenceEvaluator.from_org_config({})
        assert ev.weights.coverage == 0.30
        assert ev.threshold == 0.75

    def test_from_org_config_partial_weights(self):
        config = {
            "convergence_weights": {"coverage": 0.6},
        }
        ev = ConvergenceEvaluator.from_org_config(config)
        assert ev.weights.coverage == 0.6
        # Other weights retain defaults
        assert ev.weights.confidence_plateau == 0.20
