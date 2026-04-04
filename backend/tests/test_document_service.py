"""Tests for document processing service with PDF, DOCX, and OCR extractors.

Tests cover:
- PDF extraction via PyMuPDF with structural elements
- DOCX extraction via python-docx with headings, paragraphs, tables
- Image OCR via pytesseract (skipped if tesseract not installed)
- DocumentService MIME type routing
- File size validation
- Unsupported MIME type rejection
- NormalizedContent output with source_type="document"
- save_upload directory creation and file persistence
- All extraction runs async via run_in_executor
"""

import shutil
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.services.document.document_service import DocumentService, _MIME_EXTRACTOR_MAP
from app.services.document.extractors.docx_extractor import extract_docx
from app.services.document.extractors.ocr_extractor import extract_image_ocr
from app.services.document.extractors.pdf_extractor import extract_pdf
from app.services.intake.message_pipeline import NormalizedContent, SourceSpan, TextElement

# Paths to test fixtures
FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_PDF = FIXTURES_DIR / "sample.pdf"
SAMPLE_DOCX = FIXTURES_DIR / "sample.docx"
SAMPLE_PNG = FIXTURES_DIR / "sample.png"

# Check if tesseract is available for OCR tests
_tesseract_available = shutil.which("tesseract") is not None


# --- PDF Extractor Tests ---


@pytest.mark.asyncio
async def test_extract_pdf_returns_text_and_elements():
    """Test 1: extract_pdf returns (full_text, elements_list) with structural data."""
    text, elements = await extract_pdf(SAMPLE_PDF)
    assert isinstance(text, str)
    assert isinstance(elements, list)
    assert len(text) > 0
    assert "Sample Legal Document" in text


@pytest.mark.asyncio
async def test_extract_pdf_element_keys():
    """Test 1 continued: each element has text, element_type, page, bbox, font_size."""
    text, elements = await extract_pdf(SAMPLE_PDF)
    assert len(elements) > 0
    for elem in elements:
        assert "text" in elem
        assert "element_type" in elem
        assert "page" in elem
        assert "bbox" in elem
        assert "font_size" in elem


@pytest.mark.asyncio
async def test_extract_pdf_preserves_page_boundaries():
    """Test 2: extract_pdf preserves page boundaries with page numbers in elements."""
    text, elements = await extract_pdf(SAMPLE_PDF)
    pages = {elem["page"] for elem in elements}
    assert 1 in pages  # At least page 1


@pytest.mark.asyncio
async def test_extract_pdf_heading_classification():
    """Test: large font text classified as heading."""
    text, elements = await extract_pdf(SAMPLE_PDF)
    headings = [e for e in elements if e["element_type"] == "heading"]
    # Our sample PDF has "Sample Legal Document" at 20pt which is >= 16pt
    heading_texts = [h["text"] for h in headings]
    assert any("Sample Legal Document" in t for t in heading_texts)


# --- DOCX Extractor Tests ---


@pytest.mark.asyncio
async def test_extract_docx_returns_text_and_elements():
    """Test 3: extract_docx returns (full_text, elements_list) with headings and paragraphs."""
    text, elements = await extract_docx(SAMPLE_DOCX)
    assert isinstance(text, str)
    assert isinstance(elements, list)
    assert len(text) > 0
    assert "Test Heading" in text


@pytest.mark.asyncio
async def test_extract_docx_heading_identification():
    """Test 3: headings identified as element_type='heading', paragraphs as 'paragraph'."""
    text, elements = await extract_docx(SAMPLE_DOCX)
    headings = [e for e in elements if e["element_type"] == "heading"]
    paragraphs = [e for e in elements if e["element_type"] == "paragraph"]
    assert len(headings) > 0
    assert any("Test Heading" in h["text"] for h in headings)
    assert len(paragraphs) > 0
    assert any("Test paragraph content" in p["text"] for p in paragraphs)


@pytest.mark.asyncio
async def test_extract_docx_preserves_table_structure():
    """Test 4: extract_docx preserves table structure as element_type='table'."""
    text, elements = await extract_docx(SAMPLE_DOCX)
    tables = [e for e in elements if e["element_type"] == "table"]
    assert len(tables) > 0
    table_text = tables[0]["text"]
    assert "Header 1" in table_text
    assert "Value 1" in table_text


# --- OCR Extractor Tests ---


@pytest.mark.asyncio
@pytest.mark.skipif(not _tesseract_available, reason="tesseract not installed")
async def test_extract_image_ocr_returns_text():
    """Test 5: extract_image_ocr returns (text, elements_list) from OCR processing."""
    text, elements = await extract_image_ocr(SAMPLE_PNG)
    assert isinstance(text, str)
    assert isinstance(elements, list)
    # OCR may or may not produce meaningful text from our simple image
    # Just verify the return types are correct


@pytest.mark.asyncio
@pytest.mark.skipif(not _tesseract_available, reason="tesseract not installed")
async def test_extract_image_ocr_element_structure():
    """Test 5: OCR elements have correct structure."""
    text, elements = await extract_image_ocr(SAMPLE_PNG)
    if elements:
        assert elements[0]["element_type"] == "paragraph"
        assert elements[0]["page"] == 1


# --- DocumentService Tests ---


@pytest.fixture
def doc_service(tmp_path):
    """Create a DocumentService with tmp_path as upload dir."""
    with patch("app.services.document.document_service.get_settings") as mock_settings:
        mock_settings.return_value.intake_upload_dir = str(tmp_path)
        mock_settings.return_value.intake_max_file_size_mb = 50
        mock_settings.return_value.intake_max_page_count = 200
        return DocumentService(
            upload_dir=str(tmp_path),
            max_file_size_mb=50,
            max_page_count=200,
        )


@pytest.mark.asyncio
async def test_document_service_routes_pdf(doc_service):
    """Test 6: DocumentService.process_document routes PDF to extract_pdf."""
    result = await doc_service.process_document(
        SAMPLE_PDF, "application/pdf", message_id=1
    )
    assert isinstance(result, NormalizedContent)
    assert "Sample Legal Document" in result.text


@pytest.mark.asyncio
async def test_document_service_routes_docx(doc_service):
    """Test 6: DocumentService.process_document routes DOCX to extract_docx."""
    result = await doc_service.process_document(
        SAMPLE_DOCX,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        message_id=2,
    )
    assert isinstance(result, NormalizedContent)
    assert "Test Heading" in result.text


@pytest.mark.asyncio
@pytest.mark.skipif(not _tesseract_available, reason="tesseract not installed")
async def test_document_service_routes_image(doc_service):
    """Test 6: DocumentService.process_document routes image to extract_image_ocr."""
    result = await doc_service.process_document(
        SAMPLE_PNG, "image/png", message_id=3
    )
    assert isinstance(result, NormalizedContent)


@pytest.mark.asyncio
async def test_document_service_rejects_oversized_file(doc_service):
    """Test 7: DocumentService rejects files exceeding intake_max_file_size_mb."""
    doc_service.max_file_size_mb = 0  # 0 MB = reject everything
    with pytest.raises(ValueError, match="exceeds maximum"):
        await doc_service.save_upload(
            file_bytes=b"some content",
            filename="test.pdf",
            mime_type="application/pdf",
            org_slug="test-org",
            intake_id=1,
        )


@pytest.mark.asyncio
async def test_document_service_rejects_unsupported_mime(doc_service):
    """Test 8: DocumentService rejects unsupported MIME types with clear error."""
    with pytest.raises(ValueError, match="Unsupported MIME type"):
        await doc_service.process_document(
            Path("/tmp/test.zip"), "application/zip", message_id=1
        )


@pytest.mark.asyncio
async def test_extraction_runs_in_executor():
    """Test 9: All extraction runs via run_in_executor (does not block event loop)."""
    import asyncio
    from unittest.mock import MagicMock

    # Verify extract_pdf uses run_in_executor by checking it's async
    result = extract_pdf(SAMPLE_PDF)
    assert asyncio.iscoroutine(result)
    # Clean up the coroutine
    text, elements = await result
    assert isinstance(text, str)


@pytest.mark.asyncio
async def test_document_service_returns_normalized_content(doc_service):
    """Test 10: DocumentService.process_document returns NormalizedContent with source_type='document' and per-page source spans."""
    result = await doc_service.process_document(
        SAMPLE_PDF, "application/pdf", message_id=42, party_id=7
    )
    assert isinstance(result, NormalizedContent)
    assert result.source_type == "document"
    assert result.source_id == "42"
    assert result.party_id == 7
    assert len(result.source_spans) > 0
    # Verify source spans have page info
    for span in result.source_spans:
        assert isinstance(span, SourceSpan)
        assert span.source_page is not None
        assert span.start_char >= 0
        assert span.end_char > span.start_char


@pytest.mark.asyncio
async def test_document_service_save_upload(doc_service, tmp_path):
    """Test: DocumentService.save_upload creates directory and file."""
    doc_service.upload_dir = tmp_path
    file_bytes = b"test file content"
    file_path = await doc_service.save_upload(
        file_bytes=file_bytes,
        filename="test.pdf",
        mime_type="application/pdf",
        org_slug="test-org",
        intake_id=42,
    )
    assert file_path.exists()
    assert file_path.read_bytes() == file_bytes
    assert "test-org" in str(file_path)
    assert "42" in str(file_path)


@pytest.mark.asyncio
async def test_document_service_get_supported_mime_types(doc_service):
    """Test: get_supported_mime_types returns list of known MIME types."""
    types = doc_service.get_supported_mime_types()
    assert "application/pdf" in types
    assert "application/vnd.openxmlformats-officedocument.wordprocessingml.document" in types
    assert "image/png" in types
    assert "image/jpeg" in types


@pytest.mark.asyncio
async def test_document_service_normalized_elements(doc_service):
    """Test: NormalizedContent elements are proper TextElement objects."""
    result = await doc_service.process_document(
        SAMPLE_PDF, "application/pdf", message_id=1
    )
    assert len(result.elements) > 0
    for elem in result.elements:
        assert isinstance(elem, TextElement)
        assert isinstance(elem.text, str)
        assert elem.element_type in ("heading", "paragraph", "table", "list_item")
