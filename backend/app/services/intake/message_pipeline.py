"""Unified message normalization pipeline.

All input modalities (text, voice, document, professional notes) normalize
into a common NormalizedContent representation for downstream processing.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TextElement:
    """A structural element within normalized text."""

    text: str
    element_type: str  # "paragraph", "heading", "table", "list_item"
    page: int | None = None
    section_path: str | None = None


@dataclass
class SourceSpan:
    """Source location metadata for traceability."""

    start_char: int
    end_char: int
    source_message_id: int | None = None
    source_timestamp_start: float | None = None
    source_timestamp_end: float | None = None
    source_page: int | None = None
    source_paragraph: int | None = None


@dataclass
class NormalizedContent:
    """Common representation for all input modalities."""

    text: str
    elements: list[TextElement] = field(default_factory=list)
    source_type: str = "chat"
    source_id: str = ""
    source_spans: list[SourceSpan] = field(default_factory=list)
    party_id: int | None = None


def normalize_text(
    content: str, message_id: int, party_id: int | None = None
) -> NormalizedContent:
    """Normalize plain text chat input."""
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


def normalize_professional_note(
    content: str, message_id: int, party_id: int | None = None
) -> NormalizedContent:
    """Normalize professional note input."""
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
    """Route to appropriate normalizer based on modality."""
    if modality == "text":
        return normalize_text(content, message_id, party_id)
    elif modality == "professional_note":
        return normalize_professional_note(content, message_id, party_id)
    elif modality in ("voice", "document"):
        raise NotImplementedError(
            "Voice/document normalization handled by respective services"
        )
    else:
        raise ValueError(f"Unknown modality: {modality}")
