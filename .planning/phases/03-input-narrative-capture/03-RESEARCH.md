# Phase 3: Input & Narrative Capture - Research

**Researched:** 2026-03-24
**Domain:** Multi-modal intake (chat, voice/ASR, document processing, fact extraction), real-time messaging, pluggable provider architecture
**Confidence:** HIGH

## Summary

Phase 3 builds the intake layer that transforms consumer narratives into structured data. It spans five technical domains: (1) a conversational chat system with LLM-guided question generation, (2) a pluggable ASR provider architecture for voice transcription, (3) document processing for PDF/DOCX/image extraction, (4) a professional intake interface, and (5) an LLM-driven fact extraction pipeline that produces atomic assertions with source provenance. All modalities normalize into a common text representation that feeds Phase 2's ConceptResolver in real-time.

The existing codebase provides strong foundations: LLMService with per-org provider config (the pattern ASRService replicates), Organization.settings JSON field (for intake config), ConceptResolver (downstream consumer called per-message), TenantBase models (for all new intake tables), and field-level PII encryption (for narrative text, transcripts, document contents). The sibling project folio-enrich provides battle-tested document ingestion code (PDFIngestor, WordIngestor) using PyMuPDF and python-docx that can be adapted rather than rebuilt.

**Primary recommendation:** Build the intake layer as a set of loosely-coupled services (IntakeSessionService, ASRService, DocumentService, FactExtractionService) following the existing LLMService per-org config pattern, with WebSocket-based real-time chat and a normalized message pipeline that all modalities feed into.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions

**Chat Interaction Model:**
- Default to conversational turns with LLM-generated guiding questions, but allow consumer to provide free-form narrative submission if they prefer
- LLM-driven question generation by default; orgs can define predefined intake question templates that the LLM pulls from when relevant (LLM acts as orchestrator, deciding which predefined questions are appropriate for the consumer's situation)
- Seamless multi-modal mixing within a session: any message can be text, voice recording, or document upload -- all normalized into the same stream
- Session model is org-configurable: single-session (legal aid kiosk) or multi-session with pause/resume (law firm ongoing clients)
- Store both raw message history (full chat transcript) AND normalized output -- legal context demands full traceability
- Append-only correction model: new messages override old facts, system tracks both original and corrected assertions with timestamps, audit trail preserved
- Multi-party intakes supported: an intake can have multiple contributing consumers
- Conflicting facts between parties: track per-party assertions with source attribution, both preserved, analysis sees all versions, professionals resolve conflicts
- Professional mode: professionals can choose conversational interface (for complex narratives) or structured form (for straightforward intakes), per-case decision

**Voice/ASR Integration:**
- Pluggable ASR provider interface mirroring LLMService pattern: per-org provider config in Organization.settings with provider class map, API key management, training opt-out enforcement
- Both streaming and record-then-transcribe modes, org-configurable: streaming for cloud ASR providers that support it (Deepgram, AssemblyAI); record-then-transcribe as fallback for local Whisper or providers without streaming
- Default to storing both encrypted original audio AND transcript; org-configurable (store both, transcript-only, or ephemeral with auto-delete)
- Consumer reviews and edits transcript before it enters the analysis pipeline -- critical for legal accuracy (misheard names/dates)
- Broad audio format support: browser-native recording (WebM/Opus, MP4/AAC) plus uploaded files (MP3, WAV, M4A, OGG, WebM). Server-side conversion for ASR providers that need specific formats
- Speaker diarization when ASR provider supports it -- maps to per-party assertion tracking for multi-party intakes
- Org-configurable maximum recording duration (sensible default, e.g., 10-15 min per recording). Long narratives split across multiple recordings

**Document Processing:**
- Structured text extraction preserving document structure: headings, paragraphs, tables, lists, numbered sections. Legal documents have meaningful structure (exhibits, signatures, numbered paragraphs)
- Store both encrypted original files AND structured extracted text -- matches voice/audio storage pattern. Org-configurable retention
- Org-configurable file size and page limits with sensible defaults (e.g., 50MB per file, 200 pages per doc)
- Supported formats: PDF, DOCX, images (with OCR)

**Fact Extraction:**
- Per-message incremental extraction: facts extracted after each message/upload in conversation. LLM guiding the conversation uses already-extracted facts to ask better follow-up questions
- Legal-domain entity types: standard NER (people, dates, locations, amounts, organizations) PLUS legal-specific entities: party relationships (employer/employee, landlord/tenant), legal events (filing, service, injury), document references (contracts, leases), time periods (statute of limitations), claimed damages
- Leverage folio-enrich pipeline where useful for entity extraction and concept tagging
- Atomic decomposition: break narrative into smallest meaningful units (party relationship, event, amount, date, sequence, conditions) -- each fact independently trackable for element mapping
- Source span tracking: every extracted fact links to its source with precise location -- message ID + character offsets for chat, timestamp range for voice transcripts, page/paragraph for documents. Essential for Phase 9's narrative-anchored view
- Immediate concept resolution: as facts are extracted, they're passed to Phase 2's ConceptResolver for FOLIO IRI matching in real-time. Conversation LLM sees both raw facts AND matched FOLIO concepts for smarter follow-ups
- Dedicated LLM call for extraction: separate from conversation generation, specialized extraction prompt, can use cheaper/faster model, tunable independently
- Confidence scores on extracted facts with downstream impact: low-confidence facts enter pipeline but weighted lower in claim mapping, flagged for follow-up. Phase 4's gap analysis uses confidence
- Fact visibility: default to internal (professional review only), org-configurable for consumer-facing transparency
- Same-party conflict handling: latest version becomes active fact (append-only model), both preserved with timestamps. LLM can optionally ask for clarification on high-impact contradictions (dates, amounts) when the discrepancy matters for analysis

### Claude's Discretion

**Voice/ASR:**
- Local Whisper deployment model (sidecar service vs in-process)

**Document Processing:**
- Text extraction approach: library-based (PyMuPDF, python-docx, Tesseract), service-based (folio-enrich pipeline), or hybrid -- determined during research
- OCR engine choice and configuration
- Document chunking strategy for multi-page documents

### Deferred Ideas (OUT OF SCOPE)

None -- discussion stayed within phase scope

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INGEST-01 | Consumer can submit narrative text via conversational chat interface | WebSocket chat architecture, LLM conversation service, IntakeSession/Message models, real-time message pipeline |
| INGEST-02 | Consumer can record voice input that is transcribed via pluggable ASR (local Whisper or cloud providers) | ASRService with provider class map (faster-whisper, Deepgram SDK, AssemblyAI SDK), audio format conversion via pydub/ffmpeg, transcript review flow |
| INGEST-03 | Consumer can upload documents (PDF, DOCX, images) for text extraction and analysis | DocumentService using PyMuPDF for PDF, python-docx for DOCX, pytesseract+Pillow for image OCR, structured element extraction |
| INGEST-04 | Professional can enter notes on behalf of a consumer | Professional intake router with on_behalf_of attribution, same message pipeline as consumer input |
| INGEST-05 | System normalizes all input modalities into a common text representation for analysis | NormalizedContent model with text + structural elements + source spans, unified message processing pipeline |
| INGEST-06 | System extracts atomic factual assertions from narrative (parties, dates, locations, amounts, events) | FactExtractionService with dedicated LLM call, Pydantic-schema structured output, per-message incremental extraction, ConceptResolver integration |

</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI (WebSocket) | >=0.135.0 (already installed) | Real-time chat via native ASGI WebSocket support | Built-in, no additional dependency needed; natively async |
| PyMuPDF (pymupdf) | 1.27.2 | PDF text extraction with structure preservation | Already used in folio-enrich; best extraction quality; faster than pypdf; supports OCR fallback |
| python-docx | 1.2.0 | DOCX text extraction with paragraph/table/heading structure | Already used in folio-enrich; de facto standard for Word documents |
| pytesseract | 0.3.13 | OCR for image-based documents | Standard Tesseract wrapper; simple, reliable; system-level Tesseract required |
| Pillow | 12.1.1 | Image preprocessing for OCR pipeline | Required by pytesseract; standard imaging library |
| faster-whisper | 1.2.1 | Local ASR transcription (CTranslate2-based) | 4x faster than openai-whisper, same accuracy, less memory; bundles FFmpeg via PyAV |
| pydub | 0.25.1 | Audio format conversion (WebM/Opus -> WAV for ASR providers) | Simple API for format conversion; requires ffmpeg system binary |
| alea-llm-client | >=0.3.0 (already installed) | LLM calls for conversation generation and fact extraction | Already in the project; multi-provider abstraction |
| Pydantic | >=2.12.0 (already installed) | Structured output schemas for fact extraction | Already in the project; LLM structured output validation |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| deepgram-sdk | 6.0.1 | Cloud ASR provider (Deepgram) | When org configures Deepgram as ASR provider; supports streaming + diarization |
| assemblyai | 0.58.0 | Cloud ASR provider (AssemblyAI) | When org configures AssemblyAI as ASR provider; supports streaming + diarization |
| pymupdf4llm | 1.27.2 | Enhanced PDF-to-Markdown extraction preserving structure | For legal documents needing chapter/heading/table structure in Markdown format |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| faster-whisper (local ASR) | openai-whisper | openai-whisper is 4x slower, uses more memory; same accuracy |
| pytesseract (OCR) | EasyOCR | EasyOCR is better for unstructured image text but heavier (PyTorch); pytesseract sufficient for document OCR |
| pydub (audio conversion) | ffmpeg-python | ffmpeg-python (0.2.0) is unmaintained; pydub is simpler and actively maintained |
| WebSocket (chat) | SSE (Server-Sent Events) | SSE is unidirectional (server->client only); chat requires bidirectional messaging |

**Installation (new dependencies):**
```bash
# Document processing
pip install "pymupdf>=1.27.0" "python-docx>=1.2.0" "pytesseract>=0.3.13" "Pillow>=12.0.0"

# ASR - local
pip install "faster-whisper>=1.2.0"

# ASR - cloud (optional, per-org)
pip install "deepgram-sdk>=6.0.0" "assemblyai>=0.58.0"

# Audio processing
pip install "pydub>=0.25.1"

# System dependency: ffmpeg (for pydub), tesseract-ocr (for pytesseract)
# apt install ffmpeg tesseract-ocr
```

**Version verification:** All versions confirmed against PyPI registry on 2026-03-24.

## Architecture Patterns

### Recommended Project Structure
```
backend/app/
  models/
    intake.py              # Intake, IntakeSession, Message, NormalizedContent
    audio.py               # AudioRecording, Transcript
    document.py            # UploadedDocument, ExtractedContent
    fact.py                # ExtractedFact, FactSourceSpan, FactAssertion
  services/
    intake/
      __init__.py
      session_service.py   # IntakeSessionService - session lifecycle, message routing
      conversation.py      # ConversationService - LLM question generation
      message_pipeline.py  # Unified message normalization pipeline
    asr/
      __init__.py
      asr_service.py       # ASRService - pluggable provider interface
      providers/
        __init__.py
        base.py            # ASRProviderBase ABC
        whisper_provider.py    # faster-whisper local provider
        deepgram_provider.py   # Deepgram cloud provider
        assemblyai_provider.py # AssemblyAI cloud provider
    document/
      __init__.py
      document_service.py  # DocumentService - upload, extraction, storage
      extractors/
        __init__.py
        pdf_extractor.py   # PyMuPDF-based PDF extraction
        docx_extractor.py  # python-docx-based DOCX extraction
        ocr_extractor.py   # pytesseract+Pillow image OCR
    extraction/
      __init__.py
      fact_extraction.py   # FactExtractionService - LLM-driven fact extraction
      schemas.py           # Pydantic models for extraction output
  routers/
    intake.py              # Consumer intake WebSocket + REST endpoints
    intake_professional.py # Professional mode endpoints
```

### Pattern 1: Pluggable ASR Provider (mirrors LLMService)

**What:** Provider class map with per-org config, matching the established LLMService pattern.
**When to use:** For all ASR operations -- provider selection is org-configurable.

```python
# Mirrors LLMService._PROVIDER_MODEL_MAP pattern
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator

@dataclass
class TranscriptionResult:
    text: str
    segments: list[dict]  # [{start, end, text, speaker?}]
    language: str | None = None
    confidence: float | None = None

class ASRProviderBase(ABC):
    """Abstract base for ASR providers."""

    @abstractmethod
    async def transcribe(self, audio_bytes: bytes, format: str, **kwargs) -> TranscriptionResult:
        """Transcribe audio bytes to text."""

    async def transcribe_streaming(self, audio_stream: AsyncIterator[bytes], **kwargs) -> AsyncIterator[str]:
        """Stream transcription (override for providers that support it)."""
        raise NotImplementedError("Streaming not supported by this provider")

    @property
    def supports_streaming(self) -> bool:
        return False

    @property
    def supports_diarization(self) -> bool:
        return False

# Provider class map -- same pattern as LLMService._PROVIDER_MODEL_MAP
_ASR_PROVIDER_MAP: dict[str, type[ASRProviderBase]] = {
    "whisper": WhisperProvider,
    "deepgram": DeepgramProvider,
    "assemblyai": AssemblyAIProvider,
}

class ASRService:
    """ASR service with per-org provider config."""

    def __init__(self, org_config: OrganizationConfig | None = None):
        provider_name = "whisper"  # default
        if org_config and org_config.settings:
            provider_name = org_config.settings.get("asr_provider", "whisper")
        provider_cls = _ASR_PROVIDER_MAP.get(provider_name)
        if not provider_cls:
            raise ValueError(f"Unknown ASR provider: {provider_name}")
        self.provider = provider_cls(org_config=org_config)
```

### Pattern 2: Unified Message Pipeline

**What:** All input modalities (text, voice transcript, document text) flow through the same normalization pipeline, producing NormalizedContent with source spans.
**When to use:** Every time a message is received, regardless of modality.

```python
@dataclass
class NormalizedContent:
    """Common representation for all input modalities."""
    text: str                          # Normalized plain text
    elements: list[TextElement]        # Structural elements (paragraphs, headings, tables)
    source_type: str                   # "chat", "voice", "document", "professional_note"
    source_id: str                     # Message ID, recording ID, or document ID
    source_spans: list[SourceSpan]     # Precise location data for traceability
    party_id: int | None               # Which party contributed this content

@dataclass
class SourceSpan:
    """Links extracted content to its precise source location."""
    start_char: int                    # Character offset in normalized text
    end_char: int
    source_message_id: int | None      # For chat messages
    source_timestamp_start: float | None  # For voice transcripts (seconds)
    source_timestamp_end: float | None
    source_page: int | None            # For documents
    source_paragraph: int | None       # For documents

async def process_message(message: Message) -> NormalizedContent:
    """Route message through appropriate normalizer based on modality."""
    if message.modality == "text":
        return normalize_text(message)
    elif message.modality == "voice":
        return await normalize_voice(message)  # transcribe + normalize
    elif message.modality == "document":
        return await normalize_document(message)  # extract + normalize
    elif message.modality == "professional_note":
        return normalize_professional_note(message)
```

### Pattern 3: Per-Message Incremental Fact Extraction

**What:** After each message is normalized, a dedicated LLM call extracts atomic facts using structured output (Pydantic schema). Extracted facts are immediately passed to ConceptResolver for FOLIO IRI matching.
**When to use:** After every message normalization, before generating the next conversation response.

```python
from pydantic import BaseModel, Field

class ExtractedEntity(BaseModel):
    """A single extracted entity from narrative text."""
    entity_type: str  # "person", "date", "location", "amount", "organization",
                      # "party_relationship", "legal_event", "document_reference",
                      # "time_period", "claimed_damages"
    value: str
    confidence: float = Field(ge=0.0, le=1.0)
    source_start: int   # char offset in normalized text
    source_end: int

class ExtractedFact(BaseModel):
    """An atomic factual assertion decomposed from narrative."""
    assertion: str              # Natural language statement of the fact
    fact_type: str              # "event", "relationship", "amount", "date", "condition"
    entities: list[ExtractedEntity]
    confidence: float = Field(ge=0.0, le=1.0)
    source_start: int
    source_end: int

class ExtractionResult(BaseModel):
    """Complete extraction from a single message."""
    facts: list[ExtractedFact]
    entities: list[ExtractedEntity]

# In the extraction pipeline:
async def extract_and_resolve(
    normalized: NormalizedContent,
    session_facts: list[ExtractedFact],  # accumulated facts for context
    llm_service: LLMService,
    concept_resolver: ConceptResolver,
    folio: FOLIO,
    embedding_service: EmbeddingService,
) -> ExtractionResult:
    # 1. LLM extraction with Pydantic structured output
    result = await extract_facts_via_llm(normalized.text, session_facts, llm_service)

    # 2. Immediate concept resolution for each fact
    for fact in result.facts:
        concepts = await resolve_concepts(
            fact.assertion, folio, embedding_service
        )
        # Store fact-to-concept mappings

    return result
```

### Pattern 4: WebSocket Chat with Connection Manager

**What:** WebSocket-based real-time chat with per-session connection tracking, JWT auth on connect, and message routing.
**When to use:** All consumer chat interactions.

```python
from fastapi import WebSocket, WebSocketDisconnect
from collections import defaultdict

class IntakeConnectionManager:
    """Manages active WebSocket connections per intake session."""

    def __init__(self):
        self.active: dict[int, list[WebSocket]] = defaultdict(list)  # session_id -> connections

    async def connect(self, websocket: WebSocket, session_id: int):
        await websocket.accept()
        self.active[session_id].append(websocket)

    def disconnect(self, websocket: WebSocket, session_id: int):
        self.active[session_id].remove(websocket)

    async def send_to_session(self, session_id: int, message: dict):
        for ws in self.active[session_id]:
            await ws.send_json(message)

# Router
@router.websocket("/ws/intake/{session_id}")
async def intake_websocket(websocket: WebSocket, session_id: int):
    # Authenticate via JWT token in query params or first message
    user = await authenticate_websocket(websocket)
    await manager.connect(websocket, session_id)
    try:
        while True:
            data = await websocket.receive_json()
            # Route through message pipeline
            # Send LLM response back
    except WebSocketDisconnect:
        manager.disconnect(websocket, session_id)
```

### Pattern 5: Whisper as Sidecar Service (Recommended)

**What:** Run faster-whisper as a separate FastAPI microservice, called via HTTP from the main backend. Avoids loading large ML models into the main process.
**When to use:** For local Whisper deployments (org data_policy = "local_only" or default).

**Recommendation (Claude's Discretion):** Sidecar service is preferred over in-process for three reasons:
1. **Memory isolation:** Whisper large-v3 requires ~3GB VRAM/RAM; loading into the main FastAPI process risks OOM under concurrent intake load
2. **Independent scaling:** ASR workload is bursty and CPU/GPU-intensive; separate process/container can scale independently
3. **Startup time:** Loading Whisper models takes 5-15 seconds; sidecar avoids delaying main app startup

```python
class WhisperProvider(ASRProviderBase):
    """Local Whisper ASR via sidecar HTTP service."""

    def __init__(self, endpoint: str = "http://localhost:8790"):
        self.endpoint = endpoint

    async def transcribe(self, audio_bytes: bytes, format: str, **kwargs) -> TranscriptionResult:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.endpoint}/transcribe",
                files={"audio": ("audio." + format, audio_bytes)},
                data={"language": kwargs.get("language", "en")},
                timeout=120.0,  # Transcription can take time
            )
            response.raise_for_status()
            data = response.json()
            return TranscriptionResult(
                text=data["text"],
                segments=data.get("segments", []),
                language=data.get("language"),
            )
```

### Anti-Patterns to Avoid

- **Monolithic message handler:** Do NOT process all modalities in a single function. Use the message pipeline pattern with separate normalizers per modality.
- **Synchronous ASR in request handler:** Whisper transcription can take 30+ seconds for long recordings. Always run in background task or sidecar service, never blocking the WebSocket loop.
- **Storing extracted facts without source spans:** Every fact MUST link back to its source. Omitting source spans breaks Phase 9's narrative-anchored view and makes the audit trail incomplete.
- **Single LLM call for both conversation and extraction:** These serve different purposes and should use separate prompts and potentially different models (extraction can use a cheaper model).
- **Blocking WebSocket on LLM response:** Stream LLM responses token-by-token back through WebSocket to avoid perceived latency.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| PDF text extraction | Custom PDF parser | PyMuPDF (pymupdf) | PDF spec is 800+ pages; layout analysis, encoding detection, font handling are deceptively complex |
| DOCX text extraction | Custom XML parser | python-docx | OOXML has 7000+ page spec; table merging, style inheritance, embedded objects |
| Image OCR | Custom neural OCR | pytesseract + Pillow | OCR accuracy requires trained models; Tesseract has decades of training data |
| Audio format conversion | Custom codec handling | pydub + ffmpeg | Codec negotiation, sample rate conversion, channel mixing are complex signal processing |
| ASR transcription | Custom speech model | faster-whisper / cloud providers | Speech recognition requires billions of training samples; use proven models |
| WebSocket connection management | Raw socket handling | FastAPI WebSocket + connection manager pattern | Heartbeat, reconnection, auth, message framing need careful handling |
| Structured LLM output parsing | Regex-based JSON extraction | Pydantic + LLM structured output | LLM output is unpredictable; Pydantic validation catches schema violations |
| PDF structure (headings/tables) | Heuristic-based detection | pymupdf4llm for Markdown conversion | Heading detection from font metrics alone is error-prone; pymupdf4llm uses proven heuristics |

**Key insight:** Each modality (voice, documents, chat) has deep domain complexity. The libraries above encode years of edge-case handling. Rolling custom solutions leads to brittleness on real-world inputs (scanned legal documents, accented speech, browser-specific audio codecs).

## Common Pitfalls

### Pitfall 1: WebSocket Auth Race Condition
**What goes wrong:** WebSocket connections bypass standard HTTP middleware. JWT validation that works for REST endpoints silently fails for WebSocket, allowing unauthenticated connections.
**Why it happens:** FastAPI middleware runs on HTTP, not WebSocket. WebSocket endpoints need explicit auth.
**How to avoid:** Validate JWT in the WebSocket handshake (query param or first message). Reject before accepting the connection.
**Warning signs:** WebSocket tests passing without auth tokens.

### Pitfall 2: Audio Format Mismatch
**What goes wrong:** Browser records in WebM/Opus, but ASR provider expects WAV/PCM. Transcription returns empty or garbage.
**Why it happens:** Browsers use WebM container with Opus codec by default (MediaRecorder API). Not all ASR providers accept this format.
**How to avoid:** Always convert to WAV (PCM 16-bit, 16kHz mono) before sending to ASR. Use pydub for conversion. Detect format from content-type header.
**Warning signs:** Empty transcripts, "unsupported format" errors from ASR provider.

### Pitfall 3: Blocking Event Loop with Sync Operations
**What goes wrong:** PyMuPDF, python-docx, and faster-whisper are synchronous libraries. Calling them directly in async handlers blocks the event loop, causing WebSocket timeouts for other clients.
**Why it happens:** Python's GIL + sync I/O in async context.
**How to avoid:** Use `asyncio.get_event_loop().run_in_executor(None, sync_function)` for all CPU-bound document processing and transcription. Or offload to background tasks.
**Warning signs:** WebSocket connections dropping during document upload or voice transcription.

### Pitfall 4: LLM Extraction Hallucination
**What goes wrong:** LLM invents facts not present in the narrative (e.g., adding specific dollar amounts when consumer only said "a lot of money").
**Why it happens:** LLMs are completion engines; structured output prompts can cause them to fill in missing fields.
**How to avoid:** (1) Require source span evidence for every extracted fact. (2) Validate that extracted text actually appears in the source at the specified offsets. (3) Allow null/empty fields rather than forcing extraction. (4) Low confidence threshold for facts without clear textual evidence.
**Warning signs:** Extracted facts with no corresponding text at the claimed source spans.

### Pitfall 5: SQLite Large Binary Storage
**What goes wrong:** Storing audio files (potentially 10+ MB) and document files (up to 50MB) as BLOBs in SQLite causes severe performance degradation and memory issues.
**Why it happens:** SQLite loads entire BLOBs into memory; no streaming reads.
**How to avoid:** Use filesystem storage with database metadata. Store files in a configurable directory (default `./data/uploads/{org_slug}/`), store only the file path in the database. PostgreSQL can use `LargeBinary` for smaller files but filesystem is still preferred for large media.
**Warning signs:** Memory spikes during document/audio operations, SQLite "database or disk is full" errors.

### Pitfall 6: Transcript Review Before Pipeline
**What goes wrong:** Voice transcripts enter the fact extraction pipeline before the consumer has reviewed them, propagating ASR errors (misheard names, dates, amounts) into legal analysis.
**Why it happens:** Developer treats transcription as instant and auto-submits.
**How to avoid:** Transcription produces a draft transcript in "pending_review" status. Only after consumer confirms (or edits) does it enter the normalization pipeline. The UI must show the transcript for review.
**Warning signs:** Extracted facts from voice input contain obvious ASR errors (e.g., "John" transcribed as "Jon", "$5,000" as "five thousand").

### Pitfall 7: Concurrent Multi-Party Fact Conflicts
**What goes wrong:** Two parties in a multi-party intake provide contradictory facts (different dates, amounts), and the system silently overwrites one with the other.
**Why it happens:** Single-party assumption in the data model; no party attribution.
**How to avoid:** Every fact assertion carries a `party_id` and `contributed_by_user_id`. Conflicting facts from different parties both persist with their party attribution. Same-party conflicts follow the append-only model (latest wins, both preserved). Cross-party conflicts are never auto-resolved.
**Warning signs:** Facts changing unexpectedly, missing party attribution in fact queries.

## Code Examples

### Database Models (Tenant Schema)

```python
# backend/app/models/intake.py
"""Intake session and message models -- per-tenant schema."""
from datetime import datetime
from sqlalchemy import Boolean, Enum, Float, ForeignKey, Integer, JSON, LargeBinary, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import TenantBase

class Intake(TenantBase):
    """Top-level intake record. One per consumer matter."""
    __tablename__ = "intakes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active, paused, completed, archived
    created_by_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # null for kiosk
    session_mode: Mapped[str] = mapped_column(String(20), default="multi_session")  # single_session, multi_session
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

class IntakeParty(TenantBase):
    """A party (contributor) in an intake. Supports multi-party intakes."""
    __tablename__ = "intake_parties"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    intake_id: Mapped[int] = mapped_column(Integer, ForeignKey("intakes.id"), nullable=False)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # null for anonymous kiosk
    role_in_intake: Mapped[str] = mapped_column(String(50), default="primary")  # primary, additional_party
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)  # "Tenant", "Landlord", etc.
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

class IntakeSession(TenantBase):
    """A conversation session within an intake. Multi-session intakes have multiple."""
    __tablename__ = "intake_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    intake_id: Mapped[int] = mapped_column(Integer, ForeignKey("intakes.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active, paused, completed
    started_at: Mapped[datetime] = mapped_column(server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(nullable=True)

class Message(TenantBase):
    """A single message in a session -- any modality."""
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("intake_sessions.id"), nullable=False)
    party_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("intake_parties.id"), nullable=True)
    sender_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "consumer", "professional", "system"
    modality: Mapped[str] = mapped_column(String(20), nullable=False)  # "text", "voice", "document", "professional_note"
    content_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)  # PII: encrypted raw content
    normalized_text: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)  # PII: encrypted normalized text
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # modality-specific metadata
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
```

### Fact Model with Source Spans

```python
# backend/app/models/fact.py
"""Extracted fact models with source provenance tracking."""
from datetime import datetime
from sqlalchemy import Boolean, Float, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import TenantBase

class ExtractedFact(TenantBase):
    """An atomic factual assertion extracted from narrative."""
    __tablename__ = "extracted_facts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    intake_id: Mapped[int] = mapped_column(Integer, ForeignKey("intakes.id"), nullable=False)
    message_id: Mapped[int] = mapped_column(Integer, ForeignKey("messages.id"), nullable=False)
    party_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("intake_parties.id"), nullable=True)
    assertion_text: Mapped[str] = mapped_column(Text, nullable=False)
    fact_type: Mapped[str] = mapped_column(String(50), nullable=False)  # event, relationship, amount, date, condition
    entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # legal-domain entity type
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)  # False when superseded by correction
    superseded_by_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    visibility: Mapped[str] = mapped_column(String(20), default="internal")  # internal, consumer_visible
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # extracted entities, raw values
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

class FactSourceSpan(TenantBase):
    """Links an extracted fact to its precise source location."""
    __tablename__ = "fact_source_spans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fact_id: Mapped[int] = mapped_column(Integer, ForeignKey("extracted_facts.id"), nullable=False)
    message_id: Mapped[int] = mapped_column(Integer, ForeignKey("messages.id"), nullable=False)
    start_char: Mapped[int] = mapped_column(Integer, nullable=False)
    end_char: Mapped[int] = mapped_column(Integer, nullable=False)
    # Voice-specific spans
    timestamp_start_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    timestamp_end_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Document-specific spans
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    paragraph_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
```

### Audio Recording Model

```python
# backend/app/models/audio.py
"""Audio recording and transcript models."""
from datetime import datetime
from sqlalchemy import Float, ForeignKey, Integer, JSON, LargeBinary, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import TenantBase

class AudioRecording(TenantBase):
    """Encrypted audio recording associated with a message."""
    __tablename__ = "audio_recordings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(Integer, ForeignKey("messages.id"), nullable=False)
    intake_id: Mapped[int] = mapped_column(Integer, ForeignKey("intakes.id"), nullable=False)
    file_path_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)  # path to encrypted audio file
    original_format: Mapped[str] = mapped_column(String(20), nullable=False)  # webm, mp3, wav, etc.
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    storage_policy: Mapped[str] = mapped_column(String(20), default="store_both")  # store_both, transcript_only, ephemeral
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

class Transcript(TenantBase):
    """ASR transcript for an audio recording."""
    __tablename__ = "transcripts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recording_id: Mapped[int] = mapped_column(Integer, ForeignKey("audio_recordings.id"), nullable=False)
    text_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)  # PII: encrypted transcript
    status: Mapped[str] = mapped_column(String(20), default="pending_review")  # pending_review, approved, edited
    asr_provider: Mapped[str] = mapped_column(String(50), nullable=False)
    segments_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # [{start, end, text, speaker?}]
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(nullable=True)
```

### Document Upload Model

```python
# backend/app/models/document.py (alea-intake version, distinct from folio-enrich)
"""Uploaded document and extracted content models."""
from datetime import datetime
from sqlalchemy import ForeignKey, Integer, JSON, LargeBinary, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import TenantBase

class UploadedDocument(TenantBase):
    """An uploaded document associated with a message."""
    __tablename__ = "uploaded_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(Integer, ForeignKey("messages.id"), nullable=False)
    intake_id: Mapped[int] = mapped_column(Integer, ForeignKey("intakes.id"), nullable=False)
    file_path_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extraction_status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, completed, failed
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

class DocumentExtraction(TenantBase):
    """Extracted text and structure from an uploaded document."""
    __tablename__ = "document_extractions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(Integer, ForeignKey("uploaded_documents.id"), nullable=False)
    full_text_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)  # PII: encrypted extracted text
    elements_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # [{text, type, page, section_path}]
    extraction_method: Mapped[str] = mapped_column(String(50), nullable=False)  # pymupdf, python-docx, tesseract
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
```

### Fact Extraction LLM Prompt Pattern

```python
# Pydantic schema for structured LLM output
EXTRACTION_SYSTEM_PROMPT = """You are a legal fact extraction assistant. Given narrative text from a legal intake,
extract atomic factual assertions. Each fact should be the smallest meaningful unit.

Entity types to extract:
- person: Named individuals
- date: Specific dates or date ranges
- location: Places, addresses, jurisdictions
- amount: Dollar amounts, quantities
- organization: Companies, agencies, courts
- party_relationship: employer/employee, landlord/tenant, spouse/spouse
- legal_event: Filing, service, injury, termination, arrest
- document_reference: Contracts, leases, court orders
- time_period: Statute of limitations, employment duration
- claimed_damages: Specific damages claimed

Rules:
1. Only extract facts explicitly stated in the text. Never infer unstated facts.
2. Each fact must have a source_start and source_end character offset in the original text.
3. Use confidence 0.0-1.0 based on how clearly the fact is stated.
4. If a fact contradicts a previously extracted fact, still extract it -- note both.
5. Decompose compound statements into atomic facts.

Return a JSON object matching the ExtractionResult schema."""
```

### Document Extraction (Adapted from folio-enrich)

```python
# Adapting folio-enrich's proven extraction pattern
import asyncio
from pathlib import Path

async def extract_pdf(file_path: Path) -> tuple[str, list[dict]]:
    """Extract text and structural elements from PDF using PyMuPDF."""
    loop = asyncio.get_event_loop()

    def _extract():
        import pymupdf
        doc = pymupdf.open(str(file_path))
        elements = []
        page_texts = []
        for page_num, page in enumerate(doc, start=1):
            text = page.get_text()
            page_texts.append(text)
            # Extract structural elements
            blocks = page.get_text("dict")["blocks"]
            for block in blocks:
                if block["type"] == 0:  # text block
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            elements.append({
                                "text": span["text"],
                                "element_type": _classify_element(span),
                                "page": page_num,
                                "bbox": span["bbox"],
                                "font_size": span["size"],
                            })
        doc.close()
        return "\n\n".join(page_texts), elements

    return await loop.run_in_executor(None, _extract)
```

## Discretion Recommendations

### Text Extraction Approach: Hybrid (Library-Based + folio-enrich Reference)

**Recommendation:** Use library-based extraction (PyMuPDF, python-docx, pytesseract) directly in alea-intake, adapting patterns from folio-enrich's proven ingestors. Do NOT call folio-enrich as an HTTP service for document processing.

**Rationale:**
1. folio-enrich's ingestors are well-structured but tightly coupled to its own DocumentInput/TextElement models and pipeline orchestrator
2. Calling folio-enrich as a service adds deployment complexity (another container, network hop, availability concerns)
3. The core extraction logic (PyMuPDF for PDF, python-docx for DOCX) is straightforward to adapt -- folio-enrich's code proves the approach works
4. alea-intake needs different storage patterns (encrypted files, tenant-scoped) and different output format (source spans for fact linking)
5. Reuse the libraries and patterns, not the service itself

### OCR Engine: pytesseract + Pillow

**Recommendation:** Use pytesseract (Tesseract wrapper) with Pillow for image preprocessing. Tesseract 5.x provides adequate accuracy for document OCR (printed text in legal documents). EasyOCR is heavier (requires PyTorch) and better for scene text, which is not our use case.

**Configuration:** Tesseract with `--psm 6` (assume uniform block of text) for scanned documents, `--psm 3` (fully automatic) for mixed content.

### Document Chunking Strategy

**Recommendation:** Page-level chunking with paragraph-level elements within each page. Each page produces a separate NormalizedContent object with its page number in source spans. For fact extraction, process pages sequentially with accumulated context from previous pages (sliding window of extracted facts).

**For very long documents (>20 pages):** Chunk into groups of 5 pages with 1-page overlap. Each chunk goes through fact extraction independently, then facts are deduplicated by semantic similarity.

### Local Whisper Deployment: Sidecar Service

**Recommendation:** Deploy faster-whisper as a lightweight FastAPI sidecar service. See Pattern 5 above for rationale.

- Separate Docker container with GPU support when available
- Simple REST API: POST /transcribe with audio file, returns JSON transcript
- Uses faster-whisper's `WhisperModel("large-v3", device="auto", compute_type="int8")` for best speed/accuracy tradeoff
- Falls back to CPU with float32 when no GPU available

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| openai-whisper (PyTorch) | faster-whisper (CTranslate2) | 2023+ | 4x speed, 2x less memory, same accuracy |
| Regex-based entity extraction | LLM structured output (Pydantic) | 2024+ | Handles natural language variation; structured validation |
| Single ASR provider | Pluggable provider architecture | Standard pattern | Org chooses provider based on cost, privacy, accuracy |
| File upload -> batch process | Per-message incremental extraction | This project | Real-time conversation requires immediate fact awareness |
| pypdf for PDF extraction | PyMuPDF (pymupdf) | Ongoing | Better extraction quality, faster, structure preservation |

**Deprecated/outdated:**
- `openai-whisper`: Still maintained but slower; use `faster-whisper` for same models with better performance
- `ffmpeg-python` (0.2.0): Unmaintained since 2022; use `pydub` or direct subprocess calls to ffmpeg
- `SpeechRecognition` library: Wrapper around Google's API; doesn't support modern ASR models

## Open Questions

1. **Frontend voice recording UX**
   - What we know: Browser MediaRecorder API records WebM/Opus by default; some iOS browsers record MP4/AAC
   - What's unclear: Exact frontend component library for voice recording (Phase 8 concern, but backend must handle all formats)
   - Recommendation: Backend accepts any format and converts; document supported formats in API

2. **Predefined intake question templates schema**
   - What we know: Orgs can define templates that LLM selects from during conversation
   - What's unclear: Exact schema for question templates (simple text? conditional logic? branching?)
   - Recommendation: Start with simple JSON array of {question, context, relevance_tags}. LLM selects based on extracted facts + relevance_tags. Extend schema later if needed.

3. **Fact extraction model selection**
   - What we know: Dedicated LLM call, can use cheaper/faster model than conversation
   - What's unclear: Which specific model balances extraction accuracy with cost
   - Recommendation: Default to the org's configured LLM model. Allow org-level override for extraction-specific model in Organization.settings (e.g., `extraction_llm_model`). Smaller models like GPT-4o-mini or Claude Haiku work well for structured extraction.

4. **File storage location for audio/documents**
   - What we know: Large files should NOT be stored as database BLOBs (see Pitfall 5)
   - What's unclear: Exact filesystem structure and cloud storage integration
   - Recommendation: Local filesystem for v1 (`./data/uploads/{org_slug}/{intake_id}/`), with a `StorageBackend` abstraction that can later support S3/GCS. Store encrypted file bytes, database stores metadata + encrypted path.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio 0.24.x |
| Config file | `backend/pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `cd backend && python -m pytest tests/ -x --timeout=30` |
| Full suite command | `cd backend && python -m pytest tests/ --timeout=60` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INGEST-01 | Consumer submits text via chat, receives acknowledgment | integration | `pytest tests/test_intake_chat.py -x` | Wave 0 |
| INGEST-02 | Voice input transcribed via pluggable ASR | unit + integration | `pytest tests/test_asr_service.py tests/test_voice_intake.py -x` | Wave 0 |
| INGEST-03 | Document upload with text extraction (PDF, DOCX, image) | unit + integration | `pytest tests/test_document_service.py -x` | Wave 0 |
| INGEST-04 | Professional enters notes on behalf of consumer | integration | `pytest tests/test_professional_intake.py -x` | Wave 0 |
| INGEST-05 | All modalities normalize to common representation | unit | `pytest tests/test_message_pipeline.py -x` | Wave 0 |
| INGEST-06 | Atomic fact extraction from narrative | unit + integration | `pytest tests/test_fact_extraction.py -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `cd backend && python -m pytest tests/ -x --timeout=30`
- **Per wave merge:** `cd backend && python -m pytest tests/ --timeout=60`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_intake_chat.py` -- WebSocket chat tests (INGEST-01)
- [ ] `tests/test_asr_service.py` -- ASR provider unit tests with mocked providers (INGEST-02)
- [ ] `tests/test_voice_intake.py` -- Voice intake integration (INGEST-02)
- [ ] `tests/test_document_service.py` -- Document extraction tests with sample PDF/DOCX/image (INGEST-03)
- [ ] `tests/test_professional_intake.py` -- Professional mode tests (INGEST-04)
- [ ] `tests/test_message_pipeline.py` -- Normalization pipeline tests (INGEST-05)
- [ ] `tests/test_fact_extraction.py` -- Fact extraction with mocked LLM (INGEST-06)
- [ ] `tests/fixtures/` -- Sample test files: small PDF, DOCX, PNG image, WebM audio

## Sources

### Primary (HIGH confidence)
- folio-enrich codebase (`../folio-enrich/backend/app/services/ingestion/`) -- PDF, DOCX, document processing patterns verified by code inspection
- Existing alea-intake codebase -- LLMService, Organization, ConceptResolver patterns verified by code reading
- PyPI registry -- All library versions verified 2026-03-24 via `pip index versions`
- PyMuPDF docs (https://pymupdf.readthedocs.io/) -- Structured text extraction capabilities
- FastAPI docs (https://fastapi.tiangolo.com/advanced/websockets/) -- WebSocket support

### Secondary (MEDIUM confidence)
- faster-whisper GitHub (https://github.com/SYSTRAN/faster-whisper) -- 4x speedup claim, CTranslate2 architecture
- Deepgram docs (https://developers.deepgram.com/docs/live-streaming-audio) -- Streaming + diarization support
- AssemblyAI docs (https://www.assemblyai.com/) -- Streaming + diarization support, Slam-1 model
- Modal blog (https://modal.com/blog/choosing-whisper-variants) -- Whisper variant comparison

### Tertiary (LOW confidence)
- WebSearch results on LLM structured extraction patterns -- general ecosystem trend, not project-specific verification

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- All libraries verified against PyPI; folio-enrich proves PyMuPDF/python-docx patterns work; faster-whisper well-documented
- Architecture: HIGH -- Service patterns directly mirror existing LLMService; WebSocket is native FastAPI; data models follow established TenantBase patterns
- Pitfalls: HIGH -- Based on known async/sync issues in FastAPI, SQLite blob limitations from Phase 1 experience, and standard WebSocket auth concerns
- Fact extraction: MEDIUM -- LLM structured output via Pydantic is standard practice but extraction prompt quality needs iteration in implementation

**Research date:** 2026-03-24
**Valid until:** 2026-04-24 (30 days -- stable domain, well-established libraries)
