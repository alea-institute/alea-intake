"""Tests for analysis pipeline Pydantic schemas.

Validates LLM I/O contracts: literal field constraints, required fields,
default values, and JSON round-trip serialization for DB storage.
"""

import json

import pytest
from pydantic import ValidationError

from app.services.analysis.schemas import (
    AnalysisConfig,
    ClaimElementSchema,
    ConfidenceWeights,
    ConvergenceSignals,
    ConvergenceWeights,
    FactMapResult,
    FactMappingSchema,
    GapAnalysisResult,
    GapSchema,
    IssueSpotResult,
    OrchestratorDecision,
    QuestionGenResult,
    QuestionGroup,
    QuestionSchema,
    SpottedClaim,
)


class TestOrchestratorDecision:
    """OrchestratorDecision validates next_stage literal."""

    def test_valid_stages(self):
        for stage in ["issue_spot", "research", "fact_map", "gap_analyze", "question", "converge"]:
            decision = OrchestratorDecision(
                next_stage=stage,
                reasoning="Test reasoning",
            )
            assert decision.next_stage == stage

    def test_invalid_stage_rejected(self):
        with pytest.raises(ValidationError):
            OrchestratorDecision(
                next_stage="invalid_stage",
                reasoning="Test",
            )

    def test_skip_stages_default_empty(self):
        decision = OrchestratorDecision(
            next_stage="issue_spot",
            reasoning="Start with issue spotting",
        )
        assert decision.skip_stages == []

    def test_skip_stages_populated(self):
        decision = OrchestratorDecision(
            next_stage="gap_analyze",
            reasoning="Skip research in iteration 2",
            skip_stages=["research"],
        )
        assert decision.skip_stages == ["research"]


class TestSpottedClaim:
    """SpottedClaim requires claim_name and confidence."""

    def test_valid_claim(self):
        claim = SpottedClaim(
            claim_name="Wrongful Termination",
            claim_type="identified",
            confidence=0.85,
            rationale="Consumer described being fired without cause",
        )
        assert claim.claim_name == "Wrongful Termination"
        assert claim.confidence == 0.85

    def test_missing_claim_name_rejected(self):
        with pytest.raises(ValidationError):
            SpottedClaim(
                claim_type="identified",
                confidence=0.85,
                rationale="Test",
            )

    def test_missing_confidence_rejected(self):
        with pytest.raises(ValidationError):
            SpottedClaim(
                claim_name="Test Claim",
                claim_type="identified",
                rationale="Test",
            )

    def test_invalid_claim_type_rejected(self):
        with pytest.raises(ValidationError):
            SpottedClaim(
                claim_name="Test",
                claim_type="unknown",
                confidence=0.5,
                rationale="Test",
            )

    def test_confidence_bounds(self):
        with pytest.raises(ValidationError):
            SpottedClaim(
                claim_name="Test",
                claim_type="identified",
                confidence=1.5,
                rationale="Test",
            )

    def test_is_potential_default_false(self):
        claim = SpottedClaim(
            claim_name="Test",
            claim_type="discovered",
            confidence=0.6,
            rationale="Discovered via FOLIO adjacency",
        )
        assert claim.is_potential is False

    def test_elements_default_empty(self):
        claim = SpottedClaim(
            claim_name="Test",
            claim_type="identified",
            confidence=0.8,
            rationale="Test",
        )
        assert claim.elements == []

    def test_elements_populated(self):
        claim = SpottedClaim(
            claim_name="Wrongful Termination",
            claim_type="identified",
            confidence=0.85,
            rationale="Test",
            elements=[
                ClaimElementSchema(element_name="Employment Relationship"),
                ClaimElementSchema(
                    element_name="Termination Without Cause",
                    element_description="Employer must have fired without legal justification",
                    jurisdiction="California",
                ),
            ],
        )
        assert len(claim.elements) == 2
        assert claim.elements[1].jurisdiction == "California"


class TestIssueSpotResult:
    """IssueSpotResult contains claims and jurisdictions."""

    def test_valid_result(self):
        result = IssueSpotResult(
            claims=[
                SpottedClaim(
                    claim_name="Wrongful Termination",
                    claim_type="identified",
                    confidence=0.85,
                    rationale="Test",
                ),
            ],
            jurisdictions=["California", "Federal"],
            summary="Consumer appears to have employment-related claims",
        )
        assert len(result.claims) == 1
        assert "California" in result.jurisdictions


class TestGapSchema:
    """GapSchema validates gap_type literal (4 allowed values)."""

    def test_valid_gap_types(self):
        valid_types = [
            "unsupported_element",
            "unexplored_claim",
            "weak_mapping",
            "procedural_requirement",
        ]
        for gap_type in valid_types:
            gap = GapSchema(
                gap_type=gap_type,
                description=f"Test gap: {gap_type}",
                priority=1,
            )
            assert gap.gap_type == gap_type

    def test_invalid_gap_type_rejected(self):
        with pytest.raises(ValidationError):
            GapSchema(
                gap_type="invalid_type",
                description="Test",
                priority=1,
            )

    def test_optional_claim_and_element(self):
        gap = GapSchema(
            gap_type="unsupported_element",
            claim_name="Wrongful Termination",
            element_name="Causation",
            description="No facts support causation element",
            priority=2,
        )
        assert gap.claim_name == "Wrongful Termination"
        assert gap.element_name == "Causation"


class TestFactMapping:
    """FactMappingSchema and FactMapResult validation."""

    def test_valid_mapping(self):
        mapping = FactMappingSchema(
            fact_id=42,
            claim_name="Wrongful Termination",
            element_name="Employment Relationship",
            llm_confidence=0.88,
            mapping_rationale="Fact describes 5-year employment",
        )
        assert mapping.fact_id == 42
        assert mapping.llm_confidence == 0.88

    def test_fact_map_result(self):
        result = FactMapResult(
            mappings=[
                FactMappingSchema(
                    fact_id=1,
                    claim_name="Test Claim",
                    llm_confidence=0.9,
                    mapping_rationale="Test",
                ),
            ],
            unmapped_facts=[3, 5, 7],
        )
        assert len(result.mappings) == 1
        assert result.unmapped_facts == [3, 5, 7]


class TestQuestionGeneration:
    """QuestionGroup, QuestionSchema, and QuestionGenResult validation."""

    def test_question_group(self):
        group = QuestionGroup(
            topic="timeline",
            questions=[
                QuestionSchema(
                    question_text="When were you terminated?",
                    rationale="Need date for SOL calculation",
                    priority=1,
                ),
                QuestionSchema(
                    question_text="How long did you work there?",
                    priority=2,
                ),
            ],
        )
        assert group.topic == "timeline"
        assert len(group.questions) == 2
        assert group.questions[0].rationale is not None
        assert group.questions[1].rationale is None

    def test_question_gen_result(self):
        result = QuestionGenResult(
            groups=[
                QuestionGroup(
                    topic="timeline",
                    questions=[
                        QuestionSchema(question_text="When?", priority=1),
                    ],
                ),
            ],
            total_questions=1,
        )
        assert result.total_questions == 1


class TestConvergenceWeights:
    """ConvergenceWeights defaults sum to 1.0."""

    def test_defaults_sum_to_one(self):
        weights = ConvergenceWeights()
        total = (
            weights.coverage
            + weights.confidence_plateau
            + weights.iteration_cap
            + weights.user_fatigue
            + weights.diminishing_gaps
        )
        assert abs(total - 1.0) < 1e-9

    def test_custom_weights(self):
        weights = ConvergenceWeights(
            coverage=0.40,
            confidence_plateau=0.15,
            iteration_cap=0.10,
            user_fatigue=0.10,
            diminishing_gaps=0.25,
        )
        assert weights.coverage == 0.40
        assert weights.confidence_plateau == 0.15


class TestConfidenceWeights:
    """ConfidenceWeights defaults sum to 1.0."""

    def test_defaults_sum_to_one(self):
        weights = ConfidenceWeights()
        total = weights.llm_weight + weights.concept_weight + weights.fact_weight
        assert abs(total - 1.0) < 1e-9

    def test_custom_weights(self):
        weights = ConfidenceWeights(
            llm_weight=0.5,
            concept_weight=0.25,
            fact_weight=0.25,
        )
        assert weights.llm_weight == 0.5


class TestConvergenceSignals:
    """ConvergenceSignals validation."""

    def test_valid_signals(self):
        signals = ConvergenceSignals(
            coverage_pct=0.72,
            confidence_delta=0.03,
            iteration_number=3,
            max_iterations=10,
            skip_rate=0.1,
            avg_response_time_sec=45.2,
            new_gaps_count=2,
            previous_gaps_count=8,
        )
        assert signals.coverage_pct == 0.72
        assert signals.iteration_number == 3

    def test_coverage_bounds(self):
        with pytest.raises(ValidationError):
            ConvergenceSignals(
                coverage_pct=1.5,
                confidence_delta=0.0,
                iteration_number=1,
                max_iterations=10,
                skip_rate=0.0,
                avg_response_time_sec=30.0,
                new_gaps_count=0,
                previous_gaps_count=0,
            )


class TestAnalysisConfig:
    """AnalysisConfig round-trips to/from JSON for DB storage."""

    def test_defaults(self):
        config = AnalysisConfig()
        assert config.auto_trigger_enabled is True
        assert config.auto_trigger_fact_threshold == 5
        assert config.max_iterations == 10
        assert config.convergence_threshold == 0.75
        assert config.question_transparency is True

    def test_nested_defaults(self):
        config = AnalysisConfig()
        assert config.convergence_weights.coverage == 0.30
        assert config.confidence_weights.llm_weight == 0.4

    def test_json_round_trip(self):
        config = AnalysisConfig(
            auto_trigger_enabled=False,
            max_iterations=5,
            convergence_threshold=0.80,
            convergence_weights=ConvergenceWeights(coverage=0.40, diminishing_gaps=0.15),
        )

        # Serialize to JSON (as it would be stored in DB JSON column)
        json_str = config.model_dump_json()
        assert isinstance(json_str, str)

        # Deserialize back
        restored = AnalysisConfig.model_validate_json(json_str)
        assert restored.auto_trigger_enabled is False
        assert restored.max_iterations == 5
        assert restored.convergence_threshold == 0.80
        assert restored.convergence_weights.coverage == 0.40
        assert restored.convergence_weights.diminishing_gaps == 0.15

    def test_dict_round_trip(self):
        """Dict serialization for DB JSON column storage."""
        config = AnalysisConfig()
        data = config.model_dump()
        assert isinstance(data, dict)

        restored = AnalysisConfig.model_validate(data)
        assert restored.max_iterations == 10

    def test_from_json_string(self):
        """Parse from raw JSON string (e.g., from DB)."""
        raw = json.dumps({
            "auto_trigger_enabled": True,
            "max_iterations": 8,
            "convergence_threshold": 0.65,
        })
        config = AnalysisConfig.model_validate_json(raw)
        assert config.max_iterations == 8
        assert config.convergence_threshold == 0.65
        # Defaults for unspecified fields
        assert config.convergence_weights.coverage == 0.30


class TestGapAnalysisResult:
    """GapAnalysisResult validation."""

    def test_valid_result(self):
        result = GapAnalysisResult(
            gaps=[
                GapSchema(
                    gap_type="unsupported_element",
                    claim_name="Wrongful Termination",
                    element_name="Causation",
                    description="No supporting facts",
                    priority=1,
                ),
            ],
            coverage_pct=0.65,
            summary="Analysis has gaps in causation evidence",
        )
        assert len(result.gaps) == 1
        assert result.coverage_pct == 0.65
