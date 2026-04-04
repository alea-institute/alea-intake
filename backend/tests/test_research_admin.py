"""Tests for research admin API -- tool configuration, usage display, budget management.

Validates admin-only endpoints for listing platform tools, activating/deactivating
per org, usage summary, budget caps, and health checks per D-02/D-18.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("ALEA_SECRET_KEY", "test-secret-key-for-testing-only-not-production")

from app.services.research.usage_tracker import UsageTracker


# ---- Unit tests for research_admin router logic ----


class TestResearchAdminRouter:
    """Research admin API provides tool listing, activation, usage, budget, health."""

    def test_router_exists_with_correct_prefix(self):
        """Test 1/7/10: Router exists, has correct prefix, and requires admin role."""
        from app.routers.research_admin import router

        assert router.prefix == "/api/v1/admin/research"
        assert "research-admin" in router.tags
        # Router-level dependency should include require_role
        assert len(router.dependencies) > 0

    def test_list_tools_endpoint_exists(self):
        """Test 1: GET /admin/research/tools route exists."""
        from app.routers.research_admin import router

        paths = [r.path for r in router.routes]
        assert any("/tools" == p.split("/api/v1/admin/research")[-1] for p in paths)

    def test_activate_endpoint_exists(self):
        """Test 2: POST /admin/research/tools/{tool_name}/activate route exists."""
        from app.routers.research_admin import router

        paths = [r.path for r in router.routes]
        assert any("activate" in p for p in paths)

    def test_deactivate_endpoint_exists(self):
        """Test 3: POST /admin/research/tools/{tool_name}/deactivate route exists."""
        from app.routers.research_admin import router

        paths = [r.path for r in router.routes]
        assert any("deactivate" in p for p in paths)

    def test_usage_endpoint_exists(self):
        """Test 4: GET /admin/research/usage route exists."""
        from app.routers.research_admin import router

        paths = [r.path for r in router.routes]
        assert any("usage" in p for p in paths)

    def test_budget_endpoint_exists(self):
        """Test 5: PUT /admin/research/tools/{tool_name}/budget route exists."""
        from app.routers.research_admin import router

        paths = [r.path for r in router.routes]
        assert any("budget" in p for p in paths)

    def test_health_endpoint_exists(self):
        """Test 6: GET /admin/research/tools/{tool_name}/health route exists."""
        from app.routers.research_admin import router

        paths = [r.path for r in router.routes]
        assert any("health" in p for p in paths)


class TestResearchAdminCredentialSafety:
    """Credentials are not exposed in GET responses per D-02."""

    def test_list_tools_schema_excludes_credentials(self):
        """Test 8: ToolResponse schema has no api_key or credentials field."""
        from app.routers.research_admin import ToolResponse

        fields = ToolResponse.model_fields
        assert "api_key" not in fields
        assert "credentials" not in fields
        assert "api_key_encrypted" not in fields

    def test_list_tools_schema_shows_activation_status(self):
        """Test 9: ToolResponse shows is_free and activation status."""
        from app.routers.research_admin import ToolResponse

        fields = ToolResponse.model_fields
        assert "is_free" in fields
        assert "is_active" in fields


class TestResearchAdminRegistration:
    """Both research_admin and kb_admin routers are registered in main.py."""

    def test_research_admin_router_imported_in_main(self):
        """Test 10: research_admin router import exists in main.py."""
        import ast
        import pathlib

        main_path = pathlib.Path(__file__).parent.parent / "app" / "main.py"
        source = main_path.read_text()
        tree = ast.parse(source)

        imports = [
            node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))
        ]
        import_lines = [ast.dump(node) for node in imports]
        # Check that research_admin is imported
        assert any("research_admin" in line for line in import_lines)
        # Check that include_router is called with it
        assert "research_admin_router" in source

    def test_kb_admin_router_imported_in_main(self):
        """Test 11: kb_admin router import exists in main.py."""
        import ast
        import pathlib

        main_path = pathlib.Path(__file__).parent.parent / "app" / "main.py"
        source = main_path.read_text()
        tree = ast.parse(source)

        imports = [
            node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))
        ]
        import_lines = [ast.dump(node) for node in imports]
        assert any("kb_admin" in line for line in import_lines)
        assert "kb_admin_router" in source


# ---- UsageTracker unit tests ----


class TestUsageTracker:
    """UsageTracker tracks calls and enforces budgets."""

    @pytest.mark.asyncio
    async def test_record_and_check_budget(self):
        """Usage tracking records calls and respects budget caps."""
        tracker = UsageTracker(budget_caps={"courtlistener": 5})

        # Should be within budget initially
        assert await tracker.check_budget(1, "courtlistener") is True

        # Record 5 calls
        for _ in range(5):
            await tracker.record_call(1, "courtlistener")

        # Now should be over budget
        assert await tracker.check_budget(1, "courtlistener") is False

    @pytest.mark.asyncio
    async def test_no_cap_allows_unlimited(self):
        """Tools without budget caps always return True for check_budget."""
        tracker = UsageTracker()

        for _ in range(100):
            await tracker.record_call(1, "google_scholar")

        assert await tracker.check_budget(1, "google_scholar") is True

    @pytest.mark.asyncio
    async def test_get_usage_summary(self):
        """Usage summary returns per-tool counts and budget status."""
        tracker = UsageTracker(budget_caps={"courtlistener": 10})
        await tracker.record_call(1, "courtlistener")
        await tracker.record_call(1, "courtlistener")

        summary = await tracker.get_usage_summary(1)

        assert "courtlistener" in summary
        assert summary["courtlistener"]["call_count"] == 2
        assert summary["courtlistener"]["budget_cap"] == 10
        assert summary["courtlistener"]["within_budget"] is True
