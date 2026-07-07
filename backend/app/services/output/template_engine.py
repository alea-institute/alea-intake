"""Jinja2 template engine for rendering OutputContext into structured Markdown.

Renders per-profile output through four template files:
  - cirac_memo.md.j2: CIRAC-format case memo (D-01)
  - triage_report.md.j2: Triage & routing recommendations (D-02)
  - action_items.md.j2: Prioritized action checklist (D-03)
  - gap_appendix.md.j2: Consolidated gap report appendix (D-07)

Section visibility controlled by OutputProfile.sections dict.
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from app.services.output.schemas import OutputContext, OutputProfile


class TemplateEngine:
    """Renders OutputContext through Jinja2 templates per profile (per research Pattern 1)."""

    DEFAULT_TEMPLATE_DIR = Path(__file__).parent / "templates"

    def __init__(self, template_dir: str | Path | None = None) -> None:
        """Initialize with a Jinja2 environment loading from template directory.

        Args:
            template_dir: Path to template directory. Defaults to ./templates/.
        """
        resolved_dir = str(template_dir or self.DEFAULT_TEMPLATE_DIR)
        self._env = Environment(
            loader=FileSystemLoader(resolved_dir),
            autoescape=False,  # Markdown output, not HTML
            trim_blocks=True,
            lstrip_blocks=True,
        )
        # Register custom filters
        self._env.filters["percentage"] = _filter_percentage

    def render_full(self, context: OutputContext, profile: OutputProfile) -> str:
        """Render all enabled sections into a single Markdown document.

        Concatenates sections in order based on profile.sections visibility:
        1. Executive summary (if enabled and non-empty)
        2. CIRAC memo (if enabled)
        3. Triage routing (if enabled)
        4. Action items (if enabled)
        5. Gap appendix (if enabled)

        Args:
            context: The unified output data structure.
            profile: Output profile controlling section visibility.

        Returns:
            Complete Markdown string.
        """
        sections: list[str] = []

        # Safety alerts -- rendered ABOVE everything else (SAFETY CRITICAL, BUG-15).
        # When a DV / self-harm / trafficking concern is detected in the narrative,
        # calm actionable escalation guidance must be the first thing the reader
        # sees. Rendered independent of profile toggles; nothing renders when no
        # alert fired (empty safety_alerts).
        if context.safety_alerts:
            sections.append(
                self.render_section("safety_alerts.md.j2", context, profile)
            )

        # Deadlines & time-sensitive items -- rendered FIRST (before CIRAC), high
        # stakes, always hedged. Shown whenever any deadline was detected,
        # independent of profile section toggles.
        if context.deadlines:
            sections.append(self.render_section("deadlines.md.j2", context, profile))

        # Executive summary
        if (
            profile.sections.get("executive_summary", False)
            and context.executive_summary
        ):
            sections.append(self._render_executive_summary(context))

        # CIRAC memo
        if profile.sections.get("cirac_memo", False):
            sections.append(self.render_section("cirac_memo.md.j2", context, profile))

        # Triage routing
        if profile.sections.get("triage_routing", False) and context.triage:
            sections.append(self.render_section("triage_report.md.j2", context, profile))

        # Action items
        if profile.sections.get("action_items", False) and context.action_items:
            sections.append(self.render_section("action_items.md.j2", context, profile))

        # Gap appendix
        if profile.sections.get("gap_appendix", False):
            sections.append(self.render_section("gap_appendix.md.j2", context, profile))

        return "\n".join(sections)

    def render_section(
        self,
        template_name: str,
        context: OutputContext,
        profile: OutputProfile,
    ) -> str:
        """Render a single section template.

        Args:
            template_name: Template file name (e.g., "cirac_memo.md.j2").
            context: The unified output data structure.
            profile: Output profile for template context.

        Returns:
            Rendered Markdown string for this section.
        """
        template = self._env.get_template(template_name)
        return template.render(context=context, profile=profile)

    @staticmethod
    def _render_executive_summary(context: OutputContext) -> str:
        """Render the executive summary section.

        Args:
            context: The unified output data structure.

        Returns:
            Markdown string for executive summary.
        """
        return (
            f"## Executive Summary\n\n"
            f"{context.executive_summary}\n\n"
            f"**Completeness Score:** {context.completeness_score:.0%}\n\n"
            f"---\n"
        )


def _filter_percentage(value: float) -> str:
    """Jinja2 filter: convert float to percentage string."""
    return f"{value * 100:.0f}%"
