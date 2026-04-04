"""Deepgram ASR provider via cloud SDK.

Requires the `deepgram-sdk` package (optional dependency). Supports
streaming transcription and speaker diarization.
"""

from __future__ import annotations

from typing import Any

from app.services.asr.providers.base import ASRProviderBase, TranscriptionResult


class DeepgramProvider(ASRProviderBase):
    """Cloud ASR via Deepgram SDK with streaming and diarization support."""

    def __init__(self, api_key: str | None = None, **kwargs: Any) -> None:
        """Initialize with Deepgram API key.

        Args:
            api_key: Deepgram API key. Falls back to org_config if provided.
            **kwargs: May contain org_config for key extraction.
        """
        self._api_key = api_key
        if not self._api_key and "org_config" in kwargs:
            org_config = kwargs["org_config"]
            if hasattr(org_config, "settings") and org_config.settings:
                self._api_key = org_config.settings.get("deepgram_api_key")

    async def transcribe(
        self,
        audio_bytes: bytes,
        format: str,
        **kwargs: Any,
    ) -> TranscriptionResult:
        """Transcribe audio using Deepgram's prerecorded API.

        Args:
            audio_bytes: Raw audio data.
            format: Audio format identifier (e.g. "webm", "wav").
            **kwargs: Optional diarize (bool).

        Returns:
            TranscriptionResult parsed from Deepgram response.

        Raises:
            ImportError: If deepgram-sdk is not installed.
        """
        from deepgram import DeepgramClient, PrerecordedOptions

        client = DeepgramClient(self._api_key)
        options = PrerecordedOptions(
            model="nova-2",
            smart_format=True,
            diarize=kwargs.get("diarize", False),
        )

        response = await client.listen.asyncrest.v("1").transcribe_file(
            source={"buffer": audio_bytes, "mimetype": f"audio/{format}"},
            options=options,
        )

        # Parse the Deepgram response structure
        channel = response.results.channels[0]
        alt = channel.alternatives[0]

        # Build segments from words
        segments: list[dict] = []
        if alt.words:
            segments = [
                {
                    "start": w.start,
                    "end": w.end,
                    "text": w.word,
                    "speaker": getattr(w, "speaker", None),
                }
                for w in alt.words
            ]

        return TranscriptionResult(
            text=alt.transcript,
            segments=segments,
            language=getattr(channel, "detected_language", None),
            confidence=alt.confidence,
        )

    @property
    def supports_streaming(self) -> bool:
        """Deepgram supports real-time streaming transcription."""
        return True

    @property
    def supports_diarization(self) -> bool:
        """Deepgram supports speaker diarization."""
        return True
