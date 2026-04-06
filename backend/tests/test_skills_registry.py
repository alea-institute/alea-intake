"""Tests for Skills Registry and Marketplace Index."""

import asyncio
import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure skills bundled directory exists for registry tests
BACKEND_DIR = Path(__file__).parent.parent
SKILLS_BUNDLED_DIR = BACKEND_DIR / "app" / "skills" / "bundled"


class TestSkillsRegistryLoadBundled:
    """Test 1: SkillsRegistry.load_bundled() loads bundled skills."""

    def test_load_bundled_finds_dv_screening(self):
        from app.skills.registry import SkillsRegistry

        registry = SkillsRegistry()
        registry.load_bundled()
        skills = registry.list_skills()
        skill_names = [s.name for s in skills]
        assert "DV Screening Protocol" in skill_names

    def test_load_bundled_finds_general_intake(self):
        from app.skills.registry import SkillsRegistry

        registry = SkillsRegistry()
        registry.load_bundled()
        skills = registry.list_skills()
        skill_names = [s.name for s in skills]
        assert "General Intake Template" in skill_names

    def test_bundled_skills_marked_bundled(self):
        from app.skills.registry import SkillsRegistry

        registry = SkillsRegistry()
        registry.load_bundled()
        for skill in registry.list_skills():
            assert skill.bundled is True


class TestSkillsRegistryListSkills:
    """Test 2: SkillsRegistry.list_skills() returns Skill objects."""

    def test_list_skills_returns_skill_objects(self):
        from app.skills.registry import Skill, SkillsRegistry

        registry = SkillsRegistry()
        registry.load_bundled()
        skills = registry.list_skills()
        assert len(skills) >= 2
        for skill in skills:
            assert isinstance(skill, Skill)
            assert skill.name
            assert skill.description
            assert skill.skill_type
            assert skill.bundled is not None

    def test_list_skills_filter_by_type(self):
        from app.skills.registry import SkillsRegistry

        registry = SkillsRegistry()
        registry.load_bundled()
        screening_skills = registry.list_skills(skill_type="screening")
        assert len(screening_skills) >= 1
        for skill in screening_skills:
            assert skill.skill_type == "screening"


class TestSkillsRegistryGetSkill:
    """Test 3: SkillsRegistry.get_skill(name) returns skill content."""

    def test_get_existing_skill(self):
        from app.skills.registry import SkillsRegistry

        registry = SkillsRegistry()
        registry.load_bundled()
        skill = registry.get_skill("DV Screening Protocol")
        assert skill is not None
        assert skill.content  # non-empty Markdown content

    def test_get_nonexistent_skill(self):
        from app.skills.registry import SkillsRegistry

        registry = SkillsRegistry()
        registry.load_bundled()
        skill = registry.get_skill("Nonexistent Skill")
        assert skill is None


class TestMarketplaceIndexFetch:
    """Test 4: MarketplaceIndex.fetch_index() loads community skills."""

    @pytest.mark.asyncio
    async def test_fetch_index_returns_list(self):
        from app.skills.marketplace import MarketplaceIndex

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "name": "Immigration Screening",
                "description": "Immigration-specific screening",
                "type": "screening",
                "author": "Community",
                "url": "https://example.com/immigration.md",
            }
        ]

        with patch("app.skills.marketplace.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            marketplace = MarketplaceIndex()
            index = await marketplace.fetch_index()
            assert isinstance(index, list)
            assert len(index) == 1
            assert index[0]["name"] == "Immigration Screening"


class TestMarketplaceOfflineMode:
    """Test 5: MarketplaceIndex offline mode returns empty."""

    @pytest.mark.asyncio
    async def test_offline_returns_empty(self):
        from app.skills.marketplace import MarketplaceIndex

        with patch("app.skills.marketplace.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=Exception("Network error"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            marketplace = MarketplaceIndex()
            index = await marketplace.fetch_index()
            assert index == []


class TestMainVersion:
    """Test 6: main.py version is 1.0.0."""

    def test_version_is_1_0_0(self):
        from app.main import app

        assert app.version == "1.0.0"


class TestMainSecurityMiddleware:
    """Test 7: main.py includes SecurityHeadersMiddleware."""

    def test_security_headers_middleware_in_stack(self):
        from app.main import app
        from app.middleware.security import SecurityHeadersMiddleware

        middleware_classes = [
            m.cls for m in app.user_middleware if hasattr(m, "cls")
        ]
        assert SecurityHeadersMiddleware in middleware_classes


class TestMainRateLimiting:
    """Test 8: main.py includes setup_rate_limiting."""

    def test_limiter_on_app_state(self):
        from app.main import app

        assert hasattr(app.state, "limiter")


class TestMainCMSRouter:
    """Test 9: main.py includes cms_admin router."""

    def test_cms_admin_route_present(self):
        from app.main import app

        route_paths = [r.path for r in app.routes if hasattr(r, "path")]
        assert any("cms" in p for p in route_paths)


class TestMainLifespan:
    """Test 10: main.py lifespan includes key setup calls."""

    def test_lifespan_imports_telemetry(self):
        """Verify setup_telemetry is imported in main."""
        import app.main as main_mod

        assert hasattr(main_mod, "setup_telemetry")

    def test_lifespan_imports_logging(self):
        """Verify setup_logging is imported in main."""
        import app.main as main_mod

        assert hasattr(main_mod, "setup_logging")

    def test_lifespan_imports_migration_runner(self):
        """Verify migration_runner is referenced in lifespan code."""
        import inspect

        import app.main as main_mod

        lifespan_src = inspect.getsource(main_mod.lifespan)
        assert "run_startup_migrations" in lifespan_src

    def test_lifespan_has_skills_registry(self):
        """Verify SkillsRegistry is loaded in lifespan."""
        import inspect

        import app.main as main_mod

        lifespan_src = inspect.getsource(main_mod.lifespan)
        assert "SkillsRegistry" in lifespan_src
