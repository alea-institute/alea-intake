"""PDF text extraction using pdfplumber (MIT-licensed, pure-Python).

Extracts text with structural elements (headings, paragraphs) and page numbers.
pdfplumber exposes per-character font ``size`` and bounding boxes, so heading
classification and provenance bboxes are preserved 1:1 with the previous
PyMuPDF backend. PyMuPDF was dropped because it is AGPL-3.0 (S075.4 / license
policy 13); pdfplumber (over pdfminer.six) is MIT/BSD and keeps alea-intake
cleanly MIT-compatible. See THIRD-PARTY.md.

Runs synchronous pdfplumber operations in a thread executor to avoid blocking.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from pathlib import Path

# Font size at/above which a text line is treated as a heading (points).
_HEADING_FONT_SIZE = 16.0


def _extract_sync(file_path: Path) -> tuple[str, list[dict]]:
    """Synchronous PDF extraction using pdfplumber.

    Groups words into visual lines (by rounded top coordinate) and classifies
    each line by its largest font size: >= 16pt = heading, else paragraph.
    Preserves page boundaries and bounding-box information.

    Returns:
        Tuple of (full_text, elements) where elements are dicts with
        text, element_type, page, bbox, and font_size keys.
    """
    import pdfplumber

    elements: list[dict] = []
    page_texts: list[str] = []

    with pdfplumber.open(str(file_path)) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            page_texts.append(page.extract_text() or "")

            # Words carry per-word font size + bbox; group them into lines so a
            # heading line is classified as a unit rather than word-by-word.
            words = page.extract_words(
                extra_attrs=["size"], use_text_flow=True, keep_blank_chars=False
            )
            lines: dict[int, list[dict]] = defaultdict(list)
            for word in words:
                lines[round(word["top"])].append(word)

            for top in sorted(lines):
                line_words = lines[top]
                text = " ".join(w["text"] for w in line_words).strip()
                if not text:
                    continue

                font_size = max((w.get("size") or 0.0) for w in line_words)
                x0 = min(w["x0"] for w in line_words)
                y0 = min(w["top"] for w in line_words)
                x1 = max(w["x1"] for w in line_words)
                y1 = max(w["bottom"] for w in line_words)

                element_type = "heading" if font_size >= _HEADING_FONT_SIZE else "paragraph"

                elements.append({
                    "text": text,
                    "element_type": element_type,
                    "page": page_num,  # 1-indexed
                    "bbox": [x0, y0, x1, y1],
                    "font_size": font_size,
                })

    full_text = "\n\n".join(page_texts)
    return full_text, elements


async def extract_pdf(file_path: Path) -> tuple[str, list[dict]]:
    """Extract text and structural elements from a PDF file.

    Runs synchronous pdfplumber operations in a thread executor to avoid
    blocking the event loop.

    Args:
        file_path: Path to the PDF file.

    Returns:
        Tuple of (full_text, elements) where elements are dicts with
        text, element_type, page, bbox, and font_size keys.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _extract_sync, file_path)
