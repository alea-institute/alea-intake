"""Image OCR text extraction using pytesseract and Pillow.

Extracts text from images via Tesseract OCR.
Runs synchronous OCR operations in a thread executor to avoid blocking.
"""

from __future__ import annotations

import asyncio
from pathlib import Path


def _extract_sync(file_path: Path) -> tuple[str, list[dict]]:
    """Synchronous image OCR extraction using pytesseract.

    Returns:
        Tuple of (text, elements) where elements is a list with a single
        paragraph element containing the OCR text.
    """
    import pytesseract
    from PIL import Image

    img = Image.open(str(file_path))
    text = pytesseract.image_to_string(img, config="--psm 6")
    text = text.strip()

    elements: list[dict] = []
    if text:
        elements.append({
            "text": text,
            "element_type": "paragraph",
            "page": 1,
        })

    return text, elements


async def extract_image_ocr(file_path: Path) -> tuple[str, list[dict]]:
    """Extract text from an image file using OCR.

    Runs synchronous pytesseract operations in a thread executor to avoid
    blocking the event loop.

    Args:
        file_path: Path to the image file.

    Returns:
        Tuple of (text, elements) where elements is a list with a single
        paragraph element containing the OCR text.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _extract_sync, file_path)
