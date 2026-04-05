"""Abstract base class for format-specific export adapters.

Each adapter converts rendered Markdown content into a target format
(PDF, DOCX, JSON) using the ExportAdapter interface.
"""

from __future__ import annotations

import abc

from app.services.output.schemas import OutputContext, OutputProfile


class ExportAdapter(abc.ABC):
    """Base class for format-specific export (per research Pattern 1).

    Concrete adapters must implement:
      - export(): Convert Markdown to target format bytes
      - content_type: MIME content type for HTTP responses
      - file_extension: File extension for downloads
    """

    @abc.abstractmethod
    async def export(
        self,
        markdown: str,
        context: OutputContext,
        profile: OutputProfile,
    ) -> bytes:
        """Convert Markdown content to target format bytes.

        Args:
            markdown: Rendered Markdown content from TemplateEngine.
            context: The unified output data structure for metadata.
            profile: Output profile for branding and formatting.

        Returns:
            Bytes of the rendered output in the target format.
        """
        ...

    @property
    @abc.abstractmethod
    def content_type(self) -> str:
        """MIME content type for the export format."""
        ...

    @property
    @abc.abstractmethod
    def file_extension(self) -> str:
        """File extension for the export format (without dot)."""
        ...
