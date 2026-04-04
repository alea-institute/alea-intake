"""Unified message normalization pipeline for all intake modalities.

Converts raw input from text, voice transcripts, professional notes, and
document extractions into a common NormalizedContent representation with
source spans for provenance tracking.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field


@dataclass
class TextElement:
    """A structural element within normalized content."""

    text: str
    element_type: str  # "paragraph", "heading", "table", "list_item"
    page: int | None = None
    section_path: str | None = None


@dataclass
class SourceSpan:
    """Locates a span of content within its original source."""

    start_char: int
    end_char: int
    source_message_id: int | None = None
    source_timestamp_start: float | None = None
    source_timestamp_end: float | None = None
    source_page: int | None = None
    source_paragraph: int | None = None


@dataclass
class NormalizedContent:
    """Common representation for all intake modalities after normalization."""

    text: str
    elements: list[TextElement] = field(default_factory=list)
    source_type: str = "chat"
    source_id: str = ""
    source_spans: list[SourceSpan] = field(default_factory=list)
    party_id: int | None = None


def normalize_text(
    content: str,
    message_id: int,
    party_id: int | None = None,
) -> NormalizedContent:
    """Normalize a plain text chat message into NormalizedContent.

    Creates a single paragraph TextElement and a SourceSpan covering the full text.
    """
    return NormalizedContent(
        text=content,
        elements=[TextElement(text=content, element_type="paragraph")],
        source_type="chat",
        source_id=f"msg-{message_id}",
        source_spans=[
            SourceSpan(
                start_char=0,
                end_char=len(content),
                source_message_id=message_id,
            )
        ],
        party_id=party_id,
    )


def normalize_professional_note(
    content: str,
    message_id: int,
    party_id: int | None = None,
) -> NormalizedContent:
    """Normalize a professional note into NormalizedContent.

    Same structure as text normalization but with source_type="professional_note".
    """
    return NormalizedContent(
        text=content,
        elements=[TextElement(text=content, element_type="paragraph")],
        source_type="professional_note",
        source_id=f"msg-{message_id}",
        source_spans=[
            SourceSpan(
                start_char=0,
                end_char=len(content),
                source_message_id=message_id,
            )
        ],
        party_id=party_id,
    )


def normalize_voice_transcript(
    content: str,
    message_id: int,
    party_id: int | None = None,
    **kwargs,
) -> NormalizedContent:
    """Normalize a voice transcript into NormalizedContent.

    Voice transcripts are already text (from ASR), so normalization creates
    a single paragraph element with source_type="voice_transcript". Timestamp
    spans from ASR segments can be attached via kwargs in a future enhancement.
    """
    return NormalizedContent(
        text=content,
        elements=[TextElement(text=content, element_type="paragraph")],
        source_type="voice_transcript",
        source_id=f"msg-{message_id}",
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
    """Route a message to the appropriate normalizer based on modality.

    Args:
        modality: One of "text", "professional_note", "voice", "document".
        content: The raw content string.
        message_id: DB message ID for source tracking.
        party_id: Optional party ID for multi-party attribution.
        **kwargs: Additional arguments passed to modality-specific normalizers.

    Returns:
        NormalizedContent with text, elements, source_type, and source_spans.

    Raises:
        NotImplementedError: For "document" modality (wired in Plan 03).
    """
    if modality == "text":
        return normalize_text(content, message_id, party_id)
    elif modality == "professional_note":
        return normalize_professional_note(content, message_id, party_id)
    elif modality == "voice":
        return normalize_voice_transcript(content, message_id, party_id, **kwargs)
    elif modality == "document":
        from app.services.document import DocumentService

        file_path = kwargs["file_path"]
        mime_type = kwargs["mime_type"]
        doc_service = DocumentService()
        return await doc_service.process_document(file_path, mime_type, message_id, party_id)
    else:
        raise ValueError(f"Unknown modality: {modality}")
