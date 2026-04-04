"""AssemblyAI ASR provider via cloud SDK.

Requires the `assemblyai` package (optional dependency). Supports
speaker diarization but not streaming in the prerecorded mode.
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.services.asr.providers.base import ASRProviderBase, TranscriptionResult


class AssemblyAIProvider(ASRProviderBase):
    """Cloud ASR via AssemblyAI SDK with diarization support."""

    def __init__(self, api_key: str | None = None, **kwargs: Any) -> None:
        """Initialize with AssemblyAI API key.

        Args:
            api_key: AssemblyAI API key. Falls back to org_config if provided.
            **kwargs: May contain org_config for key extraction.
        """
        self._api_key = api_key
        if not self._api_key and "org_config" in kwargs:
            org_config = kwargs["org_config"]
            if hasattr(org_config, "settings") and org_config.settings:
                self._api_key = org_config.settings.get("assemblyai_api_key")

    async def transcribe(
        self,
        audio_bytes: bytes,
        format: str,
        **kwargs: Any,
    ) -> TranscriptionResult:
        """Transcribe audio using AssemblyAI's API.

        The AssemblyAI SDK is synchronous, so we run it in a thread executor.

        Args:
            audio_bytes: Raw audio data.
            format: Audio format identifier.
            **kwargs: Optional diarize (bool).

        Returns:
            TranscriptionResult parsed from AssemblyAI response.

        Raises:
            ImportError: If assemblyai package is not installed.
        """
        import assemblyai as aai

        if self._api_key:
            aai.settings.api_key = self._api_key

        def _transcribe_sync() -> TranscriptionResult:
            config = aai.TranscriptionConfig(
                speaker_labels=kwargs.get("diarize", False),
            )
            transcriber = aai.Transcriber()
            transcript = transcriber.transcribe(audio_bytes, config=config)

            # Build segments from words if available
            segments: list[dict] = []
            if transcript.words:
                segments = [
                    {
                        "start": w.start / 1000.0,  # ms -> seconds
                        "end": w.end / 1000.0,
                        "text": w.text,
                        "speaker": getattr(w, "speaker", None),
                    }
                    for w in transcript.words
                ]

            return TranscriptionResult(
                text=transcript.text or "",
                segments=segments,
                language=getattr(transcript, "language_code", None),
                confidence=getattr(transcript, "confidence", None),
            )

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _transcribe_sync)

    @property
    def supports_diarization(self) -> bool:
        """AssemblyAI supports speaker diarization."""
        return True
