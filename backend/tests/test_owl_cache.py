"""Tests for OWL cache freshness checking, atomic download, and rollback."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestEnsureOwlFresh:
    """Tests for ensure_owl_fresh() ETag-based freshness checking."""

    def test_304_response_returns_false(self, tmp_path: Path):
        """When server returns 304 Not Modified, ensure_owl_fresh returns False (no download)."""
        from app.services.folio.owl_cache import ensure_owl_fresh

        cache_dir = tmp_path / "folio_cache"
        cache_dir.mkdir()
        owl_file = cache_dir / "folio.owl"
        owl_file.write_text("<Ontology/>")
        meta_file = cache_dir / "folio.meta.json"
        meta_file.write_text(json.dumps({"etag": "abc123"}))

        mock_response = MagicMock()
        mock_response.status_code = 304

        with patch("app.services.folio.owl_cache.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.head.return_value = mock_response
            mock_client_cls.return_value = mock_client

            result = ensure_owl_fresh(branch="main", cache_dir=cache_dir)

        assert result is False

    def test_200_response_downloads_validates_and_writes(self, tmp_path: Path):
        """When server returns 200, downloads, validates XML, and writes atomically."""
        from app.services.folio.owl_cache import ensure_owl_fresh

        cache_dir = tmp_path / "folio_cache"
        cache_dir.mkdir()

        valid_xml = b'<?xml version="1.0"?><Ontology xmlns="http://www.w3.org/2002/07/owl#"/>'

        mock_head_resp = MagicMock()
        mock_head_resp.status_code = 200
        mock_head_resp.headers = {"etag": '"new-etag-value"'}

        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 200
        mock_get_resp.content = valid_xml
        mock_get_resp.raise_for_status = MagicMock()

        with patch("app.services.folio.owl_cache.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.head.return_value = mock_head_resp
            mock_client.get.return_value = mock_get_resp
            mock_client_cls.return_value = mock_client

            result = ensure_owl_fresh(branch="main", cache_dir=cache_dir)

        assert result is True
        owl_file = cache_dir / "folio.owl"
        assert owl_file.exists()
        assert owl_file.read_bytes() == valid_xml

    def test_backs_up_previous_owl_file(self, tmp_path: Path):
        """When a cached OWL file exists, it is backed up to .previous before replacing."""
        from app.services.folio.owl_cache import ensure_owl_fresh

        cache_dir = tmp_path / "folio_cache"
        cache_dir.mkdir()
        owl_file = cache_dir / "folio.owl"
        old_content = b"<OldOntology/>"
        owl_file.write_bytes(old_content)

        valid_xml = b'<?xml version="1.0"?><Ontology xmlns="http://www.w3.org/2002/07/owl#"/>'

        mock_head_resp = MagicMock()
        mock_head_resp.status_code = 200
        mock_head_resp.headers = {"etag": '"new-etag"'}

        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 200
        mock_get_resp.content = valid_xml
        mock_get_resp.raise_for_status = MagicMock()

        with patch("app.services.folio.owl_cache.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.head.return_value = mock_head_resp
            mock_client.get.return_value = mock_get_resp
            mock_client_cls.return_value = mock_client

            ensure_owl_fresh(branch="main", cache_dir=cache_dir)

        previous_file = cache_dir / "folio.owl.previous"
        assert previous_file.exists()
        assert previous_file.read_bytes() == old_content


class TestGetOwlStatus:
    """Tests for get_owl_status() status reporting."""

    def test_returns_expected_keys(self, tmp_path: Path):
        """get_owl_status returns dict with keys: cached, etag, last_checked, content_hash."""
        from app.services.folio.owl_cache import get_owl_status

        cache_dir = tmp_path / "folio_cache"
        cache_dir.mkdir()

        status = get_owl_status(cache_dir=cache_dir)

        assert "cached" in status
        assert "etag" in status
        assert "last_checked" in status
        assert "content_hash" in status

    def test_cached_true_when_owl_exists(self, tmp_path: Path):
        """When OWL file exists, cached is True and content_hash is populated."""
        from app.services.folio.owl_cache import get_owl_status

        cache_dir = tmp_path / "folio_cache"
        cache_dir.mkdir()
        owl_file = cache_dir / "folio.owl"
        owl_file.write_text("<Ontology/>")
        meta_file = cache_dir / "folio.meta.json"
        meta_file.write_text(json.dumps({"etag": "test-etag", "last_checked": "2026-01-01T00:00:00Z"}))

        status = get_owl_status(cache_dir=cache_dir)

        assert status["cached"] is True
        assert status["etag"] == "test-etag"
        assert status["last_checked"] == "2026-01-01T00:00:00Z"
        assert status["content_hash"] is not None
        assert len(status["content_hash"]) > 0


class TestRollbackOwl:
    """Tests for rollback_owl() version rollback."""

    def test_restores_previous_owl(self, tmp_path: Path):
        """rollback_owl restores the .previous file back to .owl."""
        from app.services.folio.owl_cache import rollback_owl

        cache_dir = tmp_path / "folio_cache"
        cache_dir.mkdir()
        owl_file = cache_dir / "folio.owl"
        owl_file.write_text("<CurrentOntology/>")
        previous_file = cache_dir / "folio.owl.previous"
        previous_file.write_text("<PreviousOntology/>")

        result = rollback_owl(cache_dir=cache_dir)

        assert result is True
        assert owl_file.read_text() == "<PreviousOntology/>"

    def test_returns_false_when_no_previous(self, tmp_path: Path):
        """rollback_owl returns False when no .previous file exists."""
        from app.services.folio.owl_cache import rollback_owl

        cache_dir = tmp_path / "folio_cache"
        cache_dir.mkdir()

        result = rollback_owl(cache_dir=cache_dir)

        assert result is False
