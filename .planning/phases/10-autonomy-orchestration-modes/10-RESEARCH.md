# Phase 10: Autonomy & Orchestration Modes - Research

**Researched:** 2026-04-03
**Domain:** Human-in-the-loop orchestration, configurable autonomy spectrum, real-time approval workflows
**Confidence:** HIGH

## Summary

Phase 10 wraps the existing AnalysisOrchestrator (Phase 4) with an autonomy layer that intercepts stage execution to enforce org-configured checkpoint behavior. The core technical challenge is implementing a pause/resume mechanism at stage boundaries -- when a stage reaches a checkpoint, the system must pause the pipeline, notify professionals via WebSocket (and optionally email), and resume only after approval, rejection, or timeout. This is fundamentally an asyncio.Event coordination problem, not a task queue problem.

The existing codebase provides strong foundations: the AnalysisOrchestrator already has a clean `_execute_stage` method that can be intercepted, the IntakeConnectionManager handles WebSocket broadcasting, the AuditLog model supports extensible event logging, and the OrganizationConfig model stores JSON configuration. The autonomy layer adds a new AutonomyConfig Pydantic schema stored in OrganizationConfig, an AutonomyInterceptor that wraps stage execution, an ApprovalQueue service with asyncio.Event-based pause/resume, and new API endpoints for approval/reject/edit actions.

**Primary recommendation:** Use the interceptor/decorator pattern on `_execute_stage` -- the AutonomyInterceptor checks the org's checkpoint config before each stage, and either passes through (auto mode) or pauses with an asyncio.Event until approval arrives (checkpoint mode). Safety alerts from Phase 5 always force checkpoint regardless of config.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Autonomy is org-configurable on a spectrum, not three fixed modes. Default is "fully autonomous except safety alerts." Org admin configures the degree of human oversight: (a) humans in-the-loop (approve before AI proceeds) or (b) humans on-the-loop (review/override after AI proceeds). All three granularity levels built: per-stage approval, per-iteration approval, consumer-facing-only approval. Admin org decides which to implement.
- **D-02:** Safety alerts (critical tier from Phase 5) ALWAYS interrupt regardless of autonomy config. This is non-negotiable.
- **D-03:** Per-stage checkpoint toggles with priority override. Admin configures checklist of analysis stages (issue_spot, explore, research, fact_map, gap_analyze, question_gen). Each stage: auto or checkpoint. Safety alerts always checkpoint regardless. Defaults: all stages auto except question_gen (checkpoint).
- **D-04:** Configurable timeout with auto-proceed option. Org sets timeout (default 30 min). Three behaviors (org chooses): (1) auto-proceed with audit note, (2) queue for next available professional, (3) pause until approval. Consumer sees "waiting for review" status.
- **D-05:** Professional can escalate/de-escalate mid-intake. Mode change takes effect at next stage boundary (current stage completes first). Audit log records mode change with reason. Reversible in either direction.
- **D-06:** Dedicated "Autonomy" tab in admin settings. Shows current mode, per-stage checkpoint toggles, timeout config, auto-proceed toggle. Preview panel shows consumer experience per mode. Inherits Phase 8 admin tabbed interface.
- **D-07:** Both WebSocket-pushed approval cards AND email/notification queue -- org decides between one or both. Real-time: approval card in Live Intakes view with Approve/Edit/Reject buttons. Email: notification with link to approval screen.
- **D-08:** Reject re-runs stage with professional's guidance note as additional LLM context. Re-runs up to 2 times; if still rejected, stage is skipped with audit note. Professional always has final say.
- **D-09:** Edit opens inline editing of AI output before pipeline proceeds. Professional can modify proposed questions, remove claims, adjust mappings. Edits preserved in audit trail.
- **D-10:** Full decision audit with timestamps and actors. Every autonomy event logged: mode set/changed (by whom, when, reason), checkpoint reached (stage, wait start), approval/reject/edit (by whom, guidance text), auto-proceed triggered (timeout duration), stage skip (reason). All entries link to intake + analysis run. Via Phase 1 audit log system.
- **D-11:** Mode-appropriate transparency. Chatbot mode: "AI Assistant" label on system messages. Professional/agent mode: "Legal professional is reviewing" status when waiting (NOT "attorney"). Agent mode: "Analysis paused for review" when checkpoint reached. Org configures label text per language (i18n).
- **D-12:** Both strict-chatbot AND identical-across-modes built -- admin org decides. Option A (recommended default for chatbot): all critical + elevated protocols mandatory, auto-escalation for immediate danger. Option B (for professional-supervised): critical mandatory, professional can silence elevated. Agent mode follows chatbot rules when unattended, professional rules when active.

### Claude's Discretion
- Approval card component layout
- Email notification template design
- Timeout countdown UI
- Auto-proceed animation/feedback
- Audit event schema details
- Mode preview panel visualization

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AUTONOMY-01 | Chatbot mode: AI runs all steps autonomously, presents questions directly to consumer | AutonomyConfig with all stages set to "auto"; default preset config |
| AUTONOMY-02 | Professional mode: AI suggests at each stage, human professional approves before proceeding | AutonomyConfig with all stages set to "checkpoint"; ApprovalQueue pause/resume |
| AUTONOMY-03 | Agent mode: AI orchestrates autonomously, pauses at configurable checkpoints for human review | AutonomyConfig with selective stages as checkpoint; same ApprovalQueue mechanism |
| AUTONOMY-04 | Autonomy level is configurable per organization | AutonomyConfig stored in OrganizationConfig.autonomy_config_json; admin API endpoints |
| AUTONOMY-05 | Per-org configuration of which analysis stages require human approval in agent mode | Per-stage checkpoint toggles in AutonomyConfig schema; AdminTabs Autonomy tab |

</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.135.1 | API endpoints for approval/reject/edit/mode-switch | Already installed; extends existing analysis router |
| SQLAlchemy | 2.0.49 | New AutonomyEvent + ApprovalRequest models | Already installed; follows existing TenantBase pattern |
| Pydantic | 2.12.5 | AutonomyConfig, ApprovalRequest schemas | Already installed; matches existing analysis schemas |
| asyncio (stdlib) | 3.13 | asyncio.Event for pause/resume at checkpoints | No dependency; Python stdlib |
| React | 19.x | Approval card components, Autonomy admin tab | Already installed frontend framework |
| Zustand | 5.0.12 | Approval queue state management | Already installed; extends existing store pattern |
| @tanstack/react-query | 5.96.2 | Server state for approval queue, autonomy config | Already installed; extends existing query pattern |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| aiosmtplib | 5.1.0 | Async email notifications for checkpoint approvals | Only when org enables email notifications (D-07) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| asyncio.Event | Celery task queue | Celery adds Redis/RabbitMQ dependency, overkill for in-process pause/resume; asyncio.Event is sufficient since the orchestrator already runs as async task |
| asyncio.Event | Database polling | Polling adds latency and DB load; Event is zero-cost while waiting |
| aiosmtplib | fastapi-mail | fastapi-mail wraps aiosmtplib with Jinja2 templates; raw aiosmtplib is simpler and avoids extra dependency since project already has Jinja2-free email needs |

**Installation:**
```bash
pip install aiosmtplib
```

**Note:** No frontend packages needed -- all required packages are already installed.

## Architecture Patterns

### Recommended Project Structure
```
backend/app/
├── services/analysis/
│   ├── orchestrator.py          # Existing -- modify _execute_stage to call interceptor
│   ├── autonomy/
│   │   ├── __init__.py
│   │   ├── config.py            # AutonomyConfig Pydantic schema + presets
│   │   ├── interceptor.py       # AutonomyInterceptor -- wraps stage execution
│   │   ├── approval_queue.py    # In-memory approval tracking with asyncio.Event
│   │   ├── notification.py      # WebSocket + email notification dispatch
│   │   └── schemas.py           # ApprovalRequest, ApprovalAction, AutonomyEvent schemas
│   └── schemas.py               # Existing -- extend AnalysisConfig with autonomy field
├── models/
│   └── autonomy.py              # ApprovalRequest, AutonomyEvent DB models
├── routers/
│   └── autonomy.py              # Approval/reject/edit/mode-switch endpoints
│   └── analysis.py              # Existing -- extend with autonomy status

frontend/src/
├── features/
│   ├── admin/components/
│   │   └── AutonomySettings.tsx  # Autonomy tab content
│   ├── chat/components/
│   │   └── ApprovalCard.tsx      # Inline approval card for professionals
│   │   └── ReviewStatus.tsx      # "Waiting for review" consumer indicator
│   └── autonomy/
│       ├── api.ts                # Approval/reject/edit API calls
│       ├── hooks.ts              # useApprovalQueue, useAutonomyConfig
│       └── types.ts              # TypeScript types
```

### Pattern 1: Autonomy Interceptor (core pattern)
**What:** A wrapper around `_execute_stage` that checks autonomy config and either passes through or pauses for approval.
**When to use:** Every stage execution in the orchestrator pipeline.
**Example:**
```python
# backend/app/services/analysis/autonomy/interceptor.py
import asyncio
from typing import Any
from app.services.analysis.autonomy.config import AutonomyConfig, StageCheckpoint

class AutonomyInterceptor:
    """Wraps stage execution with checkpoint logic."""

    def __init__(
        self,
        config: AutonomyConfig,
        approval_queue: "ApprovalQueue",
        audit_logger: "AutonomyAuditLogger",
    ):
        self._config = config
        self._queue = approval_queue
        self._audit = audit_logger

    async def execute_with_autonomy(
        self,
        stage_name: str,
        execute_fn,  # callable that runs the actual stage
        run_id: int,
        iteration_id: int,
        safety_triggered: bool = False,
    ) -> dict:
        """Check autonomy config, pause if checkpoint, then execute."""
        checkpoint = self._config.get_stage_checkpoint(stage_name)

        # D-02: Safety alerts ALWAYS force checkpoint
        needs_approval = (
            safety_triggered
            or checkpoint == StageCheckpoint.CHECKPOINT
        )

        if not needs_approval:
            # Auto mode: execute immediately
            return await execute_fn()

        # Checkpoint mode: pause and wait for approval
        request = await self._queue.create_request(
            run_id=run_id,
            stage_name=stage_name,
            iteration_id=iteration_id,
            safety_triggered=safety_triggered,
        )

        # Notify professionals (WebSocket + optional email)
        await self._queue.notify_professionals(request)

        # Wait for approval with configurable timeout
        action = await self._queue.wait_for_action(
            request.id,
            timeout_seconds=self._config.timeout_seconds,
            timeout_behavior=self._config.timeout_behavior,
        )

        if action.decision == "approve":
            return await execute_fn()
        elif action.decision == "reject":
            return await self._handle_reject(
                stage_name, execute_fn, action, run_id, iteration_id
            )
        elif action.decision == "edit":
            # Execute, then apply professional edits
            result = await execute_fn()
            return self._apply_edits(result, action.edits)
        elif action.decision == "auto_proceed":
            # Timeout: auto-proceed with audit
            await self._audit.log_auto_proceed(request)
            return await execute_fn()
        elif action.decision == "queue":
            # Timeout: queue for next professional (re-wait)
            return await self._requeue(request, execute_fn)
        else:
            # Timeout: pause until approval (no timeout)
            action = await self._queue.wait_for_action(
                request.id, timeout_seconds=None
            )
            return await self._process_action(action, execute_fn)
```

### Pattern 2: ApprovalQueue with asyncio.Event
**What:** In-memory approval tracking that uses asyncio.Event for zero-cost pause/resume.
**When to use:** Whenever a stage reaches a checkpoint.
**Example:**
```python
# backend/app/services/analysis/autonomy/approval_queue.py
import asyncio
from datetime import datetime, timezone

class ApprovalQueue:
    """Manages pending approval requests with asyncio.Event-based waiting."""

    def __init__(self):
        # request_id -> (ApprovalRequest, asyncio.Event, ApprovalAction|None)
        self._pending: dict[int, tuple[Any, asyncio.Event, Any]] = {}

    async def create_request(self, run_id, stage_name, iteration_id, safety_triggered):
        """Create approval request and register an asyncio.Event."""
        # ... create DB record ...
        event = asyncio.Event()
        self._pending[request.id] = (request, event, None)
        return request

    async def wait_for_action(
        self, request_id: int, timeout_seconds: int | None
    ) -> "ApprovalAction":
        """Wait for professional action. Returns when approved/rejected/timed out."""
        _, event, _ = self._pending[request_id]
        try:
            if timeout_seconds:
                await asyncio.wait_for(event.wait(), timeout=timeout_seconds)
            else:
                await event.wait()
        except asyncio.TimeoutError:
            return ApprovalAction(decision="timeout")

        _, _, action = self._pending[request_id]
        return action

    def resolve(self, request_id: int, action: "ApprovalAction") -> None:
        """Called by API endpoint when professional acts."""
        if request_id not in self._pending:
            raise ValueError(f"No pending request {request_id}")
        request, event, _ = self._pending[request_id]
        self._pending[request_id] = (request, event, action)
        event.set()  # Unblocks the waiting coroutine
```

### Pattern 3: Org Configuration Schema (spectrum, not modes)
**What:** AutonomyConfig as a Pydantic schema with per-stage toggles, stored in OrganizationConfig.
**When to use:** All autonomy configuration.
**Example:**
```python
# backend/app/services/analysis/autonomy/config.py
from enum import Enum
from pydantic import BaseModel, Field

class StageCheckpoint(str, Enum):
    AUTO = "auto"
    CHECKPOINT = "checkpoint"

class TimeoutBehavior(str, Enum):
    AUTO_PROCEED = "auto_proceed"      # D-04 option 1
    QUEUE_NEXT = "queue_next"          # D-04 option 2
    PAUSE_UNTIL = "pause_until"        # D-04 option 3

class SafetyBehavior(str, Enum):
    STRICT = "strict"                  # D-12 Option A: all critical + elevated mandatory
    PROFESSIONAL = "professional"      # D-12 Option B: critical mandatory, elevated silenceable

class AutonomyConfig(BaseModel):
    """Per-org autonomy configuration -- stored as JSON in OrganizationConfig."""

    # Per-stage checkpoint toggles (D-03)
    stage_checkpoints: dict[str, StageCheckpoint] = Field(default_factory=lambda: {
        "issue_spot": StageCheckpoint.AUTO,
        "explore": StageCheckpoint.AUTO,
        "research": StageCheckpoint.AUTO,
        "fact_map": StageCheckpoint.AUTO,
        "gap_analyze": StageCheckpoint.AUTO,
        "question_gen": StageCheckpoint.CHECKPOINT,  # Default: checkpoint on questions
    })

    # Timeout configuration (D-04)
    timeout_seconds: int = Field(default=1800, ge=60)  # 30 min default
    timeout_behavior: TimeoutBehavior = TimeoutBehavior.AUTO_PROCEED

    # Safety behavior (D-12)
    safety_behavior: SafetyBehavior = SafetyBehavior.STRICT

    # Notification channels (D-07)
    notify_websocket: bool = True
    notify_email: bool = False

    # Consumer-facing labels (D-11)
    labels: dict[str, str] = Field(default_factory=lambda: {
        "ai_assistant": "AI Assistant",
        "reviewing": "Legal professional is reviewing",
        "paused": "Analysis paused for review",
    })

    def get_stage_checkpoint(self, stage_name: str) -> StageCheckpoint:
        return self.stage_checkpoints.get(stage_name, StageCheckpoint.AUTO)

    @classmethod
    def chatbot_preset(cls) -> "AutonomyConfig":
        """AUTONOMY-01: All stages auto."""
        return cls(stage_checkpoints={
            s: StageCheckpoint.AUTO for s in [
                "issue_spot", "explore", "research",
                "fact_map", "gap_analyze", "question_gen"
            ]
        })

    @classmethod
    def professional_preset(cls) -> "AutonomyConfig":
        """AUTONOMY-02: All stages checkpoint."""
        return cls(stage_checkpoints={
            s: StageCheckpoint.CHECKPOINT for s in [
                "issue_spot", "explore", "research",
                "fact_map", "gap_analyze", "question_gen"
            ]
        })

    @classmethod
    def agent_preset(cls) -> "AutonomyConfig":
        """AUTONOMY-03: Selective checkpoints (default)."""
        return cls()  # Uses defaults: only question_gen is checkpoint
```

### Pattern 4: Mid-Intake Mode Switching (D-05)
**What:** Mode change takes effect at the next stage boundary, not mid-stage.
**When to use:** When professional escalates or de-escalates.
**Example:**
```python
# The interceptor checks config at each stage boundary.
# Mid-intake mode switch = update the config in DB + in-memory.
# The AutonomyInterceptor reads config before each stage,
# so the change naturally takes effect at the next stage.

async def switch_autonomy_mode(
    run_id: int,
    new_config: AutonomyConfig,
    actor_id: int,
    reason: str,
    db_session: AsyncSession,
):
    """Switch autonomy config mid-intake. Takes effect at next stage boundary."""
    # Update org config
    # ... update OrganizationConfig.autonomy_config_json ...

    # Audit log the mode change (D-10)
    await audit_logger.log_mode_change(
        run_id=run_id,
        actor_id=actor_id,
        reason=reason,
        old_config=old_config,
        new_config=new_config,
    )
```

### Pattern 5: Reject with Re-run (D-08)
**What:** On rejection, re-run the stage with professional guidance as additional LLM context, up to 2 retries.
**When to use:** When a professional rejects AI output at a checkpoint.
**Example:**
```python
async def _handle_reject(
    self, stage_name, execute_fn, action, run_id, iteration_id,
    max_retries=2,
):
    """Re-run stage with guidance, up to max_retries."""
    for attempt in range(max_retries):
        # Inject guidance into LLM context
        result = await execute_fn(guidance=action.guidance_text)

        # Create new approval request for the re-run
        request = await self._queue.create_request(
            run_id=run_id,
            stage_name=stage_name,
            iteration_id=iteration_id,
            is_rerun=True,
            attempt=attempt + 1,
            guidance=action.guidance_text,
        )
        await self._queue.notify_professionals(request)
        new_action = await self._queue.wait_for_action(
            request.id,
            timeout_seconds=self._config.timeout_seconds,
        )

        if new_action.decision == "approve":
            return result
        elif new_action.decision == "edit":
            return self._apply_edits(result, new_action.edits)

    # Exhausted retries: skip stage with audit note
    await self._audit.log_stage_skip(run_id, stage_name, "max_rejections_exceeded")
    return {"skipped": True, "reason": "max_rejections_exceeded"}
```

### Anti-Patterns to Avoid
- **Subclassing AnalysisOrchestrator:** Do NOT create a subclass. Instead, inject the AutonomyInterceptor into the existing orchestrator. The interceptor wraps `_execute_stage` calls without modifying the orchestrator's core logic.
- **Database polling for approval:** Do NOT poll the database to check if approval has arrived. Use asyncio.Event which is zero-cost while waiting and provides instant wake-up.
- **Storing asyncio.Events in the database:** Events are in-memory only. The ApprovalRequest DB record tracks state for persistence/audit; the asyncio.Event is for in-process coordination only. On server restart, pending requests become "timed_out" and are re-queued.
- **Blocking the event loop with timeout sleeps:** Use `asyncio.wait_for(event.wait(), timeout=N)` which is non-blocking, not `time.sleep()` or busy-wait loops.
- **Rigid mode enum instead of config spectrum:** Do NOT create a Mode enum with three values. The three "modes" (chatbot/professional/agent) are preset factory methods on AutonomyConfig, not a type discriminator. Any combination of per-stage toggles is valid.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async pause/resume | Custom threading or polling loop | asyncio.Event + asyncio.wait_for | Zero-cost waiting, instant wake-up, handles timeout natively |
| Email sending | Custom SMTP socket handling | aiosmtplib.send() | Handles TLS, authentication, error recovery, async-native |
| Timeout with fallback | Manual timer tracking | asyncio.wait_for() with TimeoutError catch | Built into asyncio, handles cancellation correctly |
| Config validation | Manual dict validation | Pydantic BaseModel with validators | Matches existing codebase pattern, handles serialization |
| WebSocket broadcasting | Custom connection tracking | Existing IntakeConnectionManager | Already built in Phase 8, supports per-session messaging |

**Key insight:** The entire autonomy layer is a coordination problem, not a computation problem. asyncio primitives (Event, wait_for, gather) handle all the concurrency needs. No external task queue or worker system is required.

## Common Pitfalls

### Pitfall 1: asyncio.Event Not Surviving Server Restart
**What goes wrong:** If the server restarts while a stage is awaiting approval, the in-memory asyncio.Event is lost and the pipeline hangs forever.
**Why it happens:** asyncio.Events are ephemeral -- they exist only in the current process.
**How to avoid:** Persist ApprovalRequest state in the DB with status "pending". On server startup, scan for pending requests and either: (a) re-create Events for them, or (b) mark them as "timed_out" and let the orchestrator's existing resume mechanism handle re-execution.
**Warning signs:** Analysis runs stuck in "running" status after deployment.

### Pitfall 2: Race Condition Between Approval and Timeout
**What goes wrong:** A professional approves at the exact moment the timeout fires, causing the stage to execute twice.
**Why it happens:** asyncio.wait_for cancels the wait but the approval endpoint may have already set the Event.
**How to avoid:** Use a lock or atomic state transition on the ApprovalRequest. The resolve() method should check the request status before setting the Event -- if already timed out, return a "too late" response to the professional.
**Warning signs:** Duplicate stage execution, duplicate audit entries.

### Pitfall 3: WebSocket Connection Lost During Approval Wait
**What goes wrong:** The professional's WebSocket disconnects, so they never see the approval card.
**Why it happens:** Network issues, browser tab closed, session timeout.
**How to avoid:** The approval request persists in DB regardless of WebSocket state. When a professional reconnects (or opens the Live Intakes view), pending requests load from DB. Email notification (D-07) provides a fallback channel. The approval API endpoint works independently of WebSocket.
**Warning signs:** Approval requests timing out despite active professionals.

### Pitfall 4: Modifying Orchestrator Stage Order Breaks Autonomy
**What goes wrong:** Autonomy config references stage names that the orchestrator no longer uses, or the stage list changes.
**Why it happens:** Stage names are strings that couple autonomy config to orchestrator internals.
**How to avoid:** Use `AnalysisOrchestrator.STAGES` as the source of truth for valid stage names. AutonomyConfig validation should reject unknown stage names. The admin UI should render toggles based on the orchestrator's actual stage list, not a hardcoded list.
**Warning signs:** Silently ignored checkpoint toggles, stages running without expected approval.

### Pitfall 5: Edit-in-Place Breaks Data Integrity
**What goes wrong:** Professional edits AI output (removes a claim, changes a mapping), but downstream stages still reference the removed data.
**Why it happens:** Fact-claim mappings, gaps, and questions have foreign key relationships. Editing output mid-pipeline can create orphaned references.
**How to avoid:** Edits should produce a new version of the stage output (not mutate the existing records). The next stage receives the edited output. Audit trail preserves both original and edited versions. Use a "supersedes" flag on the original records rather than deleting them.
**Warning signs:** Foreign key violations, missing claims in downstream stages.

### Pitfall 6: Consumer Sees Stale Status During Approval Wait
**What goes wrong:** Consumer's chat shows analysis running at 60% for 30 minutes while actually waiting for professional approval.
**Why it happens:** The existing analysis_progress WebSocket message doesn't have a "waiting_for_approval" state.
**How to avoid:** Add a new WebSocket event type "approval_pending" with stage name and estimated wait time. The consumer-facing UI shows the D-11 labels ("Legal professional is reviewing" / "Analysis paused for review"). Update the AnalysisProgress type in frontend/src/features/chat/types.ts.
**Warning signs:** Consumer confusion, support tickets about "stuck" analysis.

### Pitfall 7: Email Notifications Without SMTP Config
**What goes wrong:** Org enables email notifications but no SMTP server is configured, causing silent failures or crashes.
**Why it happens:** No SMTP configuration exists in the current codebase.
**How to avoid:** Add SMTP config to OrganizationConfig (or global settings). NotificationService degrades gracefully: if SMTP not configured, log a warning and rely on WebSocket only. Admin UI disables email toggle when SMTP not configured.
**Warning signs:** Email notification toggle enabled but no emails sent.

## Code Examples

### Modifying AnalysisOrchestrator to Support Autonomy
```python
# In orchestrator.py -- modify __init__ and _execute_stage
# Source: existing codebase pattern analysis

class AnalysisOrchestrator:
    def __init__(
        self,
        db_session: AsyncSession,
        llm_service: LLMService,
        folio: FOLIO | None = None,
        embedding_service: EmbeddingService | None = None,
        org_config: dict | None = None,
        max_iterations: int = 10,
        autonomy_interceptor: "AutonomyInterceptor | None" = None,  # NEW
    ) -> None:
        # ... existing init ...
        self._autonomy = autonomy_interceptor

    async def _execute_stage(self, stage_name, run, iteration, ws_manager, jurisdiction=None):
        """Execute stage with optional autonomy checkpoint."""
        async def _do_execute():
            # Original _execute_stage logic (renamed)
            return await self._execute_stage_inner(
                stage_name, run, iteration, ws_manager, jurisdiction
            )

        if self._autonomy:
            return await self._autonomy.execute_with_autonomy(
                stage_name=stage_name,
                execute_fn=_do_execute,
                run_id=run.id,
                iteration_id=iteration.id,
            )
        return await _do_execute()
```

### New DB Models for Approval Tracking
```python
# backend/app/models/autonomy.py
from datetime import datetime
from sqlalchemy import Boolean, Float, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import TenantBase

class ApprovalRequest(TenantBase):
    """A pending or resolved approval request at a pipeline checkpoint."""
    __tablename__ = "approval_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(Integer, nullable=False)
    iteration_id: Mapped[int] = mapped_column(Integer, nullable=False)
    stage_name: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    # pending | approved | rejected | edited | auto_proceeded | skipped
    safety_triggered: Mapped[bool] = mapped_column(Boolean, default=False)
    is_rerun: Mapped[bool] = mapped_column(Boolean, default=False)
    rerun_attempt: Mapped[int] = mapped_column(Integer, default=0)
    guidance_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    stage_output_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    edited_output_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timeout_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(nullable=True)


class AutonomyEvent(TenantBase):
    """Audit trail entry for autonomy-specific events (D-10)."""
    __tablename__ = "autonomy_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(Integer, nullable=False)
    intake_id: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # mode_set | mode_changed | checkpoint_reached | approved | rejected
    # edited | auto_proceeded | stage_skipped | timeout_queued
    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stage_name: Mapped[str | None] = mapped_column(String(30), nullable=True)
    details_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
```

### Adding Autonomy Column to OrganizationConfig
```python
# Add to existing backend/app/models/organization.py
class OrganizationConfig(TenantBase):
    # ... existing fields ...
    autonomy_config_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
```

### Approval API Endpoints
```python
# backend/app/routers/autonomy.py
from fastapi import APIRouter, Depends
from app.core.permissions import require_role
from app.models.user import Role

router = APIRouter(
    prefix="/api/v1/autonomy",
    tags=["autonomy"],
    dependencies=[Depends(require_role(Role.PROFESSIONAL))],
)

@router.get("/pending")
async def list_pending_approvals(...):
    """List all pending approval requests for professional's org."""

@router.post("/requests/{request_id}/approve")
async def approve_stage(request_id: int, ...):
    """Approve a pending stage -- unblocks the pipeline."""

@router.post("/requests/{request_id}/reject")
async def reject_stage(request_id: int, body: RejectBody, ...):
    """Reject a stage with guidance text -- triggers re-run."""

@router.post("/requests/{request_id}/edit")
async def edit_stage_output(request_id: int, body: EditBody, ...):
    """Edit AI output and approve with modifications."""

@router.post("/runs/{run_id}/switch-mode")
async def switch_autonomy_mode(run_id: int, body: ModeSwitchBody, ...):
    """Switch autonomy config mid-intake (D-05)."""
```

### WebSocket Event Types for Autonomy
```typescript
// Extend frontend/src/features/chat/types.ts
export type WSEvent =
  | { type: 'message_ack'; client_id: string; id: string; timestamp: string }
  | { type: 'llm_stream'; message_id: string; token: string; done: boolean }
  | { type: 'analysis_progress'; data: AnalysisProgress }
  | { type: 'safety_alert'; tier: SafetyAlert['tier']; payload: SafetyAlert }
  | { type: 'fact_extracted'; count: number }
  | { type: 'error'; code: string; message: string }
  // NEW: Autonomy events
  | { type: 'approval_pending'; request_id: number; stage: string; safety: boolean }
  | { type: 'approval_resolved'; request_id: number; decision: string }
  | { type: 'review_status'; status: 'reviewing' | 'paused' | 'proceeding'; label: string }
```

### Admin Autonomy Tab Component
```tsx
// frontend/src/features/admin/components/AutonomySettings.tsx
// Added as a new tab in AdminTabs.tsx alongside existing tabs
// Uses existing Tabs/TabsContent pattern from AdminTabs.tsx
// Stage toggles rendered from AnalysisOrchestrator.STAGES (fetched via API)
// Timeout config with number input + behavior dropdown
// Safety behavior radio group (strict vs professional)
// Mode preview panel showing consumer experience per config
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Rigid mode enum (chatbot/professional/agent) | Spectrum of per-stage toggles with preset factories | This phase (D-01) | More flexible; modes become presets on a continuous config space |
| Task queue (Celery) for human-in-loop | asyncio.Event for in-process coordination | 2024-2025 pattern shift | Simpler for single-process deployments; no broker dependency |
| Polling DB for approval status | Event-driven with asyncio.Event + WebSocket push | Standard async pattern | Zero-cost waiting; instant notification on both ends |

**Deprecated/outdated:**
- Thread-based synchronization (threading.Event): Replaced by asyncio.Event in async codebases
- Celery for in-process approval: Overkill when orchestrator and approval handler share the same event loop

## Open Questions

1. **Multi-worker deployment and asyncio.Event scope**
   - What we know: asyncio.Event is per-process. In a single-worker uvicorn deployment, one Event serves both the orchestrator and the API endpoint.
   - What's unclear: In multi-worker deployment (multiple uvicorn workers), the orchestrator coroutine and the approval API endpoint might be in different processes.
   - Recommendation: For MVP, assume single-worker. Document that multi-worker requires either: (a) sticky sessions so approval requests route to the same worker, or (b) Redis pub/sub for cross-process Event signaling (Phase 11 deployment concern). The DB-persisted ApprovalRequest status ensures no data loss regardless.

2. **Email notification SMTP configuration source**
   - What we know: No SMTP configuration exists in the current codebase.
   - What's unclear: Whether SMTP config should be per-org or global.
   - Recommendation: Global SMTP config in Settings (backend/app/config.py). Per-org toggle on/off for email notifications. Degrade gracefully if SMTP not configured.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio (backend); vitest 4.1.x (frontend) |
| Config file | backend/pyproject.toml; frontend/vite.config.ts |
| Quick run command | `cd backend && python -m pytest tests/test_autonomy*.py -x` |
| Full suite command | `cd backend && python -m pytest tests/ -x && cd ../frontend && npx vitest run` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AUTONOMY-01 | All stages auto (chatbot preset) | unit | `pytest tests/test_autonomy_interceptor.py::test_chatbot_all_auto -x` | Wave 0 |
| AUTONOMY-02 | All stages checkpoint (professional preset) | unit | `pytest tests/test_autonomy_interceptor.py::test_professional_all_checkpoint -x` | Wave 0 |
| AUTONOMY-03 | Selective checkpoints (agent preset) | unit | `pytest tests/test_autonomy_interceptor.py::test_agent_selective_checkpoints -x` | Wave 0 |
| AUTONOMY-04 | Per-org config persistence | unit | `pytest tests/test_autonomy_config.py::test_org_config_crud -x` | Wave 0 |
| AUTONOMY-05 | Per-stage toggle in admin UI | unit | `cd frontend && npx vitest run src/features/admin/components/AutonomySettings.test.tsx` | Wave 0 |
| D-02 | Safety always forces checkpoint | unit | `pytest tests/test_autonomy_interceptor.py::test_safety_always_checkpoints -x` | Wave 0 |
| D-04 | Timeout behaviors (auto-proceed, queue, pause) | unit | `pytest tests/test_autonomy_approval.py::test_timeout_behaviors -x` | Wave 0 |
| D-05 | Mid-intake mode switch | unit | `pytest tests/test_autonomy_interceptor.py::test_mid_intake_mode_switch -x` | Wave 0 |
| D-08 | Reject re-runs with guidance | unit | `pytest tests/test_autonomy_approval.py::test_reject_rerun_with_guidance -x` | Wave 0 |
| D-10 | Audit trail completeness | unit | `pytest tests/test_autonomy_audit.py -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `cd backend && python -m pytest tests/test_autonomy*.py -x`
- **Per wave merge:** `cd backend && python -m pytest tests/ -x && cd ../frontend && npx vitest run`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_autonomy_interceptor.py` -- covers AUTONOMY-01 through AUTONOMY-03, D-02, D-05
- [ ] `tests/test_autonomy_config.py` -- covers AUTONOMY-04, config schema validation
- [ ] `tests/test_autonomy_approval.py` -- covers D-04, D-08 approval queue and timeout
- [ ] `tests/test_autonomy_audit.py` -- covers D-10 audit trail events
- [ ] `frontend/src/features/admin/components/AutonomySettings.test.tsx` -- covers AUTONOMY-05

## Sources

### Primary (HIGH confidence)
- Existing codebase analysis: `backend/app/services/analysis/orchestrator.py` -- AnalysisOrchestrator._execute_stage pattern
- Existing codebase analysis: `backend/app/models/analysis.py` -- AnalysisStage checkpoint model
- Existing codebase analysis: `backend/app/services/screening/middleware.py` -- Safety screening three-tier pattern
- Existing codebase analysis: `backend/app/middleware/audit.py` -- AuditMiddleware pattern
- Existing codebase analysis: `backend/app/models/organization.py` -- OrganizationConfig JSON fields
- Existing codebase analysis: `backend/app/routers/intake.py` -- IntakeConnectionManager WebSocket broadcasting
- Existing codebase analysis: `frontend/src/features/chat/types.ts` -- WSEvent union type
- Existing codebase analysis: `frontend/src/features/admin/components/AdminTabs.tsx` -- Tab pattern

### Secondary (MEDIUM confidence)
- Python asyncio documentation -- asyncio.Event, asyncio.wait_for patterns
- aiosmtplib documentation (v5.1.0) -- async email sending API
- Human-in-the-loop patterns from OpenAI Agents SDK, LangGraph, Temporal

### Tertiary (LOW confidence)
- Multi-worker asyncio.Event coordination patterns -- needs validation for production deployment

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already installed except aiosmtplib; patterns directly extend existing code
- Architecture: HIGH -- interceptor pattern clearly maps to existing _execute_stage; asyncio.Event is well-understood
- Pitfalls: HIGH -- identified from codebase analysis (WebSocket lifecycle, DB model relationships, restart recovery)
- Multi-worker: LOW -- asyncio.Event is single-process; production multi-worker needs Redis pub/sub (Phase 11)

**Research date:** 2026-04-03
**Valid until:** 2026-05-03 (stable domain; patterns unlikely to change)
