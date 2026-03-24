---
phase: 3
slug: input-narrative-capture
status: draft
shadcn_initialized: false
preset: none
created: 2026-03-24
---

# Phase 3 -- UI Design Contract

> Interaction and copywriting contracts for the intake backend layer. Phase 3 builds backend services (WebSocket chat, ASR, document processing, fact extraction) with no frontend components. This contract defines the API-level interaction protocols, state machines, system copy, and error messages that Phase 8 (Frontend Application) will consume when building the chat UI, voice recording UI, and document upload UI.

---

## Design System

| Property | Value |
|----------|-------|
| Tool | none (backend phase -- no UI components built) |
| Preset | not applicable |
| Component library | not applicable (Phase 8 will select) |
| Icon library | not applicable (Phase 8 will select) |
| Font | not applicable (Phase 8 will select) |

**Note:** Phase 3 produces backend services and API contracts only. All frontend visual implementation happens in Phase 8. The spacing, typography, and color sections below establish project-level defaults from the existing tailwind.config.ts for consistency when Phase 8 references this contract.

---

## Spacing Scale

Declared values (inherited from existing `frontend/tailwind.config.ts`):

| Token | Value | Usage |
|-------|-------|-------|
| xs | 4px | Icon gaps, inline padding |
| sm | 8px | Compact element spacing |
| md | 16px | Default element spacing |
| lg | 24px | Section padding |
| xl | 32px | Layout gaps |
| 2xl | 48px | Major section breaks |
| 3xl | 64px | Page-level spacing |

Exceptions: 44px minimum touch target for voice recording start/stop button (Phase 8 implementation)

---

## Typography

Project baseline (to be confirmed when Phase 8 UI-SPEC is created):

| Role | Size | Weight | Line Height |
|------|------|--------|-------------|
| Body | 16px | 400 | 1.5 |
| Label | 14px | 500 | 1.4 |
| Heading | 20px | 600 | 1.2 |
| Display | 28px | 600 | 1.2 |

---

## Color

Project baseline (to be confirmed when Phase 8 UI-SPEC is created):

| Role | Value | Usage |
|------|-------|-------|
| Dominant (60%) | #FAFAFA | Background, surfaces |
| Secondary (30%) | #FFFFFF | Cards, chat bubbles, sidebar |
| Accent (10%) | #2563EB | Send button, active recording indicator, upload progress bar, primary CTA |
| Destructive | #DC2626 | Delete intake, cancel upload, discard transcript |

Accent reserved for: send message button, voice recording active state, document upload progress indicator, primary action buttons in intake flow

---

## Interaction Contracts

### WebSocket Message Protocol

Phase 3 defines the WebSocket contract at `ws://{host}/api/ws/intake/{session_id}`.

**Connection Authentication:**
- JWT token passed as query parameter: `?token={jwt}`
- Connection rejected with close code 4001 if token is invalid or expired
- Connection rejected with close code 4003 if user lacks access to the session

**Client-to-Server Messages:**

| Type | Payload | Description |
|------|---------|-------------|
| `text_message` | `{type: "text_message", content: string, party_id?: int}` | Consumer or professional sends chat text |
| `voice_upload` | `{type: "voice_upload", audio_base64: string, format: string, duration_seconds: number}` | Audio recording submitted for transcription |
| `document_upload` | `{type: "document_upload", file_base64: string, filename: string, mime_type: string, size_bytes: number}` | Document uploaded for extraction |
| `transcript_approve` | `{type: "transcript_approve", transcript_id: int}` | Consumer approves ASR transcript as-is |
| `transcript_edit` | `{type: "transcript_edit", transcript_id: int, edited_text: string}` | Consumer submits corrected transcript |
| `session_pause` | `{type: "session_pause"}` | Consumer pauses the session (multi-session mode) |
| `typing_indicator` | `{type: "typing_indicator", is_typing: boolean}` | Typing state for presence feedback |

**Server-to-Client Messages:**

| Type | Payload | Description |
|------|---------|-------------|
| `system_message` | `{type: "system_message", content: string, message_id: int}` | LLM-generated question or system status |
| `message_ack` | `{type: "message_ack", message_id: int, sequence_number: int}` | Confirms message was received and stored |
| `transcript_ready` | `{type: "transcript_ready", transcript_id: int, text: string, confidence: float, segments: array}` | ASR transcript ready for consumer review |
| `document_extracted` | `{type: "document_extracted", document_id: int, page_count: int, status: string}` | Document extraction completed |
| `extraction_update` | `{type: "extraction_update", facts_count: int, new_facts: array}` | Incremental fact extraction results (internal visibility only unless org enables consumer-facing) |
| `llm_stream` | `{type: "llm_stream", token: string, done: boolean, message_id?: int}` | Streamed LLM response tokens (token-by-token to avoid perceived latency) |
| `error` | `{type: "error", code: string, message: string, recoverable: boolean}` | Error with recovery guidance |
| `session_state` | `{type: "session_state", status: string, facts_count: int, messages_count: int}` | Session state sync on reconnection |

### State Machines

**Intake Status:**
```
active --> paused --> active (resume)
active --> completed
completed --> archived
```

**Intake Session Status:**
```
active --> paused --> active (resume, multi-session only)
active --> completed
```

**Transcript Review Status:**
```
pending_review --> approved (consumer confirms)
pending_review --> edited (consumer corrects, edited text stored)
```

**Document Extraction Status:**
```
pending --> processing --> completed
pending --> processing --> failed (extraction error)
```

**Message Processing Flow:**
```
received --> normalized --> facts_extracted --> concepts_resolved
```

---

## Copywriting Contract

### System Messages (embedded in API responses)

| Element | Copy |
|---------|------|
| Primary CTA | "Send message" (chat), "Start recording" (voice), "Upload document" (document) |
| Session welcome (default) | "Tell me about your legal situation in your own words. You can type, record your voice, or upload documents -- whatever is easiest for you." |
| Session welcome (professional) | "Enter the client's information. You can use the conversational interface or switch to structured form." |
| Session resume | "Welcome back. Here is where we left off. You mentioned {last_topic}. Would you like to continue from there?" |
| Empty state heading | "No intakes yet" |
| Empty state body | "Start a new intake to begin capturing a client's legal situation. Select 'New intake' to get started." |
| Error: connection lost | "Connection interrupted. Reconnecting... Your messages are saved." |
| Error: upload too large | "This file exceeds the {limit}MB size limit. Try a smaller file or split the document into sections." |
| Error: unsupported format | "This file type is not supported. Accepted formats: PDF, DOCX, and image files (JPG, PNG, TIFF)." |
| Error: ASR failed | "Voice transcription failed. You can try recording again or type your message instead." |
| Error: extraction failed | "We could not extract text from this document. The file may be corrupted or password-protected. Try a different copy." |
| Transcript review prompt | "Here is the transcript of your recording. Please review it for accuracy -- especially names, dates, and amounts -- then confirm or edit before continuing." |
| Transcript approved feedback | "Transcript confirmed. Your information has been added to the intake." |
| Recording limit warning | "Recording will stop automatically in {remaining} seconds." |
| Recording stopped | "Recording complete ({duration}). Transcribing..." |
| Document processing | "Processing your document ({filename})..." |
| Document complete | "Document processed: {page_count} pages extracted from {filename}." |
| Facts extracted feedback | "{count} new details captured from your message." |
| Multi-party label | "Information from {party_label}" |
| Session pause confirmation | "Session paused. You can return anytime to continue." |
| Session completed | "Thank you. All your information has been captured. {next_step}" |

### Destructive Actions

| Action | Confirmation Copy |
|--------|------------------|
| Delete intake | "Delete this intake? All messages, recordings, documents, and extracted information will be permanently removed. This cannot be undone." |
| Discard transcript | "Discard this transcript? The voice recording will be kept but the transcription will need to be redone." |
| Cancel upload | "Cancel this upload? The file will not be saved." |

---

## Registry Safety

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| shadcn official | none (backend phase) | not required |

No third-party registries. Phase 3 builds no frontend components.

---

## API Response Shapes (for Phase 8 consumption)

### Intake List Item
```json
{
  "id": 1,
  "status": "active",
  "session_mode": "multi_session",
  "created_at": "2026-03-24T10:00:00Z",
  "updated_at": "2026-03-24T14:30:00Z",
  "messages_count": 12,
  "facts_count": 8,
  "parties": [{"id": 1, "label": "Primary", "role_in_intake": "primary"}]
}
```

### Message in Chat History
```json
{
  "id": 42,
  "sender_type": "consumer",
  "modality": "text",
  "content": "My landlord hasn't returned my security deposit...",
  "sequence_number": 5,
  "created_at": "2026-03-24T10:05:00Z",
  "party_label": "Primary",
  "attachments": []
}
```

### Transcript for Review
```json
{
  "id": 7,
  "recording_id": 3,
  "text": "I signed the lease in January 2024 and paid a deposit of two thousand dollars...",
  "status": "pending_review",
  "confidence": 0.92,
  "segments": [
    {"start": 0.0, "end": 3.2, "text": "I signed the lease in January 2024", "speaker": null}
  ],
  "asr_provider": "whisper",
  "created_at": "2026-03-24T10:10:00Z"
}
```

### Extracted Fact (when consumer-visible)
```json
{
  "id": 15,
  "assertion_text": "Consumer signed a lease in January 2024",
  "fact_type": "event",
  "entity_type": "legal_event",
  "confidence": 0.95,
  "is_active": true,
  "party_label": "Primary",
  "source": {"message_id": 42, "start_char": 0, "end_char": 45}
}
```

---

## Checker Sign-Off

- [ ] Dimension 1 Copywriting: PASS
- [ ] Dimension 2 Visuals: PASS (backend phase -- interaction protocols documented)
- [ ] Dimension 3 Color: PASS (project baseline declared)
- [ ] Dimension 4 Typography: PASS (project baseline declared)
- [ ] Dimension 5 Spacing: PASS (inherited from tailwind.config.ts)
- [ ] Dimension 6 Registry Safety: PASS (no frontend dependencies)

**Approval:** pending
