"""UsageTracker -- per-org research tool usage tracking and budget enforcement.

Per D-18, tracks API call counts per tool per org per month and enforces
budget caps. Orgs can set monthly budget caps for each research tool;
tools exceeding their cap are skipped during research.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class UsageTracker:
    """Tracks per-org research tool usage and enforces budget caps.

    In-memory tracker for MVP; production would persist to DB and
    use ResearchToolConfig.config_json for budget caps.

    Args:
        budget_caps: Dict of tool_name -> monthly budget cap (float).
    """

    def __init__(self, budget_caps: dict[str, float] | None = None) -> None:
        self._budget_caps: dict[str, float] = budget_caps or {}
        # Usage: {(org_id, tool_name, month_key): call_count}
        self._usage: dict[tuple[int, str, str], int] = {}

    @staticmethod
    def _month_key() -> str:
        """Get current year-month key for bucketing."""
        now = datetime.now(timezone.utc)
        return f"{now.year}-{now.month:02d}"

    async def record_call(self, org_id: int, tool_name: str) -> None:
        """Record a research tool API call for the org.

        Args:
            org_id: Organization ID.
            tool_name: Name of the research tool adapter.
        """
        key = (org_id, tool_name, self._month_key())
        self._usage[key] = self._usage.get(key, 0) + 1

    async def check_budget(self, org_id: int, tool_name: str) -> bool:
        """Check if a tool is within its monthly budget for the org.

        Returns True if no budget cap is set or usage is within cap.

        Args:
            org_id: Organization ID.
            tool_name: Name of the research tool adapter.

        Returns:
            True if the tool can be used, False if budget exceeded.
        """
        cap = self._budget_caps.get(tool_name)
        if cap is None:
            return True  # No cap set

        key = (org_id, tool_name, self._month_key())
        current_usage = self._usage.get(key, 0)
        return current_usage < cap

    async def get_usage_summary(self, org_id: int) -> dict[str, Any]:
        """Get usage summary for all tools for the current month.

        Args:
            org_id: Organization ID.

        Returns:
            Dict with per-tool usage counts and budget status.
        """
        month = self._month_key()
        summary: dict[str, Any] = {}

        # Collect all tools that have usage or budget caps
        all_tools = set()
        for (oid, tool, m), count in self._usage.items():
            if oid == org_id and m == month:
                all_tools.add(tool)
        all_tools.update(self._budget_caps.keys())

        for tool in sorted(all_tools):
            key = (org_id, tool, month)
            count = self._usage.get(key, 0)
            cap = self._budget_caps.get(tool)
            summary[tool] = {
                "call_count": count,
                "budget_cap": cap,
                "budget_remaining": (cap - count) if cap is not None else None,
                "within_budget": count < cap if cap is not None else True,
            }

        return summary

    def set_budget_cap(self, tool_name: str, cap: float) -> None:
        """Set or update the monthly budget cap for a tool.

        Args:
            tool_name: Name of the research tool adapter.
            cap: Maximum number of calls per month.
        """
        self._budget_caps[tool_name] = cap
