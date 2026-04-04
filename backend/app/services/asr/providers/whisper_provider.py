"""Whisper ASR provider via local sidecar HTTP service.

Sends audio to a local Whisper-compatible HTTP endpoint (e.g. faster-whisper
served via a simple FastAPI sidecar). No cloud dependency, no API key needed.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.services.asr.providers.base import ASRProviderBase, TranscriptionResult


class WhisperProvider(ASRProviderBase):
    """Local Whisper ASR via sidecar HTTP service.

    Posts audio files to {endpoint}/transcribe and parses the JSON response
    into a TranscriptionResult.
    """

    def __init__(self, endpoint: str = "http://localhost:8790", **kwargs: Any) -> None:
        """Initialize with sidecar endpoint URL.

        Args:
            endpoint: Base URL of the Whisper sidecar service.
            **kwargs: Accepts and ignores org_config for interface consistency.
        """
        self._endpoint = endpoint.rstrip("/")

    async def transcribe(
        self,
        audio_bytes: bytes,
        format: str,
        **kwargs: Any,
    ) -> TranscriptionResult:
        """Transcribe audio by POSTing to the Whisper sidecar.

        Args:
            audio_bytes: Raw audio data.
            format: Audio format (e.g. "wav", "webm").
            **kwargs: Optional language hint.

        Returns:
            TranscriptionResult parsed from the sidecar JSON response.

        Raises:
            httpx.HTTPStatusError: On non-2xx response from sidecar.
        """
        language = kwargs.get("language", "en")

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self._endpoint}/transcribe",
                files={"audio": (f"audio.{format}", audio_bytes)},
                data={"language": language},
            )
            response.raise_for_status()

        data = response.json()
        return TranscriptionResult(
            text=data["text"],
            segments=data.get("segments", []),
            language=data.get("language"),
            confidence=data.get("confidence"),
        )
