"""ASR (Automatic Speech Recognition) service package.

Re-exports ASRService and TranscriptionResult for convenient importing.
"""

from app.services.asr.asr_service import ASRService
from app.services.asr.providers.base import TranscriptionResult

__all__ = ["ASRService", "TranscriptionResult"]
