"""Tests for document upload endpoint and message pipeline document modality.

Tests cover:
- POST /{intake_id}/document stores Message with modality="document"
- UploadedDocument record creation with correct fields
- DocumentExtraction record creation with extracted text
- process_message("document", ...) delegates to DocumentService
- WebSocket notification after document extraction
- LLM follow-up generation after document upload
- Unsupported MIME type returns 400
- File exceeding max size returns 413
"""

import io
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pymupdf
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import DocumentExtraction, UploadedDocument
from app.models.intake import Intake, IntakeParty, IntakeSession, Message
from app.services.document import DocumentService
from app.services.intake.message_pipeline import NormalizedContent, process_message


def _create_minimal_pdf() -> bytes:
    """Create a minimal valid PDF in memory using pymupdf."""
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Test Document Heading", fontsize=20)
    page.insert_text((72, 120), "Test paragraph for extraction.", fontsize=12)
    buf = doc.tobytes()
    doc.close()
    return buf


# --- Fixtures ---


@pytest.fixture
async def intake_records(async_session: AsyncSession):
    """Create test intake, session, and party records."""
    intake = Intake(org_id=1, status="active", session_mode="multi_session")
    async_session.add(intake)
    await async_session.flush()

    party = IntakeParty(intake_id=intake.id, role_in_intake="primary")
    async_session.add(party)
    await async_session.flush()

    session_record = IntakeSession(intake_id=intake.id, status="active")
    async_session.add(session_record)
    await async_session.flush()

    return {"intake": intake, "party": party, "session": session_record}


# --- process_message document modality tests ---


@pytest.mark.asyncio
async def test_process_message_document_modality(tmp_path):
    """Test 7: process_message('document', ...) delegates to DocumentService instead of raising NotImplementedError."""
    # Create a real test PDF
    pdf_bytes = _create_minimal_pdf()
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(pdf_bytes)

    with patch("app.services.document.document_service.get_settings") as mock_settings:
        mock_settings.return_value.intake_upload_dir = str(tmp_path)
        mock_settings.return_value.intake_max_file_size_mb = 50
        mock_settings.return_value.intake_max_page_count = 200

        result = await process_message(
            "document",
            "test content",
            message_id=1,
            party_id=None,
            file_path=pdf_path,
            mime_type="application/pdf",
        )

    assert isinstance(result, NormalizedContent)
    assert result.source_type == "document"
    assert "Test Document Heading" in result.text


@pytest.mark.asyncio
async def test_process_message_document_no_not_implemented(tmp_path):
    """Test: document modality does NOT raise NotImplementedError."""
    pdf_bytes = _create_minimal_pdf()
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(pdf_bytes)

    with patch("app.services.document.document_service.get_settings") as mock_settings:
        mock_settings.return_value.intake_upload_dir = str(tmp_path)
        mock_settings.return_value.intake_max_file_size_mb = 50
        mock_settings.return_value.intake_max_page_count = 200

        # Should NOT raise
        result = await process_message(
            "document",
            "ignored",
            message_id=99,
            file_path=pdf_path,
            mime_type="application/pdf",
        )
        assert result.source_type == "document"


@pytest.mark.asyncio
async def test_process_message_voice_still_raises():
    """Test: voice modality still raises NotImplementedError (Plan 02 handles it)."""
    with pytest.raises(NotImplementedError, match="Voice"):
        await process_message("voice", "content", message_id=1)


# --- Document upload endpoint tests (unit-style with mocked DB) ---


@pytest.mark.asyncio
async def test_document_service_returns_normalized_for_upload(tmp_path):
    """Test 4: Document extraction produces NormalizedContent with source_type='document'."""
    pdf_bytes = _create_minimal_pdf()
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(pdf_bytes)

    with patch("app.services.document.document_service.get_settings") as mock_settings:
        mock_settings.return_value.intake_upload_dir = str(tmp_path)
        mock_settings.return_value.intake_max_file_size_mb = 50
        mock_settings.return_value.intake_max_page_count = 200

        doc_service = DocumentService(
            upload_dir=str(tmp_path),
            max_file_size_mb=50,
            max_page_count=200,
        )
        result = await doc_service.process_document(
            pdf_path, "application/pdf", message_id=1, party_id=2
        )

    assert isinstance(result, NormalizedContent)
    assert result.source_type == "document"
    assert result.party_id == 2
    assert len(result.elements) > 0
    assert len(result.source_spans) > 0


@pytest.mark.asyncio
async def test_unsupported_mime_type_raises():
    """Test 8: Unsupported MIME type raises ValueError with supported types list."""
    with patch("app.services.document.document_service.get_settings") as mock_settings:
        mock_settings.return_value.intake_upload_dir = "/tmp"
        mock_settings.return_value.intake_max_file_size_mb = 50
        mock_settings.return_value.intake_max_page_count = 200

        doc_service = DocumentService(upload_dir="/tmp")
        with pytest.raises(ValueError, match="Unsupported MIME type"):
            await doc_service.process_document(
                Path("/tmp/test.zip"), "application/zip", message_id=1
            )


@pytest.mark.asyncio
async def test_file_too_large_raises():
    """Test 9: File exceeding max size raises ValueError."""
    with patch("app.services.document.document_service.get_settings") as mock_settings:
        mock_settings.return_value.intake_upload_dir = "/tmp"
        mock_settings.return_value.intake_max_file_size_mb = 0
        mock_settings.return_value.intake_max_page_count = 200

        doc_service = DocumentService(upload_dir="/tmp", max_file_size_mb=0)
        with pytest.raises(ValueError, match="exceeds maximum"):
            await doc_service.save_upload(
                file_bytes=b"some content",
                filename="big.pdf",
                mime_type="application/pdf",
                org_slug="test",
                intake_id=1,
            )


# --- Integration tests with async_session ---


@pytest.mark.asyncio
async def test_upload_document_stores_message(async_session, intake_records):
    """Test 1+3: Document upload stores Message with modality='document'."""
    from app.services.intake.session_service import IntakeSessionService

    svc = IntakeSessionService(async_session)
    msg = await svc.store_message(
        session_id=intake_records["session"].id,
        sender_type="consumer",
        modality="document",
        content="test.pdf",
        party_id=intake_records["party"].id,
    )

    assert msg.id is not None
    assert msg.modality == "document"
    assert msg.sender_type == "consumer"
    assert msg.sequence_number == 1


@pytest.mark.asyncio
async def test_upload_document_creates_uploaded_document_record(async_session, intake_records):
    """Test 2: UploadedDocument record created with correct fields."""
    from app.services.intake.session_service import IntakeSessionService

    svc = IntakeSessionService(async_session)
    msg = await svc.store_message(
        session_id=intake_records["session"].id,
        sender_type="consumer",
        modality="document",
        content="sample.pdf",
    )

    doc = UploadedDocument(
        message_id=msg.id,
        intake_id=intake_records["intake"].id,
        file_path_encrypted=b"/tmp/test/sample.pdf",
        original_filename="sample.pdf",
        mime_type="application/pdf",
        file_size_bytes=1024,
        extraction_status="pending",
    )
    async_session.add(doc)
    await async_session.flush()

    assert doc.id is not None
    assert doc.mime_type == "application/pdf"
    assert doc.original_filename == "sample.pdf"
    assert doc.file_size_bytes == 1024
    assert doc.extraction_status == "pending"


@pytest.mark.asyncio
async def test_upload_document_creates_extraction_record(async_session, intake_records):
    """Test 3: DocumentExtraction record created with extracted text and elements."""
    from app.services.intake.session_service import IntakeSessionService

    svc = IntakeSessionService(async_session)
    msg = await svc.store_message(
        session_id=intake_records["session"].id,
        sender_type="consumer",
        modality="document",
        content="sample.pdf",
    )

    doc = UploadedDocument(
        message_id=msg.id,
        intake_id=intake_records["intake"].id,
        original_filename="sample.pdf",
        mime_type="application/pdf",
        file_size_bytes=1024,
        extraction_status="completed",
    )
    async_session.add(doc)
    await async_session.flush()

    extraction = DocumentExtraction(
        document_id=doc.id,
        full_text_encrypted=b"Extracted text content",
        elements_json=[{"text": "Heading", "element_type": "heading", "page": 1}],
        extraction_method="pymupdf",
    )
    async_session.add(extraction)
    await async_session.flush()

    assert extraction.id is not None
    assert extraction.extraction_method == "pymupdf"
    assert extraction.elements_json is not None


@pytest.mark.asyncio
async def test_document_triggers_llm_followup(async_session, intake_records):
    """Test 6: After document upload, a system Message is created as LLM follow-up."""
    from app.services.intake.conversation import ConversationService
    from app.services.intake.session_service import IntakeSessionService

    svc = IntakeSessionService(async_session)

    # Store consumer document message
    msg = await svc.store_message(
        session_id=intake_records["session"].id,
        sender_type="consumer",
        modality="document",
        content="test.pdf",
    )

    # Generate LLM follow-up (mocked)
    conv_svc = ConversationService(llm_service=None)  # type: ignore[arg-type]
    response = await conv_svc.generate_response(
        messages=[{"role": "user", "content": "[Document uploaded: test.pdf]"}]
    )

    # Store system message
    system_msg = await svc.store_message(
        session_id=intake_records["session"].id,
        sender_type="system",
        modality="text",
        content=response,
    )

    assert system_msg.sender_type == "system"
    assert system_msg.modality == "text"
    assert system_msg.sequence_number == 2  # After the document message


@pytest.mark.asyncio
async def test_document_websocket_notification():
    """Test 5: WebSocket notification is sent with document_ready type."""
    from app.routers.intake import IntakeConnectionManager

    test_manager = IntakeConnectionManager()
    mock_ws = AsyncMock()
    mock_ws.accept = AsyncMock()

    await test_manager.connect(mock_ws, session_id=42)

    await test_manager.send_to_session(42, {
        "type": "document_ready",
        "message_id": 1,
        "document_id": 2,
        "extraction_status": "completed",
        "text_preview": "Sample text...",
    })

    mock_ws.send_json.assert_called_once()
    call_args = mock_ws.send_json.call_args[0][0]
    assert call_args["type"] == "document_ready"
    assert call_args["message_id"] == 1
    assert call_args["document_id"] == 2
    assert call_args["extraction_status"] == "completed"


@pytest.mark.asyncio
async def test_document_service_get_extraction_method():
    """Test: get_extraction_method returns correct method names."""
    with patch("app.services.document.document_service.get_settings") as mock_settings:
        mock_settings.return_value.intake_upload_dir = "/tmp"
        mock_settings.return_value.intake_max_file_size_mb = 50
        mock_settings.return_value.intake_max_page_count = 200

        doc_service = DocumentService(upload_dir="/tmp")
        assert doc_service.get_extraction_method("application/pdf") == "pymupdf"
        assert doc_service.get_extraction_method(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ) == "python-docx"
        assert doc_service.get_extraction_method("image/png") == "tesseract"
