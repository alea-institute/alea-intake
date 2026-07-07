"""Tests for the multi-stage concept resolution pipeline."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.embedding.backends import SearchResult


# ---------------------------------------------------------------------------
# ResolvedConcept / ConceptResolutionConfig dataclass tests
# ---------------------------------------------------------------------------


class TestResolvedConceptDataclass:
    """Tests for ResolvedConcept dataclass shape."""

    def test_resolved_concept_fields(self):
        """ResolvedConcept has required fields."""
        from app.services.folio.concept_resolver import ResolvedConcept

        rc = ResolvedConcept(
            iri="https://folio.openlegalstandard.org/objective001",
            label="Wrongful Termination Claim",
            branch="Objectives",
            confidence=0.85,
            source="embedding",
            matched_text="I was fired from my job",
        )
        assert rc.iri == "https://folio.openlegalstandard.org/objective001"
        assert rc.label == "Wrongful Termination Claim"
        assert rc.branch == "Objectives"
        assert rc.confidence == 0.85
        assert rc.source == "embedding"
        assert rc.matched_text == "I was fired from my job"
        assert rc.is_unmapped is False
        assert rc.reason == ""

    def test_concept_resolution_config_defaults(self):
        """ConceptResolutionConfig has sensible defaults."""
        from app.services.folio.concept_resolver import ConceptResolutionConfig

        config = ConceptResolutionConfig()
        assert config.confidence_threshold == 0.5
        assert config.high_confidence_threshold == 0.85
        assert config.max_embedding_candidates == 20
        assert config.max_label_results == 10
        assert config.max_llm_results == 10
        assert config.enable_llm_stage is True


# ---------------------------------------------------------------------------
# resolve_concepts pipeline tests
# ---------------------------------------------------------------------------


def _make_mock_embedding_service(results: list[SearchResult] | None = None):
    """Create a mock EmbeddingService that returns given SearchResults."""
    svc = AsyncMock()
    svc.search = AsyncMock(return_value=results or [])
    return svc


def _make_owl_class(iri: str, label: str, sub_class_of: list[str] | None = None):
    """Create a mock OWLClass-like object."""
    cls = MagicMock()
    cls.iri = iri
    cls.label = label
    cls.sub_class_of = sub_class_of or []
    cls.alternative_labels = []
    cls.definition = f"Definition of {label}"
    return cls


class TestResolveConceptsPipeline:
    """Tests for the resolve_concepts multi-stage pipeline."""

    @pytest.mark.asyncio
    async def test_high_confidence_embedding_skips_llm(self, mock_folio):
        """When embedding returns high-confidence match, LLM stage is skipped."""
        from app.services.folio.concept_resolver import ConceptResolutionConfig, resolve_concepts

        emb_service = _make_mock_embedding_service([
            SearchResult(
                iri="https://folio.openlegalstandard.org/objective001",
                label="Wrongful Termination Claim",
                score=0.92,
                metadata={"branch": "Objectives"},
            ),
        ])

        config = ConceptResolutionConfig(enable_llm_stage=True)
        mock_llm = MagicMock()

        results = await resolve_concepts(
            text="I was wrongfully fired from my job",
            folio=mock_folio,
            embedding_service=emb_service,
            config=config,
            llm_model=mock_llm,
        )

        # LLM should NOT have been called since embedding score > 0.85
        mock_folio.parallel_search_by_llm.assert_not_called()
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_low_confidence_invokes_llm(self, mock_folio):
        """When no high-confidence match, LLM stage is invoked."""
        from app.services.folio.concept_resolver import ConceptResolutionConfig, resolve_concepts

        emb_service = _make_mock_embedding_service([
            SearchResult(
                iri="https://folio.openlegalstandard.org/objective001",
                label="Wrongful Termination Claim",
                score=0.45,
                metadata={"branch": "Objectives"},
            ),
        ])

        # Mock LLM search to return an OWLClass
        llm_result = _make_owl_class(
            "https://folio.openlegalstandard.org/objective001",
            "Wrongful Termination Claim",
        )
        llm_result.relevance = 8
        llm_result.reason = "Employment termination scenario"
        mock_folio.parallel_search_by_llm = AsyncMock(return_value=[llm_result])

        config = ConceptResolutionConfig(enable_llm_stage=True)
        mock_llm = MagicMock()

        results = await resolve_concepts(
            text="I was wrongfully fired from my job",
            folio=mock_folio,
            embedding_service=emb_service,
            config=config,
            llm_model=mock_llm,
        )

        mock_folio.parallel_search_by_llm.assert_called_once()

    @pytest.mark.asyncio
    async def test_term_expansion_used(self, mock_folio):
        """resolve_concepts applies term expansions before label search."""
        from app.services.folio.concept_resolver import resolve_concepts

        emb_service = _make_mock_embedding_service()

        with patch(
            "app.services.folio.concept_resolver.expand_legal_terms",
            return_value=["wrongful termination", "employment termination", "discharge"],
        ) as mock_expand:
            results = await resolve_concepts(
                text="fired",
                folio=mock_folio,
                embedding_service=emb_service,
            )
            mock_expand.assert_called_once()

    @pytest.mark.asyncio
    async def test_results_sorted_by_confidence(self, mock_folio):
        """Results are sorted by confidence descending."""
        from app.services.folio.concept_resolver import resolve_concepts

        emb_service = _make_mock_embedding_service([
            SearchResult(
                iri="https://folio.openlegalstandard.org/objective001",
                label="Wrongful Termination Claim",
                score=0.7,
                metadata={"branch": "Objectives"},
            ),
            SearchResult(
                iri="https://folio.openlegalstandard.org/objective002",
                label="Breach of Contract",
                score=0.9,
                metadata={"branch": "Objectives"},
            ),
        ])

        results = await resolve_concepts(
            text="I was fired and my contract was violated",
            folio=mock_folio,
            embedding_service=emb_service,
        )

        if len(results) >= 2:
            assert results[0].confidence >= results[1].confidence

    @pytest.mark.asyncio
    async def test_confidence_threshold_filters(self, mock_folio):
        """Results below confidence_threshold are filtered out."""
        from app.services.folio.concept_resolver import ConceptResolutionConfig, resolve_concepts

        emb_service = _make_mock_embedding_service([
            SearchResult(
                iri="https://folio.openlegalstandard.org/objective001",
                label="Wrongful Termination Claim",
                score=0.9,
                metadata={"branch": "Objectives"},
            ),
            SearchResult(
                iri="https://folio.openlegalstandard.org/objective002",
                label="Breach of Contract",
                score=0.2,
                metadata={"branch": "Objectives"},
            ),
        ])

        config = ConceptResolutionConfig(confidence_threshold=0.6)
        results = await resolve_concepts(
            text="wrongful termination",
            folio=mock_folio,
            embedding_service=emb_service,
            config=config,
        )

        # All results should be above threshold
        for r in results:
            assert r.confidence >= 0.6

    @pytest.mark.asyncio
    async def test_empty_text_returns_empty(self, mock_folio):
        """resolve_concepts('') returns empty list."""
        from app.services.folio.concept_resolver import resolve_concepts

        emb_service = _make_mock_embedding_service()
        results = await resolve_concepts(
            text="",
            folio=mock_folio,
            embedding_service=emb_service,
        )
        assert results == []

    @pytest.mark.asyncio
    async def test_stopword_only_text_returns_empty(self, mock_folio):
        """resolve_concepts with only stopwords returns empty list."""
        from app.services.folio.concept_resolver import resolve_concepts

        emb_service = _make_mock_embedding_service()
        results = await resolve_concepts(
            text="the is a an",
            folio=mock_folio,
            embedding_service=emb_service,
        )
        assert results == []


# ---------------------------------------------------------------------------
# combine_scores tests
# ---------------------------------------------------------------------------


class TestCombineScores:
    """Tests for score normalization and combination."""

    def test_combine_scores_normalization(self):
        """Embedding 0.8, label 80/100, LLM 8/10 produce combined ~0.8."""
        from app.services.folio.concept_resolver import _combine_score

        # All three stages present with equivalent values
        score = _combine_score(
            embedding_score=0.8,
            label_score=0.8,  # already normalized to 0-1
            llm_score=0.8,  # already normalized to 0-1
        )
        assert 0.7 <= score <= 0.9

    def test_combine_scores_weights(self):
        """Weights: embedding 0.3, label 0.3, LLM 0.4."""
        from app.services.folio.concept_resolver import (
            EMBEDDING_WEIGHT,
            LABEL_WEIGHT,
            LLM_WEIGHT,
        )

        assert EMBEDDING_WEIGHT == pytest.approx(0.3)
        assert LABEL_WEIGHT == pytest.approx(0.3)
        assert LLM_WEIGHT == pytest.approx(0.4)

    def test_single_stage_score_penalized(self):
        """Concept from only one stage gets a penalty."""
        from app.services.folio.concept_resolver import _combine_score

        # Only embedding, no label or LLM
        single = _combine_score(embedding_score=0.9, label_score=None, llm_score=None)
        # Multi-stage same score
        multi = _combine_score(embedding_score=0.9, label_score=0.9, llm_score=0.9)
        assert single < multi


# ---------------------------------------------------------------------------
# persist_resolutions tests
# ---------------------------------------------------------------------------


class TestPersistResolutions:
    """Tests for persisting ResolvedConcept records to DB."""

    @pytest.mark.asyncio
    async def test_persist_resolutions_creates_mappings(self, async_session):
        """persist_resolutions creates ConceptMapping records in DB session."""
        from app.services.folio.concept_resolver import ResolvedConcept, persist_resolutions

        resolutions = [
            ResolvedConcept(
                iri="https://folio.openlegalstandard.org/objective001",
                label="Wrongful Termination Claim",
                branch="Objectives",
                confidence=0.85,
                source="combined",
                matched_text="I was fired",
                reason="Employment issue",
            ),
            ResolvedConcept(
                iri="https://folio.openlegalstandard.org/areaoflaw001",
                label="Employment Law",
                branch="Area of Law",
                confidence=0.72,
                source="embedding",
                matched_text="I was fired",
            ),
        ]

        mappings = await persist_resolutions(
            session=async_session,
            intake_id=1,
            resolutions=resolutions,
        )

        assert len(mappings) == 2
        assert mappings[0].iri == "https://folio.openlegalstandard.org/objective001"
        assert mappings[0].confidence == 0.85
        assert mappings[0].source == "combined"
        assert mappings[0].intake_id == 1
        assert mappings[1].iri == "https://folio.openlegalstandard.org/areaoflaw001"


class TestResolverStageResilience:
    """BUG-9: a failing embedding backend must not kill the deterministic cascade."""

    @pytest.mark.asyncio
    async def test_embedding_failure_degrades_to_label_stage(self, mock_folio):
        """resolve_concepts still returns label-stage matches when embeddings raise."""
        from app.services.folio.concept_resolver import (
            ConceptResolutionConfig,
            resolve_concepts,
        )

        emb_service = AsyncMock()
        emb_service.search = AsyncMock(
            side_effect=RuntimeError('relation "shared.folio_embeddings" does not exist')
        )

        config = ConceptResolutionConfig(enable_llm_stage=False)
        results = await resolve_concepts(
            text="Wrongful Termination Claim",
            folio=mock_folio,
            embedding_service=emb_service,
            config=config,
        )

        # The label/prefix stage matched despite the dead embedding stage.
        assert len(results) > 0
        assert any("objective001" in r.iri for r in results)
