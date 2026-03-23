"""Tests for database backend engine factory abstraction.

Covers:
- SQLite engine creation
- PostgreSQL engine URL format
- Unsupported backend raises ValueError
"""

from unittest.mock import patch

import pytest

from app.config import Settings


def _make_settings(**overrides) -> Settings:
    """Create test settings with sensible defaults."""
    defaults = {
        "secret_key": "test-secret",
        "database_backend": "sqlite",
        "sqlite_path": ":memory:",
    }
    defaults.update(overrides)
    return Settings(**defaults)


class TestSQLiteEngineCreation:
    """Test SQLite engine creation via the engine factory."""

    def test_sqlite_engine_creation(self):
        """With database_backend='sqlite', engine URL starts with 'sqlite+aiosqlite'."""
        from app.db.engine import create_engine

        settings = _make_settings(database_backend="sqlite", sqlite_path="/tmp/test.db")

        with patch("app.db.engine.get_settings", return_value=settings):
            engine = create_engine()

        assert "sqlite+aiosqlite" in str(engine.url)


class TestPostgreSQLEngineURL:
    """Test PostgreSQL engine URL format."""

    def test_postgresql_engine_url_format(self):
        """With database_backend='postgresql', engine URL starts with 'postgresql+asyncpg'."""
        from app.db.engine import create_engine

        settings = _make_settings(
            database_backend="postgresql",
            db_host="localhost",
            db_port=5432,
            db_name="testdb",
            db_user="testuser",
            db_password="testpass",
        )

        with patch("app.db.engine.get_settings", return_value=settings):
            engine = create_engine()

        url_str = str(engine.url)
        assert url_str.startswith("postgresql+asyncpg")
        assert "testuser" in url_str
        assert "testdb" in url_str


class TestUnsupportedBackend:
    """Test that unsupported backends raise errors."""

    def test_unsupported_backend_raises(self):
        """With database_backend='mysql' -> ValueError."""
        # The DatabaseBackend enum should reject 'mysql' during Settings validation
        with pytest.raises(Exception):
            _make_settings(database_backend="mysql")
