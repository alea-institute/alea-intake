"""Tests for pluggable ASR service with provider architecture.

Covers:
  - TranscriptionResult dataclass structure
  - ASRProviderBase abstract interface and defaults
  - WhisperProvider: HTTP POST to sidecar, response parsing
  - DeepgramProvider: SDK delegation, streaming/diarization support
  - AssemblyAIProvider: SDK delegation, diarization support
  - ASRService: provider resolution from config, delegation, unknown provider error
  - _ASR_PROVIDER_MAP registry
  - Audio format conversion (pydub-based, mocked)
"""

from __future__ import annotations

import asyncio
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.asr.providers.base import ASRProviderBase, TranscriptionResult
from app.services.asr.providers.whisper_provider import WhisperProvider
from app.services.asr.providers.deepgram_provider import DeepgramProvider
from app.services.asr.providers.assemblyai_provider import AssemblyAIProvider
from app.services.asr.asr_service import ASRService, _ASR_PROVIDER_MAP, convert_audio_format


# ---------------------------------------------------------------------------
# Test 1: ASRProviderBase is abstract with abstract transcribe method
# ---------------------------------------------------------------------------

class TestASRProviderBase:
    def test_abstract_cannot_instantiate(self):
        """ASRProviderBase cannot be directly instantiated due to abstract transcribe."""
        with pytest.raises(TypeError):
            ASRProviderBase()

    def test_supports_streaming_defaults_false(self):
        """ASRProviderBase.supports_streaming defaults to False."""
        # Create a minimal concrete subclass
        class MinimalProvider(ASRProviderBase):
            async def transcribe(self, audio_bytes, format, **kwargs):
                return TranscriptionResult(text="", segments=[])

        provider = MinimalProvider()
        assert provider.supports_streaming is False

    def test_supports_diarization_defaults_false(self):
        """ASRProviderBase.supports_diarization defaults to False."""
        class MinimalProvider(ASRProviderBase):
            async def transcribe(self, audio_bytes, format, **kwargs):
                return TranscriptionResult(text="", segments=[])

        provider = MinimalProvider()
        assert provider.supports_diarization is False


# ---------------------------------------------------------------------------
# Test 4: TranscriptionResult dataclass
# ---------------------------------------------------------------------------

class TestTranscriptionResult:
    def test_dataclass_fields(self):
        """TranscriptionResult has text, segments, language, confidence fields."""
        result = TranscriptionResult(
            text="Hello world",
            segments=[{"start": 0.0, "end": 1.5, "text": "Hello world", "speaker": None}],
            language="en",
            confidence=0.95,
        )
        assert result.text == "Hello world"
        assert len(result.segments) == 1
        assert result.language == "en"
        assert result.confidence == 0.95

    def test_optional_fields_default_none(self):
        """TranscriptionResult language and confidence default to None."""
        result = TranscriptionResult(text="test", segments=[])
        assert result.language is None
        assert result.confidence is None


# ---------------------------------------------------------------------------
# Tests 5-6: WhisperProvider
# ---------------------------------------------------------------------------

class TestWhisperProvider:
    @pytest.mark.asyncio
    async def test_transcribe_sends_post_returns_result(self):
        """WhisperProvider.transcribe POSTs to {endpoint}/transcribe and parses response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "text": "test transcript",
            "segments": [{"start": 0.0, "end": 1.0, "text": "test transcript", "speaker": None}],
            "language": "en",
            "confidence": 0.92,
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.asr.providers.whisper_provider.httpx.AsyncClient", return_value=mock_client):
            provider = WhisperProvider(endpoint="http://localhost:8790")
            result = await provider.transcribe(b"fake audio bytes", "webm")

        assert isinstance(result, TranscriptionResult)
        assert result.text == "test transcript"
        assert len(result.segments) == 1
        assert result.language == "en"
        assert result.confidence == 0.92

        # Verify POST was called with correct endpoint
        mock_client.post.assert_awaited_once()
        call_args = mock_client.post.call_args
        assert "/transcribe" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_uses_120s_timeout(self):
        """WhisperProvider uses httpx.AsyncClient with 120s timeout."""
        with patch("app.services.asr.providers.whisper_provider.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"text": "ok", "segments": []}
            mock_response.raise_for_status = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            provider = WhisperProvider()
            await provider.transcribe(b"audio", "wav")

            # Check that AsyncClient was created with timeout=120.0
            mock_cls.assert_called_once()
            call_kwargs = mock_cls.call_args
            assert call_kwargs[1].get("timeout") == 120.0 or (call_kwargs[0] and call_kwargs[0][0] == 120.0) or call_kwargs[1].get("timeout") == 120.0


# ---------------------------------------------------------------------------
# Tests 7-9: DeepgramProvider
# ---------------------------------------------------------------------------

class TestDeepgramProvider:
    @pytest.mark.asyncio
    async def test_transcribe_calls_sdk(self):
        """DeepgramProvider.transcribe calls Deepgram SDK with audio bytes."""
        # Mock the deepgram module
        mock_deepgram_module = MagicMock()
        mock_client = MagicMock()
        mock_listen = MagicMock()
        mock_asyncrest = MagicMock()
        mock_v = MagicMock()

        # Build the mock chain: client.listen.asyncrest.v("1").transcribe_file(...)
        mock_result = MagicMock()
        mock_result.results.channels = [MagicMock()]
        mock_result.results.channels[0].alternatives = [MagicMock()]
        mock_result.results.channels[0].alternatives[0].transcript = "deepgram transcript"
        mock_result.results.channels[0].alternatives[0].confidence = 0.98
        mock_result.results.channels[0].alternatives[0].words = [
            MagicMock(start=0.0, end=1.0, word="deepgram"),
            MagicMock(start=1.0, end=2.0, word="transcript"),
        ]
        # Make detected_language available
        mock_result.results.channels[0].detected_language = "en"

        mock_v.transcribe_file = AsyncMock(return_value=mock_result)
        mock_asyncrest.v.return_value = mock_v
        mock_listen.asyncrest = mock_asyncrest
        mock_client.listen = mock_listen

        mock_deepgram_module.DeepgramClient.return_value = mock_client
        mock_deepgram_module.PrerecordedOptions = MagicMock

        with patch.dict("sys.modules", {"deepgram": mock_deepgram_module}):
            provider = DeepgramProvider(api_key="test-key")
            result = await provider.transcribe(b"audio bytes", "webm")

        assert isinstance(result, TranscriptionResult)
        assert result.text == "deepgram transcript"
        assert result.confidence == 0.98

    def test_supports_streaming_true(self):
        """DeepgramProvider.supports_streaming returns True."""
        provider = DeepgramProvider(api_key="test-key")
        assert provider.supports_streaming is True

    def test_supports_diarization_true(self):
        """DeepgramProvider.supports_diarization returns True."""
        provider = DeepgramProvider(api_key="test-key")
        assert provider.supports_diarization is True


# ---------------------------------------------------------------------------
# Test 10: AssemblyAIProvider
# ---------------------------------------------------------------------------

class TestAssemblyAIProvider:
    @pytest.mark.asyncio
    async def test_transcribe_calls_sdk(self):
        """AssemblyAIProvider.transcribe calls AssemblyAI SDK with audio bytes."""
        mock_aai_module = MagicMock()

        mock_transcript = MagicMock()
        mock_transcript.text = "assemblyai transcript"
        mock_transcript.confidence = 0.96
        mock_transcript.language_code = "en"
        mock_transcript.words = [
            MagicMock(start=0, end=1000, text="assemblyai"),
            MagicMock(start=1000, end=2000, text="transcript"),
        ]
        mock_transcript.utterances = None

        mock_transcriber = MagicMock()
        mock_transcriber.transcribe.return_value = mock_transcript
        mock_aai_module.Transcriber.return_value = mock_transcriber
        mock_aai_module.TranscriptionConfig = MagicMock

        with patch.dict("sys.modules", {"assemblyai": mock_aai_module}):
            provider = AssemblyAIProvider(api_key="test-key")
            result = await provider.transcribe(b"audio bytes", "wav")

        assert isinstance(result, TranscriptionResult)
        assert result.text == "assemblyai transcript"

    def test_supports_diarization_true(self):
        """AssemblyAIProvider.supports_diarization returns True."""
        provider = AssemblyAIProvider(api_key="test-key")
        assert provider.supports_diarization is True


# ---------------------------------------------------------------------------
# Tests 11-14: ASRService
# ---------------------------------------------------------------------------

class TestASRService:
    def test_resolves_provider_from_default_config(self):
        """ASRService resolves provider from platform default (whisper)."""
        with patch("app.services.asr.asr_service.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                asr_default_provider="whisper",
                whisper_endpoint="http://localhost:8790",
            )
            service = ASRService()
            assert service.provider_name == "whisper"
            assert isinstance(service._provider, WhisperProvider)

    @pytest.mark.asyncio
    async def test_transcribe_delegates_to_provider(self):
        """ASRService.transcribe delegates to provider.transcribe."""
        with patch("app.services.asr.asr_service.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                asr_default_provider="whisper",
                whisper_endpoint="http://localhost:8790",
            )
            service = ASRService()

            mock_result = TranscriptionResult(text="delegated", segments=[])
            service._provider = AsyncMock()
            service._provider.transcribe = AsyncMock(return_value=mock_result)

            result = await service.transcribe(b"audio", "wav")
            assert result.text == "delegated"
            service._provider.transcribe.assert_awaited_once()

    def test_provider_map_has_correct_keys(self):
        """_ASR_PROVIDER_MAP contains whisper, deepgram, assemblyai keys."""
        assert "whisper" in _ASR_PROVIDER_MAP
        assert "deepgram" in _ASR_PROVIDER_MAP
        assert "assemblyai" in _ASR_PROVIDER_MAP

    def test_raises_for_unknown_provider(self):
        """ASRService raises ValueError for unknown provider name."""
        with patch("app.services.asr.asr_service.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                asr_default_provider="nonexistent_provider",
                whisper_endpoint="http://localhost:8790",
            )
            with pytest.raises(ValueError, match="Unknown ASR provider"):
                ASRService()


# ---------------------------------------------------------------------------
# Test 15: Audio format conversion
# ---------------------------------------------------------------------------

class TestAudioFormatConversion:
    @pytest.mark.asyncio
    async def test_convert_webm_to_wav(self):
        """convert_audio_format(webm_bytes, 'webm', 'wav') produces WAV output."""
        # Mock pydub since it may not be installed
        mock_segment = MagicMock()
        mock_segment.set_channels.return_value = mock_segment
        mock_segment.set_frame_rate.return_value = mock_segment

        # Mock export to write WAV header
        def mock_export(buf, format, **kwargs):
            buf.write(b"RIFF" + b"\x00" * 100)  # Minimal WAV-like output

        mock_segment.export = mock_export

        with patch("app.services.asr.asr_service.AudioSegment") as mock_audio_seg:
            mock_audio_seg.from_file.return_value = mock_segment
            result = await convert_audio_format(b"fake webm data", "webm", "wav")

        assert isinstance(result, bytes)
        assert len(result) > 0
