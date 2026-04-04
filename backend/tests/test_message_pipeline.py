"""Tests for intake DB models and message normalization pipeline.

Covers:
  - All 10 intake model column definitions (Intake, IntakeParty, IntakeSession, Message,
    AudioRecording, Transcript, UploadedDocument, DocumentExtraction, ExtractedFact, FactSourceSpan)
  - Config settings for intake, ASR, and file storage
  - NormalizedContent dataclass fields
  - normalize_text and normalize_professional_note functions
  - process_message dispatcher
"""

import pytest
from sqlalchemy import inspect as sa_inspect

from app.models.intake import Intake, IntakeParty, IntakeSession, Message
from app.models.audio import AudioRecording, Transcript
from app.models.document import UploadedDocument, DocumentExtraction
from app.models.fact import ExtractedFact, FactSourceSpan
from app.services.intake.message_pipeline import (
    NormalizedContent,
    SourceSpan,
    TextElement,
    normalize_professional_note,
    normalize_text,
    process_message,
)


# ---------------------------------------------------------------------------
# Helper: extract column names from a model class via SQLAlchemy inspection
# ---------------------------------------------------------------------------

def _col_names(model_cls) -> set[str]:
    mapper = sa_inspect(model_cls)
    return {c.key for c in mapper.column_attrs}


# ---------------------------------------------------------------------------
# Model column tests
# ---------------------------------------------------------------------------

class TestIntakeModel:
    def test_intake_columns(self):
        cols = _col_names(Intake)
        for expected in (
            "id", "org_id", "status", "created_by_user_id",
            "session_mode", "metadata_json", "created_at", "updated_at",
        ):
            assert expected in cols, f"Intake missing column '{expected}'"

    def test_intake_tablename(self):
        assert Intake.__tablename__ == "intakes"


class TestIntakePartyModel:
    def test_intake_party_columns(self):
        cols = _col_names(IntakeParty)
        for expected in ("id", "intake_id", "user_id", "role_in_intake", "label", "created_at"):
            assert expected in cols, f"IntakeParty missing column '{expected}'"

    def test_intake_party_tablename(self):
        assert IntakeParty.__tablename__ == "intake_parties"


class TestIntakeSessionModel:
    def test_intake_session_columns(self):
        cols = _col_names(IntakeSession)
        for expected in ("id", "intake_id", "status", "started_at", "ended_at"):
            assert expected in cols, f"IntakeSession missing column '{expected}'"

    def test_intake_session_tablename(self):
        assert IntakeSession.__tablename__ == "intake_sessions"


class TestMessageModel:
    def test_message_columns(self):
        cols = _col_names(Message)
        for expected in (
            "id", "session_id", "party_id", "sender_type", "modality",
            "content_encrypted", "normalized_text", "metadata_json",
            "sequence_number", "created_at",
        ):
            assert expected in cols, f"Message missing column '{expected}'"

    def test_message_tablename(self):
        assert Message.__tablename__ == "messages"


class TestAudioRecordingModel:
    def test_audio_recording_columns(self):
        cols = _col_names(AudioRecording)
        for expected in (
            "id", "message_id", "intake_id", "file_path_encrypted",
            "original_format", "duration_seconds", "file_size_bytes",
            "storage_policy", "created_at",
        ):
            assert expected in cols, f"AudioRecording missing column '{expected}'"

    def test_audio_recording_tablename(self):
        assert AudioRecording.__tablename__ == "audio_recordings"


class TestTranscriptModel:
    def test_transcript_columns(self):
        cols = _col_names(Transcript)
        for expected in (
            "id", "recording_id", "text_encrypted", "status", "asr_provider",
            "segments_json", "language", "confidence", "created_at", "reviewed_at",
        ):
            assert expected in cols, f"Transcript missing column '{expected}'"

    def test_transcript_tablename(self):
        assert Transcript.__tablename__ == "transcripts"


class TestUploadedDocumentModel:
    def test_uploaded_document_columns(self):
        cols = _col_names(UploadedDocument)
        for expected in (
            "id", "message_id", "intake_id", "file_path_encrypted",
            "original_filename", "mime_type", "file_size_bytes",
            "page_count", "extraction_status", "created_at",
        ):
            assert expected in cols, f"UploadedDocument missing column '{expected}'"

    def test_uploaded_document_tablename(self):
        assert UploadedDocument.__tablename__ == "uploaded_documents"


class TestDocumentExtractionModel:
    def test_document_extraction_columns(self):
        cols = _col_names(DocumentExtraction)
        for expected in (
            "id", "document_id", "full_text_encrypted", "elements_json",
            "extraction_method", "created_at",
        ):
            assert expected in cols, f"DocumentExtraction missing column '{expected}'"

    def test_document_extraction_tablename(self):
        assert DocumentExtraction.__tablename__ == "document_extractions"


class TestExtractedFactModel:
    def test_extracted_fact_columns(self):
        cols = _col_names(ExtractedFact)
        for expected in (
            "id", "intake_id", "message_id", "party_id", "assertion_text",
            "fact_type", "entity_type", "confidence", "is_active",
            "superseded_by_id", "visibility", "metadata_json", "created_at",
        ):
            assert expected in cols, f"ExtractedFact missing column '{expected}'"

    def test_extracted_fact_tablename(self):
        assert ExtractedFact.__tablename__ == "extracted_facts"


class TestFactSourceSpanModel:
    def test_fact_source_span_columns(self):
        cols = _col_names(FactSourceSpan)
        for expected in (
            "id", "fact_id", "message_id", "start_char", "end_char",
            "timestamp_start_sec", "timestamp_end_sec",
            "page_number", "paragraph_index",
        ):
            assert expected in cols, f"FactSourceSpan missing column '{expected}'"

    def test_fact_source_span_tablename(self):
        assert FactSourceSpan.__tablename__ == "fact_source_spans"


# ---------------------------------------------------------------------------
# Config settings tests
# ---------------------------------------------------------------------------

class TestConfigSettings:
    def test_intake_config_fields(self):
        from app.config import Settings

        # Verify fields exist with defaults
        s = Settings(secret_key="test")
        assert s.intake_upload_dir == "./data/uploads"
        assert s.intake_max_file_size_mb == 50
        assert s.intake_max_page_count == 200
        assert s.intake_max_recording_duration_sec == 900
        assert s.intake_default_session_mode == "multi_session"
        assert s.intake_fact_visibility == "internal"

    def test_asr_config_fields(self):
        from app.config import Settings

        s = Settings(secret_key="test")
        assert s.asr_default_provider == "whisper"
        assert s.whisper_endpoint == "http://localhost:8790"
        assert s.asr_audio_storage_policy == "store_both"


# ---------------------------------------------------------------------------
# NormalizedContent dataclass tests
# ---------------------------------------------------------------------------

class TestNormalizedContentDataclass:
    def test_normalized_content_has_fields(self):
        nc = NormalizedContent(
            text="hello",
            elements=[],
            source_type="chat",
            source_id="msg-1",
            source_spans=[],
            party_id=None,
        )
        assert nc.text == "hello"
        assert nc.elements == []
        assert nc.source_type == "chat"
        assert nc.source_id == "msg-1"
        assert nc.source_spans == []
        assert nc.party_id is None

    def test_normalized_content_with_party_id(self):
        nc = NormalizedContent(
            text="hi",
            elements=[],
            source_type="chat",
            source_id="msg-2",
            source_spans=[],
            party_id=42,
        )
        assert nc.party_id == 42


# ---------------------------------------------------------------------------
# normalize_text tests
# ---------------------------------------------------------------------------

class TestNormalizeText:
    def test_normalize_text_returns_normalized_content(self):
        result = normalize_text("My landlord won't return my deposit", message_id=1)
        assert isinstance(result, NormalizedContent)
        assert result.text == "My landlord won't return my deposit"
        assert result.source_type == "chat"

    def test_normalize_text_source_span_covers_full_text(self):
        content = "Hello world"
        result = normalize_text(content, message_id=5)
        assert len(result.source_spans) == 1
        span = result.source_spans[0]
        assert span.start_char == 0
        assert span.end_char == len(content)

    def test_normalize_text_single_paragraph_element(self):
        result = normalize_text("Some text", message_id=1)
        assert len(result.elements) == 1
        assert result.elements[0].element_type == "paragraph"

    def test_normalize_text_with_party_id(self):
        result = normalize_text("content", message_id=1, party_id=7)
        assert result.party_id == 7


# ---------------------------------------------------------------------------
# normalize_professional_note tests
# ---------------------------------------------------------------------------

class TestNormalizeProfessionalNote:
    def test_normalize_professional_note_source_type(self):
        result = normalize_professional_note("Client appears distressed", message_id=10)
        assert isinstance(result, NormalizedContent)
        assert result.source_type == "professional_note"


# ---------------------------------------------------------------------------
# process_message dispatcher tests
# ---------------------------------------------------------------------------

class TestProcessMessage:
    @pytest.mark.asyncio
    async def test_process_text_message(self):
        result = await process_message("text", "Hello", message_id=1)
        assert isinstance(result, NormalizedContent)
        assert result.source_type == "chat"
        assert result.text == "Hello"

    @pytest.mark.asyncio
    async def test_process_professional_note_message(self):
        result = await process_message("professional_note", "Note content", message_id=2)
        assert isinstance(result, NormalizedContent)
        assert result.source_type == "professional_note"

    @pytest.mark.asyncio
    async def test_process_voice_returns_voice_transcript(self):
        result = await process_message("voice", "transcribed speech", message_id=3)
        assert isinstance(result, NormalizedContent)
        assert result.source_type == "voice_transcript"
        assert result.text == "transcribed speech"

    @pytest.mark.asyncio
    async def test_process_document_raises_not_implemented(self):
        with pytest.raises(NotImplementedError):
            await process_message("document", "doc data", message_id=4)
