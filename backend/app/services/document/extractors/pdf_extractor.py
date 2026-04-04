"""PDF text extraction using PyMuPDF (pymupdf).

Extracts text with structural elements (headings, paragraphs) and page numbers.
Runs synchronous PyMuPDF operations in a thread executor to avoid blocking.
"""

from __future__ import annotations

import asyncio
from pathlib import Path


def _extract_sync(file_path: Path) -> tuple[str, list[dict]]:
    """Synchronous PDF extraction using PyMuPDF.

    Classifies elements by font size: >= 16pt = heading, else paragraph.
    Preserves page boundaries and bounding box information.

    Returns:
        Tuple of (full_text, elements) where elements are dicts with
        text, element_type, page, bbox, and font_size keys.
    """
    import pymupdf

    doc = pymupdf.open(str(file_path))
    elements: list[dict] = []
    page_texts: list[str] = []

    try:
        for page_num in range(len(doc)):
            page = doc[page_num]
            page_text = page.get_text()
            page_texts.append(page_text)

            # Get structured blocks for element classification
            blocks = page.get_text("dict")["blocks"]
            for block in blocks:
                # Only process text blocks (type 0), skip images (type 1)
                if block.get("type") != 0:
                    continue

                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        if not text:
                            continue

                        font_size = span.get("size", 12.0)
                        bbox = span.get("bbox", block.get("bbox", [0, 0, 0, 0]))

                        element_type = "heading" if font_size >= 16.0 else "paragraph"

                        elements.append({
                            "text": text,
                            "element_type": element_type,
                            "page": page_num + 1,  # 1-indexed
                            "bbox": list(bbox),
                            "font_size": font_size,
                        })
    finally:
        doc.close()

    full_text = "\n\n".join(page_texts)
    return full_text, elements


async def extract_pdf(file_path: Path) -> tuple[str, list[dict]]:
    """Extract text and structural elements from a PDF file.

    Runs synchronous PyMuPDF operations in a thread executor to avoid
    blocking the event loop.

    Args:
        file_path: Path to the PDF file.

    Returns:
        Tuple of (full_text, elements) where elements are dicts with
        text, element_type, page, bbox, and font_size keys.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _extract_sync, file_path)
