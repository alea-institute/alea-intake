---
phase: 05-pre-research-exploration-safety
verified: 2026-04-03T00:00:00Z
status: gaps_found
score: 9/11 must-haves verified
re_verification: false
gaps:
  - truth: "Every consumer message gets a fast keyword/pattern screening check in <50ms"
    status: failed
    reason: "intake.py calls screen_message_fast with signature mismatch: passes user_id where db_session is required. At runtime, screen_message_fast will receive an integer as its AsyncSession argument and will fail, falling into the broad except block and silently skipping all screening."
    artifacts:
      - path: "backend/app/routers/intake.py"
        issue: "Line 502-503: screen_message_fast(content, session_id=session_id, user_id=user_id) — function signature is (content, session_id, db_session, active_protocols, question_transparency). db_session receives the integer user_id."
      - path: "backend/app/services/screening/middleware.py"
        issue: "Function works correctly in isolation but is called incorrectly from intake.py."
    missing:
      - "Fix _handle_text_message in intake.py to pass db_session instead of user_id"
      - "Fix _handle_transcript_approve in intake.py (same error at line 730-731)"
      - "Fix persist_screening_event call at line 510-512: called as persist_screening_event(session_id, tp, content) but signature is (db_session, session_id, triggered, action_taken) — missing db_session, wrong arg order"
      - "Fix queue_elevated_screening call at line 514-517: called as queue_elevated_screening(session_id, [...]) but signature is (db_session, session_id, triggered_protocols)"
      - "Fix add_to_exploration_queue call at line 519-522: same db_session omission"
  - truth: "Elevated-tier triggers queue a screening event for the next conversation pause"
    status: failed
    reason: "Even if screen_message_fast were called correctly, the dispatch filtering in intake.py checks tp.get('tier') but ScreeningResult.triggered_protocols uses 'severity_tier' as the dict key. Elevated filtering at line 515-516 always produces an empty list — no ScreeningEvents are ever queued for elevated-tier triggers."
    artifacts:
      - path: "backend/app/routers/intake.py"
        issue: "Lines 509, 516, 521: dispatch checks tp.get('tier') / getattr(tp, 'tier') but triggered_protocol dicts from middleware.py use key 'severity_tier' (middleware.py line 135)"
    missing:
      - "Change all tp.get('tier') and getattr(tp, 'tier') references to 'severity_tier' in intake.py dispatch logic"
human_verification:
  - test: "Trigger DV keywords in a live intake session"
    expected: "safety_alert WebSocket message is received immediately before message_ack, containing National DV Hotline resources and 'Are you safe right now?' question"
    why_human: "Requires running the full WebSocket stack; automated tests mock the intake handler rather than invoking it end-to-end"
---

# Phase 5: Pre-Research Exploration and Safety Verification Report

**Phase Goal:** The system performs pre-research exploration using three layers (FOLIO relationships, curated screening protocols, LLM reasoning) to discover adjacent legal issues and ensure continuous safety screening throughout every conversation.
**Verified:** 2026-04-03T00:00:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Organizations can create, read, update, and delete screening protocols via admin API | VERIFIED | `backend/app/routers/screening_admin.py` — 7 endpoints at `/api/v1/admin/screening/` with `require_role(Role.ADMIN)` |
| 2 | 16 seed protocols load idempotently at startup across three severity tiers (5 Critical, 5 Elevated, 6 Advisory) | VERIFIED | `seed_protocols.py` — exactly 5/5/6 distribution confirmed; `seed_protocols_to_db` uses INSERT ON CONFLICT DO NOTHING; wired in `main.py` lifespan |
| 3 | Organizations can activate protocols as mandatory, optional, or disabled | VERIFIED | `ProtocolService.activate_protocol` validates mode in `("mandatory", "optional", "disabled")` and creates/updates `OrgProtocolActivation` |
| 4 | Organizations can pin to a specific protocol version and running intakes use the pinned version | VERIFIED | `OrgProtocolActivation.pinned_version_id` is non-nullable; `get_active_protocols` joins on `ProtocolVersion.id == act.pinned_version_id` |
| 5 | Organizations can share protocols to the community pool or keep them private | VERIFIED | `ProtocolService.list_protocols` enforces: seeds visible to all, `is_shared=True` visible to all, private protocols only visible to `owner_org_id` |
| 6 | Exploration depth (min/max rounds) and question transparency are configurable per org | VERIFIED | `ExplorationConfig` has `min_rounds`, `max_rounds`, `stability_threshold`, `question_transparency`; wired into `AnalysisConfig.exploration` |
| 7 | Exploration runs as a stage between issue_spot and research in the analysis pipeline | VERIFIED | `orchestrator.py` STAGES = `["issue_spot", "explore", "research", "fact_map", "gap_analyze", "question_gen"]`; `_get_stage_instance("explore")` returns `ExploreStage` |
| 8 | Exploration uses three layers in parallel: cheap LLM wide-net + sequential FOLIO/protocols/expensive LLM | VERIFIED | `engine.py` — `asyncio.gather(cheap_task, _sequential_pipeline())` where sequential runs FOLIO adjacency -> protocol matching -> expensive LLM |
| 9 | Exploration-discovered issues become new AnalysisClaim records with claim_type='discovered' and is_potential=True | VERIFIED | `explore.py` lines 114-130: persists `AnalysisClaim(claim_type="discovered", is_potential=True)` for each new claim |
| 10 | Every consumer message gets a fast keyword/pattern screening check in <50ms | FAILED | `intake.py` calls `screen_message_fast(content, session_id=session_id, user_id=user_id)` — wrong third argument; function requires `db_session: AsyncSession`, receives integer `user_id` |
| 11 | Elevated-tier triggers queue a screening event for the next conversation pause | FAILED | Dispatch filtering uses `tp.get("tier")` but `ScreeningResult.triggered_protocols` dicts use key `"severity_tier"` — elevated filter always produces empty list |

**Score:** 9/11 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/models/screening.py` | ScreeningProtocol, ProtocolVersion, OrgProtocolActivation, ScreeningEvent DB models | VERIFIED | All 4 models present with correct columns, TenantBase/SharedBase split |
| `backend/app/services/screening/seed_protocols.py` | 16 seed protocol definitions and idempotent DB loader | VERIFIED | SEED_PROTOCOLS list with 5/5/6 severity distribution; seed_protocols_to_db with ON CONFLICT DO NOTHING |
| `backend/app/services/screening/protocol_service.py` | Protocol CRUD, activation management, version pinning | VERIFIED | ProtocolService class with full lifecycle; visibility rules enforced |
| `backend/app/services/screening/trigger_matcher.py` | Fast keyword/regex/FOLIO-concept trigger matching | VERIFIED | Pre-compiles regex at init; match_fast runs keyword then regex then FOLIO IRI checks |
| `backend/app/services/exploration/schemas.py` | Pydantic schemas for exploration I/O and ExplorationConfig | VERIFIED | ExplorationConfig, ExplorationResult, ExplorationRoundResult, ExplorationStageResult, ScreeningResult all present |
| `backend/app/routers/screening_admin.py` | Admin CRUD endpoints for protocols and activations | VERIFIED | 7 endpoints at `/api/v1/admin/screening/` with ADMIN role guard |
| `backend/app/services/exploration/engine.py` | ExplorationEngine with three-layer parallel execution and multi-round stability | VERIFIED | asyncio.gather for parallel branches; min_rounds/max_rounds/stability_threshold loop |
| `backend/app/services/exploration/layers.py` | Layer implementations: FOLIO adjacency, protocol matching, cheap LLM, expensive LLM | VERIFIED | 4 async layer functions with graceful degradation |
| `backend/app/services/analysis/stages/explore.py` | ExploreStage following IssueSpotStage pattern | VERIFIED | Matches IssueSpotStage constructor; execute returns dict; persists AnalysisClaim |
| `backend/app/services/analysis/orchestrator.py` | Updated STAGES list with 'explore' between issue_spot and research | VERIFIED | STAGES confirmed; _get_stage_instance("explore") creates ExploreStage |
| `backend/app/services/screening/middleware.py` | screen_message_fast function and screening result handling | VERIFIED (module) | Module is substantive and correct; wiring from intake.py is broken |
| `backend/app/routers/intake.py` | Updated _handle_text_message with per-message screening hook | STUB/WIRED | Code calls screening functions but with wrong arguments — screening silently fails at runtime |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `seed_protocols.py` | `models/screening.py` | `ScreeningProtocol(` creation | WIRED | `seed_protocols_to_db` creates ScreeningProtocol + ProtocolVersion records |
| `routers/screening_admin.py` | `services/screening/protocol_service.py` | `ProtocolService` method calls | WIRED | Each endpoint instantiates `ProtocolService(session)` and calls its methods |
| `services/analysis/schemas.py` | `services/exploration/schemas.py` | `AnalysisConfig.exploration` referencing `ExplorationConfig` | WIRED | `analysis/schemas.py` imports and references `ExplorationConfig` at lines 205, 209 |
| `orchestrator.py` | `stages/explore.py` | `_get_stage_instance` creates `ExploreStage` | WIRED | Lines 510-513: `from app.services.analysis.stages.explore import ExploreStage; return ExploreStage(...)` |
| `engine.py` | `layers.py` | Engine calls layer functions in `asyncio.gather` | WIRED | engine.py imports all 4 layer functions; calls via asyncio.gather at line 240 |
| `engine.py` | `folio/concept_resolver.py` | Deduplication via `resolve_concepts` | WIRED | Lazy wrapper at line 58-62; called in `_deduplicate_results` at line 318 |
| `stages/explore.py` | `models/analysis.py` | Creates `AnalysisClaim(` records for discovered issues | WIRED | Lines 114-132: `AnalysisClaim(claim_type="discovered", is_potential=True)` with `session.add` |
| `routers/intake.py` | `services/screening/middleware.py` | `screen_message_fast` called before message processing | NOT_WIRED | Import correct; call at line 502-503 passes `user_id` where `db_session: AsyncSession` is required |
| `services/screening/middleware.py` | `services/screening/trigger_matcher.py` | `TriggerMatcher.match_fast` for keyword/regex check | WIRED | middleware.py imports and uses TriggerMatcher correctly |
| `services/screening/middleware.py` | `models/screening.py` | `ScreeningEvent(` persistence for audit trail | WIRED | `persist_screening_event` creates `ScreeningEvent` and adds to session |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|--------------------|--------|
| `stages/explore.py` | `stage_result` | `engine.explore(run, iteration, claims, facts)` | Yes — live LLM + FOLIO calls | FLOWING |
| `routers/intake.py` | `screening_result` | `screen_message_fast(content, session_id, ...)` | Would flow from TriggerMatcher | DISCONNECTED — argument mismatch causes runtime exception before any matching occurs |
| `routers/screening_admin.py` | Protocol list | `ProtocolService.list_protocols()` | DB query via SQLAlchemy select | FLOWING |

---

### Behavioral Spot-Checks

Runnable entry points require a live server — testing is limited to module import checks.

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All phase 05 tests pass | `pytest tests/test_screening_protocols.py tests/test_seed_protocols.py tests/test_exploration_engine.py tests/test_exploration_stage.py tests/test_screening_middleware.py -q` | 88 passed in 1.79s | PASS |
| screen_message_fast signature | `inspect.signature(screen_message_fast)` | `(content, session_id, db_session, active_protocols, question_transparency)` | PASS |
| intake.py screening call | `grep "screen_message_fast" intake.py` | Calls with `user_id=user_id` as third kwarg, not `db_session` | FAIL |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| EXPLORE-01 | Plan 02 | System performs pre-research exploration between issue-spotting and research phases | SATISFIED | ExploreStage in STAGES between issue_spot and research; orchestrator verified |
| EXPLORE-02 | Plan 02 | Exploration uses three layers: FOLIO ontology relationships, curated screening protocols, and LLM reasoning | SATISFIED | `layers.py` — layer_folio_adjacency, layer_protocol_match, layer_cheap_llm, layer_expensive_llm all implemented |
| EXPLORE-03 | Plan 01 | Organizations can define mandatory safety screening protocols that run before analysis proceeds | SATISFIED | `OrgProtocolActivation.activation_mode="mandatory"` enforced; get_active_protocols filters only non-disabled |
| EXPLORE-04 | Plan 03 | Safety screening is continuous throughout the conversation, not just at intake start | BLOCKED | `_handle_text_message` and `_handle_transcript_approve` have broken calls to `screen_message_fast` — screening silently fails; REQUIREMENTS.md also shows this as Pending |
| EXPLORE-05 | Plans 01, 02 | Exploration depth is configurable per organization (1 round to "until stable") | SATISFIED | ExplorationConfig.min_rounds/max_rounds/stability_threshold wired into AnalysisConfig.exploration |
| EXPLORE-06 | Plans 01, 02 | System explains why it's asking exploration questions (configurable transparency per org) | SATISFIED | ExplorationConfig.question_transparency; ExploreStage returns question_transparency flag; screening respects text_transparent variant |
| EXPLORE-07 | Plan 01 | Open screening protocol library allows community-contributed protocols across organizations | SATISFIED | ProtocolService.list_protocols returns is_seed + is_shared protocols to all orgs |
| EXPLORE-08 | Plan 01 | Organizations can create private screening protocols not shared with the library | SATISFIED | Private protocols (owner_org_id set, is_shared=False) only returned to owning org in list_protocols |
| EXPLORE-09 | Plans 01, 03 | Default DV screening protocol ships with the system for family law matters | SATISFIED | slug="dv-ipv", severity_tier="critical", keywords include "domestic violence", area_of_law_iris=[] (universal per D-11), National DV Hotline in escalation_actions |
| EXPLORE-10 | Plans 02, 03 | Exploration can surface entirely new legal issues not in the initial issue-spotting (e.g., DV in custody cases) | SATISFIED | ExploreStage persists AnalysisClaim(claim_type="discovered", is_potential=True) for each new issue from all three layers |

**Orphaned requirements check:** REQUIREMENTS.md maps all 10 EXPLORE requirements to Phase 5. Plans 01–03 collectively claim all 10 IDs. No orphaned requirements.

**Note:** REQUIREMENTS.md marks EXPLORE-04 with `[ ]` (Pending) and status "Pending" at line 174, consistent with the gap found above.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/app/routers/intake.py` | 502–503 | `screen_message_fast(content, session_id=session_id, user_id=user_id)` — wrong third argument | Blocker | screening silently fails for every message; EXPLORE-04 not satisfied at runtime |
| `backend/app/routers/intake.py` | 510–512 | `persist_screening_event(session_id, tp, content)` — missing db_session, wrong argument order | Blocker | ScreeningEvent audit records never created for critical triggers |
| `backend/app/routers/intake.py` | 514–517 | `queue_elevated_screening(session_id, [...])` — missing db_session | Blocker | No ScreeningEvent queued for elevated triggers |
| `backend/app/routers/intake.py` | 519–522 | `add_to_exploration_queue(session_id, [...])` — missing db_session | Blocker | No exploration queue entry for advisory triggers |
| `backend/app/routers/intake.py` | 509, 516, 521 | Dispatch filters check `tp.get("tier")` but dict key is `"severity_tier"` | Blocker | Elevated and advisory dispatch lists always empty even if prior fixes applied |
| `backend/app/routers/screening_admin.py` | 79 | `owner_org_id=None` hardcoded in create_protocol | Warning | New org protocols created without org ownership; mitigated by comment noting production fix needed |

---

### Human Verification Required

#### 1. End-to-end DV keyword safety alert

**Test:** In a running intake session, send a text message containing "I'm afraid my husband will hurt me."
**Expected:** Client receives a `safety_alert` WebSocket message containing National DV Hotline resources and the "Are you safe right now?" mandatory question, followed by the normal `message_ack`.
**Why human:** Requires a live WebSocket server with DB and active protocol activations; automated tests mock the WebSocket and do not exercise the full intake.py path.

#### 2. Exploration stage fires between issue_spot and research

**Test:** Trigger an analysis run to completion and inspect the `analysis_stages` table.
**Expected:** A row with `stage_name="explore"` appears between `stage_name="issue_spot"` and `stage_name="research"` for the same iteration.
**Why human:** Requires a complete analysis pipeline run with valid LLM credentials and DB state.

---

### Gaps Summary

Two blocker gaps prevent full goal achievement for the continuous safety screening component (EXPLORE-04).

**Gap 1 — Broken function call signatures in intake.py (Root cause)**

The `_handle_text_message` and `_handle_transcript_approve` handlers in `intake.py` import and call `screen_message_fast`, `persist_screening_event`, `queue_elevated_screening`, and `add_to_exploration_queue` with incorrect arguments. The `db_session: AsyncSession` parameter is absent from every call site; `screen_message_fast` receives `user_id` as its third positional argument instead. All four calls will raise `TypeError` or silently produce wrong behavior, which the surrounding `except Exception` block swallows. The effect: safety screening is wired at the call site but dead at runtime.

**Gap 2 — Wrong dict key in priority dispatch filtering**

The dispatch code that separates triggered protocols by severity tier uses `tp.get("tier")` and `getattr(tp, "tier")`, but `ScreeningResult.triggered_protocols` dicts are constructed in `middleware.py` with key `"severity_tier"` (line 135). Even after fixing Gap 1, elevated and advisory event persistence would silently receive empty lists, meaning only critical-tier events are handled (and only because `has_critical` is a boolean flag, not derived from the filtered list).

Both gaps share a root cause: the intake.py integration code was written against a different or earlier version of the middleware function signatures and ScreeningResult schema, and the integration tests use mocks rather than the real intake handler, so the mismatch was not caught by the test suite.

**Exploration pipeline (Truths 7–9) is fully verified.** The three-layer engine, orchestrator integration, and AnalysisClaim persistence are correct, substantive, and properly wired.

---

_Verified: 2026-04-03T00:00:00Z_
_Verifier: Claude (gsd-verifier)_
