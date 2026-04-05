"""PDF export adapter using WeasyPrint with CSS Paged Media for legal formatting.

Converts Markdown to HTML via markdown-it-py, applies the legal_pdf.css
stylesheet, and renders to PDF with page numbers, headers, footers,
and optional org branding.
"""

from __future__ import annotations

from pathlib import Path

from markdown_it import MarkdownIt
from weasyprint import HTML

from app.services.output.export.base import ExportAdapter
from app.services.output.schemas import OutputContext, OutputProfile


class PDFAdapter(ExportAdapter):
    """Export adapter producing PDF via WeasyPrint with CSS Paged Media."""

    CSS_PATH = Path(__file__).parent.parent / "templates" / "css" / "legal_pdf.css"

    def __init__(self) -> None:
        self._md = MarkdownIt("commonmark", {"breaks": True, "html": True}).enable("table")

    async def export(
        self,
        markdown: str,
        context: OutputContext,
        profile: OutputProfile,
    ) -> bytes:
        """Convert Markdown to PDF with legal formatting.

        1. Convert Markdown to HTML via markdown-it-py
        2. Wrap in full HTML document with CSS
        3. Inject metadata elements for running headers/footers
        4. Apply org branding CSS variables if provided
        5. Render via WeasyPrint

        Args:
            markdown: Rendered Markdown content.
            context: Output data for metadata (matter title, org info).
            profile: Output profile for branding.

        Returns:
            PDF bytes.
        """
        # Convert Markdown to HTML
        html_body = self._md.render(markdown) if markdown else ""

        # Load CSS stylesheet
        css_content = ""
        if self.CSS_PATH.exists():
            css_content = self.CSS_PATH.read_text(encoding="utf-8")

        # Build org branding overrides
        branding_css = self._build_branding_css(profile)

        # Build full HTML document
        full_html = self._build_html_document(
            body_html=html_body,
            css=css_content,
            branding_css=branding_css,
            matter_title=context.matter_title,
            org_name=profile.org_branding.org_name if profile.org_branding else None,
        )

        # Render PDF via WeasyPrint
        pdf_bytes: bytes = HTML(string=full_html).write_pdf()
        return pdf_bytes

    @property
    def content_type(self) -> str:
        return "application/pdf"

    @property
    def file_extension(self) -> str:
        return "pdf"

    @staticmethod
    def _build_branding_css(profile: OutputProfile) -> str:
        """Generate CSS variable overrides from org branding."""
        if not profile.org_branding:
            return ""
        b = profile.org_branding
        lines = [":root {"]
        lines.append(f"  --primary-color: {b.primary_color};")
        lines.append(f"  --secondary-color: {b.secondary_color};")
        if b.font_name:
            lines.append(f'  --body-font: "{b.font_name}", serif;')
        lines.append("}")
        return "\n".join(lines)

    @staticmethod
    def _build_html_document(
        body_html: str,
        css: str,
        branding_css: str,
        matter_title: str,
        org_name: str | None,
    ) -> str:
        """Wrap body HTML in a full HTML document with CSS and metadata elements."""
        org_display = org_name or ""
        return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{matter_title}</title>
<style>
{css}
{branding_css}
</style>
</head>
<body>
<div class="matter-title" style="display:none">{matter_title}</div>
<div class="org-name" style="display:none">{org_display}</div>
<main class="legal-document">
{body_html}
</main>
</body>
</html>"""
