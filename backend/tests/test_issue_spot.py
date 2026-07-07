"""Tests for the issue-spotting stage prompt (GATE-01 / RUB-INTAKE-01).

Validates that ISSUE_SPOT_SYSTEM_PROMPT instructs the model to surface latent,
unspoken relief issues raised by the facts, while preserving the JSON output
contract and the no-fabrication guardrail (RUB-04).
"""

from __future__ import annotations


def test_prompt_preserves_json_output_contract():
    """BUG-6 lesson: prompt must still contain the word 'json' and the schema keys."""
    from app.services.analysis.stages.issue_spot import ISSUE_SPOT_SYSTEM_PROMPT

    lowered = ISSUE_SPOT_SYSTEM_PROMPT.lower()
    assert "json" in lowered
    assert "claims" in lowered
    assert "jurisdictions" in lowered
    assert "summary" in lowered


def test_prompt_contains_latent_issue_guidance():
    """GATE-01: prompt instructs surfacing latent/unspoken issues the facts raise."""
    from app.services.analysis.stages.issue_spot import ISSUE_SPOT_SYSTEM_PROMPT

    lowered = ISSUE_SPOT_SYSTEM_PROMPT.lower()
    # General instruction to surface unspoken issues.
    assert "latent" in lowered
    assert "unspoken" in lowered or "did not name" in lowered


def test_prompt_covers_required_latent_triggers():
    """GATE-01: the checklist covers the specific non-obvious relief issues missed."""
    from app.services.analysis.stages.issue_spot import ISSUE_SPOT_SYSTEM_PROMPT

    lowered = ISSUE_SPOT_SYSTEM_PROMPT.lower()
    for marker in (
        "vawa",
        "u-visa",
        "t-visa",
        "in-absentia",
        "motion to reopen",
        "order for protection",
        "warranty of habitability",
        "abduction",
    ):
        assert marker in lowered, f"missing latent-issue trigger: {marker}"


def test_prompt_keeps_no_fabrication_guardrail():
    """RUB-04: prompt must forbid fabricating issues unsupported by the facts."""
    from app.services.analysis.stages.issue_spot import ISSUE_SPOT_SYSTEM_PROMPT

    lowered = ISSUE_SPOT_SYSTEM_PROMPT.lower()
    assert "fabricate" in lowered or "do not fabricate" in lowered
    assert "fairly raise" in lowered or "fairly raised" in lowered
