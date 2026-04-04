"""ASR provider abstract base class and shared data structures.

All ASR providers implement ASRProviderBase, producing TranscriptionResult
instances that flow into the intake pipeline for review and normalization.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TranscriptionResult:
    """Result returned by any ASR provider after transcription.

    Attributes:
        text: Full transcript text.
        segments: List of segment dicts with keys: start (float), end (float),
                  text (str), speaker (str|None).
        language: Detected language code (e.g. "en"), or None.
        confidence: Overall confidence score 0.0-1.0, or None.
    """

    text: str
    segments: list[dict] = field(default_factory=list)
    language: str | None = None
    confidence: float | None = None


class ASRProviderBase(ABC):
    """Abstract base class for pluggable ASR providers.

    Mirrors the LLMService provider pattern: each provider implements
    transcribe(), and optionally streaming/diarization.
    """

    @abstractmethod
    async def transcribe(
        self,
        audio_bytes: bytes,
        format: str,
        **kwargs: Any,
    ) -> TranscriptionResult:
        """Transcribe audio bytes into text with segments and metadata.

        Args:
            audio_bytes: Raw audio data.
            format: Audio format identifier (e.g. "wav", "webm", "mp3").
            **kwargs: Provider-specific options (language, diarize, etc.).

        Returns:
            TranscriptionResult with transcript text, segments, and metadata.
        """

    async def transcribe_streaming(
        self,
        audio_stream: AsyncIterator[bytes],
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream-transcribe audio chunks into partial transcript strings.

        Default implementation raises NotImplementedError. Override in
        providers that support real-time streaming (e.g. Deepgram).
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support streaming transcription"
        )
        # Make this an async generator to satisfy type checking
        yield ""  # pragma: no cover

    @property
    def supports_streaming(self) -> bool:
        """Whether this provider supports streaming transcription."""
        return False

    @property
    def supports_diarization(self) -> bool:
        """Whether this provider supports speaker diarization."""
        return False
