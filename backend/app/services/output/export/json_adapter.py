"""JSON export adapter using Pydantic serialization.

Exports the OutputContext as structured JSON matching the Pydantic schema,
providing machine-readable output for integrations and API consumers.
"""

from __future__ import annotations

from app.services.output.export.base import ExportAdapter
from app.services.output.schemas import OutputContext, OutputProfile


class JSONAdapter(ExportAdapter):
    """Export adapter producing JSON via Pydantic model serialization."""

    async def export(
        self,
        markdown: str,
        context: OutputContext,
        profile: OutputProfile,
    ) -> bytes:
        """Serialize OutputContext to JSON bytes.

        The Markdown content is not included in the JSON output; instead
        the structured OutputContext data is serialized directly.

        Args:
            markdown: Rendered Markdown content (not used in JSON export).
            context: The unified output data structure.
            profile: Output profile (not used in JSON export).

        Returns:
            UTF-8 encoded JSON bytes.
        """
        return context.model_dump_json(indent=2).encode("utf-8")

    @property
    def content_type(self) -> str:
        return "application/json"

    @property
    def file_extension(self) -> str:
        return "json"
