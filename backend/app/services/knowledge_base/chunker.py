"""Semantic chunker with paragraph/heading boundary respect and overlap.

Splits text into ~500-token chunks respecting paragraph boundaries and
preserving headings with their content. Each chunk overlaps with the
previous chunk by a configurable number of tokens.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ChunkResult:
    """A single semantic chunk with metadata."""

    content: str
    heading: str | None
    chunk_index: int
    token_count: int
    start_offset: int
    end_offset: int


# Markdown heading pattern: # ## ### etc.
_MD_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

# Uppercase-line heading: all caps, at least 3 chars, no lowercase
_UPPERCASE_HEADING_RE = re.compile(r"^([A-Z][A-Z\s\-:,.]{2,})$", re.MULTILINE)


def _tokenize(text: str) -> list[str]:
    """Simple whitespace tokenization for token counting."""
    return text.split()


def _token_count(text: str) -> int:
    """Count tokens using whitespace splitting."""
    return len(_tokenize(text))


def _detect_heading(line: str) -> str | None:
    """Detect whether a line is a heading (Markdown or uppercase).

    Returns the heading text (without # prefix) or None.
    """
    line = line.strip()
    if not line:
        return None

    # Markdown heading
    md_match = re.match(r"^(#{1,6})\s+(.+)$", line)
    if md_match:
        return md_match.group(2).strip()

    # Uppercase-line heading: all uppercase, 3+ chars, mostly letters
    if (
        len(line) >= 3
        and line == line.upper()
        and any(c.isalpha() for c in line)
        and sum(1 for c in line if c.isalpha()) / max(len(line), 1) > 0.5
    ):
        return line.strip()

    return None


class SemanticChunker:
    """Semantic text chunker with paragraph/heading boundary respect.

    Splits text by paragraph boundaries (\n\n), detects headings,
    and produces chunks within the max_tokens limit with overlap.
    """

    def chunk(
        self,
        text: str,
        max_tokens: int = 500,
        overlap: int = 50,
    ) -> list[ChunkResult]:
        """Split text into semantic chunks.

        Args:
            text: The input text to chunk.
            max_tokens: Maximum tokens per chunk (~500).
            overlap: Number of tokens to overlap between consecutive chunks (~50).

        Returns:
            List of ChunkResult with content, heading, offsets, and token counts.
        """
        if not text or not text.strip():
            return []

        # Split into sections by headings and paragraphs
        sections = self._split_into_sections(text)

        # Build chunks respecting token limits
        raw_chunks = self._build_chunks(sections, max_tokens)

        # Apply overlap between consecutive chunks
        final_chunks = self._apply_overlap(raw_chunks, overlap, text)

        return final_chunks

    def _split_into_sections(self, text: str) -> list[dict]:
        """Split text into sections, each with optional heading and content paragraphs.

        Returns list of dicts: {"heading": str|None, "content": str, "offset": int}
        """
        sections: list[dict] = []
        # Split by double newlines (paragraph boundaries)
        parts = re.split(r"\n\n+", text)
        offset = 0

        current_heading: str | None = None

        for part in parts:
            part_stripped = part.strip()
            if not part_stripped:
                # Track offset past empty section
                offset = text.find(part, offset) + len(part)
                continue

            # Find this part's position in original text
            part_offset = text.find(part_stripped, offset)
            if part_offset == -1:
                part_offset = offset

            # Check if first line is a heading
            first_line = part_stripped.split("\n")[0]
            detected = _detect_heading(first_line)

            if detected is not None:
                current_heading = detected
                # Content is everything after the heading line
                rest = part_stripped[len(first_line):].strip()
                if rest:
                    sections.append({
                        "heading": current_heading,
                        "content": rest,
                        "offset": part_offset,
                    })
                else:
                    # Heading-only section: next content block will get this heading
                    # Store as empty section so heading is preserved
                    sections.append({
                        "heading": current_heading,
                        "content": "",
                        "offset": part_offset,
                    })
            else:
                sections.append({
                    "heading": current_heading,
                    "content": part_stripped,
                    "offset": part_offset,
                })

            offset = part_offset + len(part_stripped)

        # Merge consecutive empty-content sections into the next non-empty section
        merged: list[dict] = []
        pending_heading: str | None = None
        for sec in sections:
            if not sec["content"] and sec["heading"]:
                pending_heading = sec["heading"]
            else:
                if pending_heading and not sec["heading"]:
                    sec["heading"] = pending_heading
                elif pending_heading and sec["heading"]:
                    pass  # Keep section's own heading
                pending_heading = None
                merged.append(sec)

        # If there are only heading-only sections with no content, create minimal chunks
        if not merged and sections:
            for sec in sections:
                if sec["heading"]:
                    merged.append({
                        "heading": sec["heading"],
                        "content": sec["heading"],
                        "offset": sec["offset"],
                    })

        return merged

    def _build_chunks(
        self, sections: list[dict], max_tokens: int
    ) -> list[dict]:
        """Build chunks from sections, grouping small sections together.

        Returns list of dicts: {"heading": str|None, "content": str, "offset": int}
        """
        chunks: list[dict] = []
        current_content: list[str] = []
        current_heading: str | None = None
        current_offset: int = 0
        current_tokens: int = 0

        for sec in sections:
            sec_tokens = _token_count(sec["content"]) if sec["content"] else 0

            if sec_tokens > max_tokens:
                # Flush current accumulator
                if current_content:
                    chunks.append({
                        "heading": current_heading,
                        "content": "\n\n".join(current_content),
                        "offset": current_offset,
                    })
                    current_content = []
                    current_tokens = 0
                    current_heading = None

                # Split large section by sentences
                sentences = self._split_by_sentences(sec["content"])
                sent_chunk: list[str] = []
                sent_tokens: int = 0
                sent_offset: int = sec["offset"]

                for sent in sentences:
                    st = _token_count(sent)
                    if sent_tokens + st > max_tokens and sent_chunk:
                        chunks.append({
                            "heading": sec["heading"],
                            "content": " ".join(sent_chunk),
                            "offset": sent_offset,
                        })
                        sent_chunk = []
                        sent_tokens = 0
                        sent_offset = sec["offset"]

                    sent_chunk.append(sent)
                    sent_tokens += st

                if sent_chunk:
                    chunks.append({
                        "heading": sec["heading"],
                        "content": " ".join(sent_chunk),
                        "offset": sent_offset,
                    })
            else:
                # Accumulate sections into a single chunk
                if current_tokens + sec_tokens > max_tokens and current_content:
                    # Flush
                    chunks.append({
                        "heading": current_heading,
                        "content": "\n\n".join(current_content),
                        "offset": current_offset,
                    })
                    current_content = []
                    current_tokens = 0
                    current_heading = None

                if not current_content:
                    current_heading = sec["heading"]
                    current_offset = sec["offset"]

                if sec["content"]:
                    current_content.append(sec["content"])
                    current_tokens += sec_tokens

        # Flush remaining
        if current_content:
            chunks.append({
                "heading": current_heading,
                "content": "\n\n".join(current_content),
                "offset": current_offset,
            })

        return chunks

    def _split_by_sentences(self, text: str) -> list[str]:
        """Split text into sentences, falling back to token-based splitting."""
        # Simple sentence splitting: split on '. ', '! ', '? ' and newlines
        sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
        sentences = [s.strip() for s in sentences if s.strip()]

        # Fallback: if only one "sentence" and it's very long, split by tokens
        if len(sentences) <= 1 and _token_count(text) > 100:
            tokens = _tokenize(text)
            # Split into ~100-token segments for further chunking
            segments: list[str] = []
            for i in range(0, len(tokens), 100):
                segments.append(" ".join(tokens[i : i + 100]))
            return segments

        return sentences

    def _apply_overlap(
        self, chunks: list[dict], overlap: int, original_text: str
    ) -> list[ChunkResult]:
        """Apply token overlap between consecutive chunks.

        Last `overlap` tokens of chunk N are prepended to chunk N+1.
        """
        if not chunks:
            return []

        results: list[ChunkResult] = []

        for i, chunk in enumerate(chunks):
            content = chunk["content"]

            if i > 0 and overlap > 0:
                # Get last `overlap` tokens from previous chunk
                prev_tokens = _tokenize(chunks[i - 1]["content"])
                overlap_tokens = prev_tokens[-overlap:] if len(prev_tokens) >= overlap else prev_tokens
                overlap_text = " ".join(overlap_tokens)
                content = overlap_text + " " + content

            tc = _token_count(content)

            # Calculate offsets in original text
            start = chunk["offset"]
            # Find end offset
            clean_content = chunk["content"]
            end_idx = original_text.find(clean_content, max(0, start - 10))
            if end_idx >= 0:
                end = end_idx + len(clean_content)
            else:
                end = start + len(clean_content)

            results.append(
                ChunkResult(
                    content=content,
                    heading=chunk["heading"],
                    chunk_index=i,
                    token_count=tc,
                    start_offset=start,
                    end_offset=end,
                )
            )

        return results
