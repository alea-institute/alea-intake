"""Tests for FOLIO singleton service (get_folio, reload_folio, reset_folio)."""

from unittest.mock import MagicMock, patch

import pytest


class TestGetFolio:
    """Tests for get_folio() singleton behavior."""

    def setup_method(self):
        """Reset singleton before each test."""
        from app.services.folio.folio_service import reset_folio
        reset_folio()

    def teardown_method(self):
        """Reset singleton after each test."""
        from app.services.folio.folio_service import reset_folio
        reset_folio()

    def test_returns_folio_instance(self):
        """get_folio() returns a FOLIO instance (mocked)."""
        from app.services.folio.folio_service import get_folio

        mock_folio = MagicMock()
        with patch("app.services.folio.folio_service.FOLIO", return_value=mock_folio):
            result = get_folio()

        assert result is mock_folio

    def test_returns_same_instance_on_second_call(self):
        """get_folio() returns the same instance on second call (singleton)."""
        from app.services.folio.folio_service import get_folio

        mock_folio = MagicMock()
        with patch("app.services.folio.folio_service.FOLIO", return_value=mock_folio):
            first = get_folio()
            second = get_folio()

        assert first is second

    def test_reload_replaces_singleton(self):
        """reload_folio(new_instance) replaces the singleton."""
        from app.services.folio.folio_service import get_folio, reload_folio

        mock_folio_1 = MagicMock()
        mock_folio_2 = MagicMock()

        with patch("app.services.folio.folio_service.FOLIO", return_value=mock_folio_1):
            first = get_folio()

        assert first is mock_folio_1

        reload_folio(mock_folio_2)

        with patch("app.services.folio.folio_service.FOLIO", return_value=mock_folio_1):
            current = get_folio()

        assert current is mock_folio_2


class TestTermExpansions:
    """Tests for legal term expansions and branch signal words."""

    def test_legal_term_expansions_has_at_least_20_entries(self):
        """LEGAL_TERM_EXPANSIONS has at least 20 entries."""
        from app.services.folio.term_expansions import LEGAL_TERM_EXPANSIONS

        assert isinstance(LEGAL_TERM_EXPANSIONS, dict)
        assert len(LEGAL_TERM_EXPANSIONS) >= 20

    def test_branch_signal_words_has_branch_mappings(self):
        """BRANCH_SIGNAL_WORDS maps FOLIO branch names to signal word lists."""
        from app.services.folio.term_expansions import BRANCH_SIGNAL_WORDS

        assert isinstance(BRANCH_SIGNAL_WORDS, dict)
        assert len(BRANCH_SIGNAL_WORDS) >= 10
        for key, value in BRANCH_SIGNAL_WORDS.items():
            assert isinstance(key, str)
            assert isinstance(value, list)

    def test_expand_legal_terms_fired_from_job(self):
        """expand_legal_terms("fired from my job") returns expansions including "wrongful termination"."""
        from app.services.folio.term_expansions import expand_legal_terms

        results = expand_legal_terms("fired from my job")

        assert isinstance(results, list)
        assert len(results) > 0
        # At least one expansion should contain "wrongful termination"
        all_text = " ".join(results).lower()
        assert "wrongful termination" in all_text


class TestFolioSettings:
    """Tests for FOLIO-related settings in config."""

    def test_settings_has_folio_fields(self):
        """Settings has folio_owl_branch, folio_update_interval_hours, folio_cache_dir."""
        from app.config import Settings

        # Check that the fields exist with correct defaults
        fields = Settings.model_fields
        assert "folio_owl_branch" in fields
        assert "folio_update_interval_hours" in fields
        assert "folio_cache_dir" in fields

    def test_settings_folio_defaults(self):
        """Settings has correct default values for FOLIO config."""
        s = _make_test_settings()

        assert s.folio_owl_branch == "main"
        assert s.folio_update_interval_hours == 24
        assert s.folio_cache_dir == "./data/folio_cache"


class TestFolioConceptModels:
    """Tests for FOLIO concept database models."""

    def test_concept_mapping_columns(self):
        """ConceptMapping has required columns."""
        from app.models.folio_concepts import ConceptMapping

        table = ConceptMapping.__table__
        col_names = {c.name for c in table.columns}

        assert "intake_id" in col_names
        assert "iri" in col_names
        assert "label" in col_names
        assert "branch" in col_names
        assert "confidence" in col_names
        assert "matched_text" in col_names
        assert "source" in col_names
        assert "is_unmapped" in col_names
        assert "metadata_json" in col_names

    def test_concept_graph_node_columns(self):
        """ConceptGraphNode has required columns."""
        from app.models.folio_concepts import ConceptGraphNode

        table = ConceptGraphNode.__table__
        col_names = {c.name for c in table.columns}

        assert "intake_id" in col_names
        assert "iri" in col_names
        assert "label" in col_names
        assert "branch" in col_names
        assert "is_unmapped" in col_names
        assert "confidence" in col_names
        assert "metadata_json" in col_names

    def test_concept_graph_edge_columns(self):
        """ConceptGraphEdge has required columns."""
        from app.models.folio_concepts import ConceptGraphEdge

        table = ConceptGraphEdge.__table__
        col_names = {c.name for c in table.columns}

        assert "intake_id" in col_names
        assert "source_iri" in col_names
        assert "target_iri" in col_names
        assert "relationship" in col_names
        assert "traversal_depth" in col_names

    def test_unmapped_concept_record_columns(self):
        """UnmappedConceptRecord has required columns."""
        from app.models.folio_concepts import UnmappedConceptRecord

        table = UnmappedConceptRecord.__table__
        col_names = {c.name for c in table.columns}

        assert "intake_id" in col_names
        assert "local_iri" in col_names
        assert "original_text" in col_names
        assert "suggested_branch" in col_names
        assert "unmapped_confidence" in col_names
        assert "nearest_iris" in col_names
        assert "org_id" in col_names
        assert "created_at" in col_names


def _make_test_settings():
    """Create test settings with required fields."""
    from app.config import Settings
    return Settings(
        secret_key="test-secret-key-for-testing-only",
        database_backend="sqlite",
        sqlite_path=":memory:",
    )
