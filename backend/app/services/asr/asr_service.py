"""Pluggable ASR service with per-org provider configuration.

Mirrors the LLMService pattern: _ASR_PROVIDER_MAP maps provider names to
classes, ASRService resolves the provider from org config or platform defaults,
and delegates transcription calls.

Audio format conversion handles browser-native formats (WebM/Opus) by
converting to WAV for providers that need PCM input.
"""

from __future__ import annotations

import asyncio
from io import BytesIO
from typing import TYPE_CHECKING, Any

from app.config import get_settings
from app.services.asr.providers.assemblyai_provider import AssemblyAIProvider
from app.services.asr.providers.base import ASRProviderBase, TranscriptionResult
from app.services.asr.providers.deepgram_provider import DeepgramProvider
from app.services.asr.providers.whisper_provider import WhisperProvider

if TYPE_CHECKING:
    from app.models.organization import OrganizationConfig

# Provider name -> class mapping (mirrors _PROVIDER_MODEL_MAP in llm_service.py)
_ASR_PROVIDER_MAP: dict[str, type[ASRProviderBase]] = {
    "whisper": WhisperProvider,
    "deepgram": DeepgramProvider,
    "assemblyai": AssemblyAIProvider,
}

# Formats that need conversion to WAV for most ASR providers
_BROWSER_FORMATS = {"webm", "opus", "ogg"}


def _import_pydub():
    """Lazy-import pydub to avoid hard dependency."""
    try:
        from pydub import AudioSegment
        return AudioSegment
    except ImportError as e:
        raise ImportError(
            "pydub is required for audio format conversion. "
            "Install it with: pip install pydub"
        ) from e


# Expose AudioSegment at module level for test patching
try:
    from pydub import AudioSegment
except ImportError:
    AudioSegment = None  # type: ignore[assignment,misc]


async def convert_audio_format(
    audio_bytes: bytes,
    input_format: str,
    output_format: str = "wav",
) -> bytes:
    """Convert audio from one format to another using pydub.

    Runs in a thread executor since pydub/ffmpeg is CPU-bound.

    Args:
        audio_bytes: Raw audio data in input_format.
        input_format: Source format (e.g. "webm", "opus", "mp3").
        output_format: Target format (default "wav").

    Returns:
        Converted audio bytes in the output format.

    Raises:
        ImportError: If pydub is not installed.
    """
    _AudioSegment = AudioSegment or _import_pydub()

    def _convert() -> bytes:
        segment = _AudioSegment.from_file(BytesIO(audio_bytes), format=input_format)
        # For WAV output, convert to mono 16kHz (optimal for most ASR)
        if output_format == "wav":
            segment = segment.set_channels(1).set_frame_rate(16000)

        buf = BytesIO()
        segment.export(buf, format=output_format)
        return buf.getvalue()

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _convert)


class ASRService:
    """Pluggable ASR service with per-org provider configuration.

    Resolves the ASR provider from org config settings or falls back to the
    platform default (Settings.asr_default_provider). Converts browser-native
    audio formats before transcription when needed.
    """

    def __init__(self, org_config: Any | None = None) -> None:
        """Initialize ASR service, resolving the provider.

        Args:
            org_config: Per-org configuration with settings dict. If provided,
                        looks for "asr_provider" in org_config.settings.

        Raises:
            ValueError: If the resolved provider name is not in _ASR_PROVIDER_MAP.
        """
        settings = get_settings()

        # Resolve provider name from org config or platform default
        provider_name: str | None = None
        if org_config and hasattr(org_config, "settings") and org_config.settings:
            provider_name = org_config.settings.get("asr_provider")
        if not provider_name:
            provider_name = settings.asr_default_provider

        self._provider_name = provider_name

        # Look up provider class
        provider_cls = _ASR_PROVIDER_MAP.get(provider_name)
        if provider_cls is None:
            raise ValueError(
                f"Unknown ASR provider: '{provider_name}'. "
                f"Available: {', '.join(_ASR_PROVIDER_MAP.keys())}"
            )

        # Build provider kwargs
        kwargs: dict[str, Any] = {}
        if provider_name == "whisper":
            kwargs["endpoint"] = settings.whisper_endpoint
        elif provider_name == "deepgram":
            api_key = None
            if org_config and hasattr(org_config, "settings") and org_config.settings:
                api_key = org_config.settings.get("deepgram_api_key")
            kwargs["api_key"] = api_key
        elif provider_name == "assemblyai":
            api_key = None
            if org_config and hasattr(org_config, "settings") and org_config.settings:
                api_key = org_config.settings.get("assemblyai_api_key")
            kwargs["api_key"] = api_key

        self._provider: ASRProviderBase = provider_cls(**kwargs)

    @property
    def provider_name(self) -> str:
        """Return the resolved provider name string."""
        return self._provider_name

    @property
    def supports_streaming(self) -> bool:
        """Whether the current provider supports streaming transcription."""
        return self._provider.supports_streaming

    @property
    def supports_diarization(self) -> bool:
        """Whether the current provider supports speaker diarization."""
        return self._provider.supports_diarization

    async def transcribe(
        self,
        audio_bytes: bytes,
        format: str,
        **kwargs: Any,
    ) -> TranscriptionResult:
        """Transcribe audio, converting format if needed.

        Browser-native formats (WebM/Opus/OGG) are converted to WAV before
        sending to providers that don't accept them natively.

        Args:
            audio_bytes: Raw audio data.
            format: Audio format identifier.
            **kwargs: Passed through to provider.transcribe.

        Returns:
            TranscriptionResult from the ASR provider.
        """
        # Convert browser formats to WAV for compatibility
        actual_format = format.lower()
        actual_bytes = audio_bytes

        if actual_format in _BROWSER_FORMATS:
            try:
                actual_bytes = await convert_audio_format(audio_bytes, actual_format, "wav")
                actual_format = "wav"
            except ImportError:
                # pydub not available -- send raw format and hope provider handles it
                pass

        return await self._provider.transcribe(actual_bytes, actual_format, **kwargs)
