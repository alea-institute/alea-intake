"""Document processing service with format-specific extractors.

Routes documents to the correct extractor based on MIME type, validates
file size and format, saves uploads to disk, and returns NormalizedContent
for integration with the message pipeline.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.services.document.extractors import extract_docx, extract_image_ocr, extract_pdf
from app.services.intake.message_pipeline import NormalizedContent, SourceSpan, TextElement

# Map MIME types to their async extractor functions
_MIME_EXTRACTOR_MAP: dict[str, Callable[..., Coroutine[Any, Any, tuple[str, list[dict]]]]] = {
    "application/pdf": extract_pdf,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": extract_docx,
    "image/png": extract_image_ocr,
    "image/jpeg": extract_image_ocr,
    "image/tiff": extract_image_ocr,
}

# Extraction method names by MIME type (for DocumentExtraction.extraction_method)
_MIME_EXTRACTION_METHOD: dict[str, str] = {
    "application/pdf": "pdfplumber",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "python-docx",
    "image/png": "tesseract",
    "image/jpeg": "tesseract",
    "image/tiff": "tesseract",
}


class DocumentService:
    """Service for processing uploaded documents with format-specific extractors.

    Validates file size and MIME type, saves uploads to disk, routes to the
    correct extractor, and returns NormalizedContent with per-page source spans.
    """

    def __init__(
        self,
        upload_dir: str | None = None,
        max_file_size_mb: int | None = None,
        max_page_count: int | None = None,
    ) -> None:
        """Initialize DocumentService with optional overrides.

        Args:
            upload_dir: Override upload directory (defaults to config).
            max_file_size_mb: Override max file size in MB (defaults to config).
            max_page_count: Override max page count (defaults to config).
        """
        settings = get_settings()
        self.upload_dir = Path(upload_dir or settings.intake_upload_dir)
        self.max_file_size_mb = max_file_size_mb or settings.intake_max_file_size_mb
        self.max_page_count = max_page_count or settings.intake_max_page_count

    async def save_upload(
        self,
        file_bytes: bytes,
        filename: str,
        mime_type: str,
        org_slug: str,
        intake_id: int,
    ) -> Path:
        """Save an uploaded file to disk.

        Validates file size against max_file_size_mb. Creates directory
        structure {upload_dir}/{org_slug}/{intake_id}/.

        Args:
            file_bytes: The raw file content.
            filename: Original filename.
            mime_type: MIME type of the file.
            org_slug: Organization slug for directory isolation.
            intake_id: Intake ID for directory structure.

        Returns:
            Path to the saved file.

        Raises:
            ValueError: If file exceeds max size.
        """
        max_bytes = self.max_file_size_mb * 1024 * 1024
        if len(file_bytes) > max_bytes:
            raise ValueError(
                f"File size {len(file_bytes)} bytes exceeds maximum "
                f"{self.max_file_size_mb} MB ({max_bytes} bytes)"
            )

        # Create directory structure
        dest_dir = self.upload_dir / org_slug / str(intake_id)
        dest_dir.mkdir(parents=True, exist_ok=True)

        # Save file
        file_path = dest_dir / filename
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, file_path.write_bytes, file_bytes)

        return file_path

    async def process_document(
        self,
        file_path: Path,
        mime_type: str,
        message_id: int,
        party_id: int | None = None,
    ) -> NormalizedContent:
        """Process a document and return NormalizedContent.

        Routes to the correct extractor based on MIME type. Converts
        extracted elements to TextElement objects. Creates SourceSpan
        per page for provenance tracking.

        Args:
            file_path: Path to the document file.
            mime_type: MIME type of the document.
            message_id: The DB message ID for source tracking.
            party_id: Optional party ID for multi-party attribution.

        Returns:
            NormalizedContent with source_type="document" and per-page source spans.

        Raises:
            ValueError: If MIME type is not supported.
        """
        extractor = _MIME_EXTRACTOR_MAP.get(mime_type)
        if extractor is None:
            supported = list(_MIME_EXTRACTOR_MAP.keys())
            raise ValueError(
                f"Unsupported MIME type: {mime_type}. Supported types: {supported}"
            )

        # Call the extractor
        text, elements = await extractor(file_path)

        # Convert to TextElement objects
        text_elements = [
            TextElement(
                text=elem["text"],
                element_type=elem["element_type"],
                page=elem.get("page"),
                section_path=elem.get("section_path"),
            )
            for elem in elements
        ]

        # Create per-page source spans
        spans = _build_page_spans(text, elements, message_id)

        return NormalizedContent(
            text=text,
            elements=text_elements,
            source_type="document",
            source_id=str(message_id),
            source_spans=spans,
            party_id=party_id,
        )

    def get_supported_mime_types(self) -> list[str]:
        """Return list of supported MIME types."""
        return list(_MIME_EXTRACTOR_MAP.keys())

    def get_extraction_method(self, mime_type: str) -> str:
        """Return the extraction method name for a MIME type."""
        return _MIME_EXTRACTION_METHOD.get(mime_type, "unknown")


def _build_page_spans(
    text: str,
    elements: list[dict],
    message_id: int,
) -> list[SourceSpan]:
    """Build per-page SourceSpan objects from extracted elements.

    Groups elements by page and creates a span for each page's character range
    in the full text.
    """
    if not elements:
        if text:
            return [
                SourceSpan(
                    start_char=0,
                    end_char=len(text),
                    source_message_id=message_id,
                    source_page=1,
                )
            ]
        return []

    # Group elements by page
    pages: dict[int, list[dict]] = {}
    for elem in elements:
        page = elem.get("page", 1) or 1
        if page not in pages:
            pages[page] = []
        pages[page].append(elem)

    # Build spans for each page based on character offsets in full text
    spans: list[SourceSpan] = []
    current_offset = 0

    for page_num in sorted(pages.keys()):
        page_elements = pages[page_num]
        page_text = "\n".join(elem["text"] for elem in page_elements)

        # Find this page's text in the full text
        idx = text.find(page_text, current_offset) if page_text else -1
        if idx >= 0:
            start = idx
            end = idx + len(page_text)
        else:
            # Fallback: use the first element's text
            first_text = page_elements[0]["text"]
            idx = text.find(first_text, current_offset)
            if idx >= 0:
                start = idx
                # Find the last element's text to determine end
                last_text = page_elements[-1]["text"]
                last_idx = text.find(last_text, start)
                end = last_idx + len(last_text) if last_idx >= 0 else start + len(first_text)
            else:
                start = current_offset
                end = min(current_offset + len(page_text), len(text))

        spans.append(
            SourceSpan(
                start_char=start,
                end_char=end,
                source_message_id=message_id,
                source_page=page_num,
            )
        )
        current_offset = end

    return spans
