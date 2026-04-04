---
phase: 03-input-narrative-capture
plan: 02
subsystem: asr, api
tags: [asr, whisper, deepgram, assemblyai, websocket, voice, transcription, httpx, pydub]

# Dependency graph
requires:
  - phase: 03-01
    provides: "Intake models (AudioRecording, Transcript), WebSocket router, IntakeSessionService, message pipeline"
  - phase: 01-05
    provides: "LLMService pattern (_PROVIDER_MODEL_MAP) replicated for ASR providers"
provides:
  - "ASRService with pluggable provider architecture (Whisper, Deepgram, AssemblyAI)"
  - "TranscriptionResult dataclass for ASR output"
  - "Audio format conversion (WebM/Opus -> WAV via pydub)"
  - "voice_upload WebSocket handler: base64 audio -> ASR -> transcript_ready for review"
  - "transcript_approve and transcript_edit WebSocket handlers"
  - "normalize_voice_transcript in message pipeline"
affects: [03-03, 04-exploration, 05-research, 09-output]

# Tech tracking
tech-stack:
  added: [httpx (already present), pydub (optional, for audio conversion)]
  patterns: ["ASR provider plugin pattern via _ASR_PROVIDER_MAP", "Voice WebSocket flow: upload -> review -> approve/edit -> pipeline"]

key-files:
  created:
    - backend/app/services/asr/providers/base.py
    - backend/app/services/asr/providers/whisper_provider.py
    - backend/app/services/asr/providers/deepgram_provider.py
    - backend/app/services/asr/providers/assemblyai_provider.py
    - backend/app/services/asr/asr_service.py
    - backend/app/services/asr/__init__.py
    - backend/app/services/asr/providers/__init__.py
    - backend/tests/test_asr_service.py
    - backend/tests/test_voice_intake.py
  modified:
    - backend/app/routers/intake.py
    - backend/app/services/intake/message_pipeline.py
    - backend/tests/test_message_pipeline.py

key-decisions:
  - "ASR provider pattern mirrors LLMService _PROVIDER_MODEL_MAP for consistency"
  - "WhisperProvider uses httpx.AsyncClient with 120s timeout for sidecar HTTP calls"
  - "Cloud providers (Deepgram, AssemblyAI) import SDKs lazily to avoid hard dependencies"
  - "Audio conversion via pydub is optional -- graceful fallback if not installed"
  - "Voice normalization uses source_type 'voice_transcript' in message pipeline"

patterns-established:
  - "_ASR_PROVIDER_MAP: provider name -> class lookup for ASR (mirrors LLM pattern)"
  - "Voice WebSocket flow: voice_upload -> transcript_ready -> transcript_approve/edit -> normalize -> LLM follow-up"
  - "Lazy SDK imports for optional cloud providers (deepgram, assemblyai)"

requirements-completed: [INGEST-02]

# Metrics
duration: 10min
completed: 2026-04-04
---

# Phase 3 Plan 02: ASR Service & Voice Intake Summary

**Pluggable ASR service with Whisper/Deepgram/AssemblyAI providers and WebSocket voice upload flow with transcript review before pipeline entry**

## Performance

- **Duration:** 10 min
- **Started:** 2026-04-04T01:55:55Z
- **Completed:** 2026-04-04T02:06:14Z
- **Tasks:** 2
- **Files modified:** 12

## Accomplishments
- Pluggable ASR service with 3 provider implementations: WhisperProvider (local sidecar HTTP), DeepgramProvider (cloud SDK with streaming + diarization), AssemblyAIProvider (cloud SDK with diarization)
- Voice upload WebSocket flow: consumer sends base64 audio, server stores AudioRecording, transcribes via ASRService, sends transcript_ready for review, consumer approves or edits, transcript enters normalization pipeline, LLM generates follow-up
- Audio format conversion handles browser-native WebM/Opus by converting to WAV (mono 16kHz) for ASR compatibility
- Voice modality wired into message normalization pipeline as "voice_transcript" source type

## Task Commits

Each task was committed atomically:

1. **Task 1: Pluggable ASR service with provider architecture**
   - `1acda39` (test: add failing tests for ASR provider architecture)
   - `86b08c3` (feat: implement pluggable ASR service with Whisper, Deepgram, AssemblyAI providers)
2. **Task 2: Wire voice_upload handling into intake WebSocket router**
   - `d478124` (test: add failing tests for voice_upload WebSocket flow)
   - `07cc23f` (feat: wire voice_upload, transcript_approve, transcript_edit into WebSocket router)

_Note: TDD tasks each have 2 commits (RED test -> GREEN implementation)_

## Files Created/Modified
- `backend/app/services/asr/providers/base.py` - ASRProviderBase ABC and TranscriptionResult dataclass
- `backend/app/services/asr/providers/whisper_provider.py` - Local Whisper sidecar HTTP provider
- `backend/app/services/asr/providers/deepgram_provider.py` - Cloud Deepgram SDK provider with streaming + diarization
- `backend/app/services/asr/providers/assemblyai_provider.py` - Cloud AssemblyAI SDK provider with diarization
- `backend/app/services/asr/asr_service.py` - ASRService with _ASR_PROVIDER_MAP, per-org config resolution, audio conversion
- `backend/app/services/asr/__init__.py` - Package re-exports ASRService, TranscriptionResult
- `backend/app/services/asr/providers/__init__.py` - Package re-exports all providers
- `backend/app/routers/intake.py` - Extended WebSocket handler with voice_upload, transcript_approve, transcript_edit
- `backend/app/services/intake/message_pipeline.py` - Added normalize_voice_transcript, wired voice modality
- `backend/tests/test_asr_service.py` - 17 tests for ASR provider architecture
- `backend/tests/test_voice_intake.py` - 3 tests for voice WebSocket integration flow
- `backend/tests/test_message_pipeline.py` - Updated voice normalization test (was NotImplementedError, now passing)

## Decisions Made
- **ASR provider pattern mirrors LLMService:** Used _ASR_PROVIDER_MAP dict mapping provider names to classes, matching the existing _PROVIDER_MODEL_MAP pattern for consistency
- **Lazy SDK imports:** Deepgram and AssemblyAI providers import their SDKs inside the transcribe method to avoid hard dependencies -- ImportError raised at call time if SDK not installed
- **Optional pydub:** Audio conversion gracefully falls back to sending raw format if pydub is not installed, allowing providers that accept WebM natively to work without ffmpeg
- **Voice transcript normalization:** Added normalize_voice_transcript with source_type="voice_transcript" to distinguish voice-origin content in downstream processing

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated existing voice normalization test**
- **Found during:** Task 2 (full test suite regression check)
- **Issue:** test_message_pipeline.py had `test_process_voice_raises_not_implemented` which expected NotImplementedError for voice modality, but we just wired voice normalization
- **Fix:** Updated test to assert voice normalization returns NormalizedContent with source_type="voice_transcript"
- **Files modified:** backend/tests/test_message_pipeline.py
- **Verification:** All 246 tests pass
- **Committed in:** 07cc23f (part of Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug fix)
**Impact on plan:** Necessary update to reflect new voice normalization capability. No scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required. ASR providers use mocked SDKs in tests. Production deployment requires:
- Whisper sidecar service at ALEA_WHISPER_ENDPOINT (default http://localhost:8790)
- Deepgram API key in org settings for cloud ASR
- AssemblyAI API key in org settings for cloud ASR

## Known Stubs
None - all voice flow paths are fully wired with real handler logic. Cloud SDK calls are lazy-imported but functional when SDKs are installed.

## Next Phase Readiness
- ASR service ready for document upload flow (Plan 03) to complete all input modalities
- Voice transcript normalization produces NormalizedContent compatible with downstream fact extraction (Phase 4)
- ASRService provider architecture extensible for future providers

## Self-Check: PASSED

All 12 files verified present. All 4 commit hashes verified in git log.

---
*Phase: 03-input-narrative-capture*
*Completed: 2026-04-04*
