# Phase 10: Autonomy & Orchestration Modes - Context

**Gathered:** 2026-04-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Configurable autonomy system that wraps the existing analysis pipeline with org-defined oversight levels. Not three rigid modes but a spectrum of human involvement — from fully autonomous (AI-only) to fully human-guided (professional approves every stage) — with per-stage checkpoint toggles, timeout handling, mid-intake mode switching, approval queues, and full audit trail. All org-configurable.

</domain>

<decisions>
## Implementation Decisions

### Autonomy Model (not rigid modes — a spectrum)
- **D-01:** Autonomy is org-configurable on a spectrum, not three fixed modes. Default is "fully autonomous except safety alerts." Org admin configures the degree of human oversight: (a) humans in-the-loop (approve before AI proceeds) or (b) humans on-the-loop (review/override after AI proceeds). All three granularity levels built: per-stage approval, per-iteration approval, consumer-facing-only approval. Admin org decides which to implement.
- **D-02:** Safety alerts (critical tier from Phase 5) ALWAYS interrupt regardless of autonomy config. This is non-negotiable.

### Checkpoint Configuration (AUTONOMY-03, AUTONOMY-05)
- **D-03:** Per-stage checkpoint toggles with priority override. Admin configures checklist of analysis stages (issue_spot, explore, research, fact_map, gap_analyze, question_gen). Each stage: auto or checkpoint. Safety alerts always checkpoint regardless. Defaults: all stages auto except question_gen (checkpoint).
- **D-04:** Configurable timeout with auto-proceed option. Org sets timeout (default 30 min). Three behaviors (org chooses): (1) auto-proceed with audit note, (2) queue for next available professional, (3) pause until approval. Consumer sees "waiting for review" status.

### Mode Switching (AUTONOMY-04)
- **D-05:** Professional can escalate/de-escalate mid-intake. Mode change takes effect at next stage boundary (current stage completes first). Audit log records mode change with reason. Reversible in either direction.
- **D-06:** Dedicated "Autonomy" tab in admin settings. Shows current mode, per-stage checkpoint toggles, timeout config, auto-proceed toggle. Preview panel shows consumer experience per mode. Inherits Phase 8 admin tabbed interface.

### Professional Approval Workflow (AUTONOMY-02)
- **D-07:** Both WebSocket-pushed approval cards AND email/notification queue — org decides between one or both. Real-time: approval card in Live Intakes view with Approve/Edit/Reject buttons. Email: notification with link to approval screen.
- **D-08:** Reject re-runs stage with professional's guidance note as additional LLM context. Re-runs up to 2 times; if still rejected, stage is skipped with audit note. Professional always has final say.
- **D-09:** Edit opens inline editing of AI output before pipeline proceeds. Professional can modify proposed questions, remove claims, adjust mappings. Edits preserved in audit trail.

### Audit Trail
- **D-10:** Full decision audit with timestamps and actors. Every autonomy event logged: mode set/changed (by whom, when, reason), checkpoint reached (stage, wait start), approval/reject/edit (by whom, guidance text), auto-proceed triggered (timeout duration), stage skip (reason). All entries link to intake + analysis run. Via Phase 1 audit log system.

### Consumer Experience
- **D-11:** Mode-appropriate transparency. Chatbot mode: "AI Assistant" label on system messages. Professional/agent mode: "Legal professional is reviewing" status when waiting (NOT "attorney"). Agent mode: "Analysis paused for review" when checkpoint reached. Org configures label text per language (i18n).

### Mode-Specific Safety Behavior
- **D-12:** Both strict-chatbot AND identical-across-modes built — admin org decides. Option A (recommended default for chatbot): all critical + elevated protocols mandatory, auto-escalation for immediate danger. Option B (for professional-supervised): critical mandatory, professional can silence elevated. Agent mode follows chatbot rules when unattended, professional rules when active.

### Claude's Discretion
- Approval card component layout
- Email notification template design
- Timeout countdown UI
- Auto-proceed animation/feedback
- Audit event schema details
- Mode preview panel visualization

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Dependencies
- `.planning/phases/04-core-analysis-pipeline/04-CONTEXT.md` — AnalysisOrchestrator stages, checkpointing
- `.planning/phases/05-pre-research-exploration-safety/05-CONTEXT.md` — Three-tier safety screening, protocol activation
- `.planning/phases/08-frontend-application/08-CONTEXT.md` — Professional oversight D-31, admin UI D-11

### Existing Code
- `backend/app/services/analysis/orchestrator.py` — AnalysisOrchestrator (wrap with autonomy layer)
- `backend/app/models/analysis.py` — AnalysisRun, AnalysisStage (checkpoint records)
- `backend/app/services/screening/middleware.py` — Safety screening (integrate with mode-specific behavior)
- `backend/app/routers/analysis.py` — Analysis API (extend with approval endpoints)
- `frontend/src/features/admin/` — Admin tabs (add Autonomy tab)
- `frontend/src/features/chat/` — Chat interface (add approval cards, mode indicators)
- `backend/app/middleware/audit.py` — Audit logging (extend for autonomy events)

### Requirements
- `.planning/REQUIREMENTS.md` — AUTONOMY-01 through AUTONOMY-05

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **AnalysisOrchestrator**: Stage-based loop with checkpointing — wrap with autonomy interceptor
- **IntakeConnectionManager**: WebSocket broadcasting — use for approval push notifications
- **Phase 1 AuditMiddleware**: Audit log system — extend for autonomy events
- **Admin tabs**: Phase 8 tabbed admin — add Autonomy tab
- **Live Intakes view**: Phase 8 professional oversight — extend with approval cards

### Integration Points
- Autonomy interceptor wraps orchestrator's `_execute_stage` to check mode/checkpoint config
- Approval endpoints extend existing analysis router
- Autonomy admin tab added to existing admin interface
- Consumer-facing mode labels injected into existing chat message rendering

</code_context>

<specifics>
## Specific Ideas

- "Legal professional" (not "attorney") for professional-mode labels
- "Build both, admin decides" pattern continues from Phase 8
- Autonomy is a spectrum, not three rigid modes — the three requirement names (chatbot/professional/agent) are presets on a continuous configuration space
- Safety alerts are unconditionally non-negotiable regardless of autonomy config

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 10-autonomy-orchestration-modes*
*Context gathered: 2026-04-06*
