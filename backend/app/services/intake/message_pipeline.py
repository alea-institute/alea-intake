"""Unified message normalization pipeline for all intake modalities.

Normalizes text, voice transcripts, document extractions, and professional
notes into a common NormalizedContent representation with source spans
for provenance tracking.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TextElement:
    """A structural element extracted from content (paragraph, heading, table, etc.)."""

    text: str
    element_type: str  # paragraph, heading, table, list_item
    page: int | None = None
    section_path: str | None = None


@dataclass
class SourceSpan:
    """A span linking normalized content back to its original source."""

    start_char: int
    end_char: int
    source_message_id: int | None = None
    source_timestamp_start: float | None = None
    source_timestamp_end: float | None = None
    source_page: int | None = None
    source_paragraph: int | None = None


@dataclass
class NormalizedContent:
    """The common representation for all intake message content."""

    text: str
    elements: list[TextElement]
    source_type: str  # chat, voice_transcript, document, professional_note
    source_id: str
    source_spans: list[SourceSpan]
    party_id: int | None = None


def normalize_text(content: str, message_id: int, party_id: int | None = None) -> NormalizedContent:
    """Normalize a plain text message into NormalizedContent."""
    return NormalizedContent(
        text=content,
        elements=[TextElement(text=content, element_type="paragraph")],
        source_type="chat",
        source_id=str(message_id),
        source_spans=[
            SourceSpan(
                start_char=0,
                end_char=len(content),
                source_message_id=message_id,
            )
        ],
        party_id=party_id,
    )


def normalize_professional_note(content: str, message_id: int, party_id: int | None = None) -> NormalizedContent:
    """Normalize a professional note into NormalizedContent."""
    return NormalizedContent(
        text=content,
        elements=[TextElement(text=content, element_type="paragraph")],
        source_type="professional_note",
        source_id=str(message_id),
        source_spans=[
            SourceSpan(
                start_char=0,
                end_char=len(content),
                source_message_id=message_id,
            )
        ],
        party_id=party_id,
    )


async def process_message(
    modality: str,
    content: str,
    message_id: int,
    party_id: int | None = None,
    **kwargs,
) -> NormalizedContent:
    """Route message to the appropriate normalizer based on modality.

    Args:
        modality: The message modality (text, voice, document, professional_note).
        content: The message content (text string or extracted text).
        message_id: The DB message ID for source tracking.
        party_id: Optional party ID for multi-party attribution.
        **kwargs: Additional arguments (file_path, mime_type for document modality).

    Returns:
        NormalizedContent with source spans and structural elements.

    Raises:
        NotImplementedError: For voice modality (handled by ASR service directly).
        ValueError: For unknown modalities.
    """
    if modality == "text":
        return normalize_text(content, message_id, party_id)
    elif modality == "professional_note":
        return normalize_professional_note(content, message_id, party_id)
    elif modality == "document":
        # Delegate to DocumentService for document processing
        from app.services.document import DocumentService

        file_path = kwargs["file_path"]
        mime_type = kwargs["mime_type"]
        doc_service = DocumentService()
        return await doc_service.process_document(file_path, mime_type, message_id, party_id)
    elif modality == "voice":
        raise NotImplementedError("Voice normalization handled by ASR service directly")
    else:
        raise ValueError(f"Unknown modality: {modality}")
