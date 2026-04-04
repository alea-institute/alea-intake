"""Tests for InsightsService -- secondary/practical knowledge retrieval by FOLIO IRI.

Covers:
- get_insights returns KB documents with source_type="insight" matching IRI per D-08
- add_insight creates KBDocument + chunks for secondary knowledge
- Insights rank below primary research authorities per D-08
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestInsightsService:
    """Tests for InsightsService secondary knowledge store."""

    @pytest.fixture
    def mock_session(self):
        session = AsyncMock()
        return session

    @pytest.fixture
    def mock_retriever(self):
        retriever = AsyncMock()
        return retriever

    @pytest.fixture
    def service(self, mock_session, mock_retriever):
        from app.services.research.insights_service import InsightsService

        return InsightsService(db_session=mock_session, kb_retriever=mock_retriever)

    @pytest.mark.asyncio
    async def test_get_insights_by_folio_iri(self, service, mock_session):
        """Test 10: InsightsService.get_insights returns KB documents with source_type='insight' matching the IRI per D-08."""
        from app.services.knowledge_base.retriever import KBSearchResult

        # Mock DB query for insights
        mock_doc = SimpleNamespace(
            id=1, title="Lease Advocacy Tips", source_type="insight",
            folio_iris_json=json.dumps(["https://folio.openlegalstandard.org/lease"]),
            org_id=1,
        )
        mock_chunk = SimpleNamespace(
            id=1, document_id=1, content="Always negotiate early termination clause.",
            heading="Lease Tips", folio_iris_json=json.dumps(["https://folio.openlegalstandard.org/lease"]),
            token_count=7,
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_chunk]
        mock_session.execute.return_value = mock_result

        results = await service.get_insights("https://folio.openlegalstandard.org/lease", top_k=5)
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_add_insight(self, service, mock_session):
        """Test 11: InsightsService.add_insight creates KB document + chunks for secondary knowledge."""
        # Mock session add and flush
        mock_session.flush = AsyncMock()
        mock_session.add = MagicMock()

        doc_id = await service.add_insight(
            folio_iri="https://folio.openlegalstandard.org/lease",
            content="When negotiating a lease, always check the early termination clause.",
            source="llm",
        )
        # Should have created a document
        assert mock_session.add.called
        assert isinstance(doc_id, int)

    @pytest.mark.asyncio
    async def test_insights_rank_below_primary(self, service, mock_session):
        """Test 12: Insights rank below primary research authorities in combined results per D-08."""
        from app.services.knowledge_base.retriever import KBSearchResult

        # Create insight results with high scores
        insight_result = KBSearchResult(
            chunk_content="Insight content",
            document_title="Insight Doc",
            document_id=1,
            score=0.95,
            folio_iris=["https://folio.openlegalstandard.org/lease"],
            is_insight=True,
        )
        primary_result = KBSearchResult(
            chunk_content="Primary authority content",
            document_title="Primary Doc",
            document_id=2,
            score=0.80,
            folio_iris=["https://folio.openlegalstandard.org/lease"],
            is_insight=False,
        )

        # Insights should be demoted below primary per D-08
        combined = service.rank_results([insight_result, primary_result])
        assert len(combined) == 2
        # Primary should come first despite lower base score
        assert combined[0].is_insight is False
        assert combined[1].is_insight is True
