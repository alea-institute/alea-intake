---
phase: 04-core-analysis-pipeline
verified: 2026-04-04T15:45:34Z
status: passed
score: 22/22 must-haves verified
re_verification: false
---

# Phase 4: Core Analysis Pipeline Verification Report

**Phase Goal:** The system performs iterative analysis -- issue-spotting, fact-to-claim mapping, gap analysis, follow-up questioning, and convergence detection -- producing a complete mapping of consumer facts to legal claims, elements, and identified gaps
**Verified:** 2026-04-04T15:45:34Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|---------|
| 1  | Analysis state models exist and can be created in the DB | VERIFIED | 8 models in analysis.py, all inherit TenantBase, 12 model creation tests pass |
| 2  | FactClaimMapping links facts to claims/elements with composite confidence | VERIFIED | llm_confidence, concept_confidence, fact_confidence, confidence columns present; 7 fact_map tests pass |
| 3  | AnalysisGap has four gap types and FollowUpQuestion has topic grouping | VERIFIED | gap_type field present; topic_group field present; test_four_gap_types passes |
| 4  | Org-configurable analysis settings extend OrganizationConfig | VERIFIED | analysis_config_json column added to OrganizationConfig |
| 5  | Pydantic schemas define LLM I/O contracts for all stages | VERIFIED | 15 classes in schemas.py, all key classes present, 32 schema tests pass |
| 6  | ConvergenceEvaluator returns (converged, score) from five weighted signals | VERIFIED | evaluate() implemented with 5 signals, spot-check confirms output (0.9 signals → converged=True, score=0.92) |
| 7  | Hard iteration cap always terminates regardless of other signals | VERIFIED | test_hard_cap_exact and test_hard_cap_exceeded pass |
| 8  | Org-configurable weights override defaults and change convergence behavior | VERIFIED | from_org_config() classmethod implemented, test_from_org_config_with_weights passes |
| 9  | Composite confidence scoring combines LLM, concept, and fact confidence | VERIFIED | compute_composite_confidence(0.8, 0.6, 0.9) = 0.77 confirmed via spot-check |
| 10 | Hysteresis prevents oscillation once convergence threshold is crossed | VERIFIED | hysteresis logic implemented, test_hysteresis_sticky_convergence passes |
| 11 | Issue-spotting stage identifies legal claims from extracted facts via LLM | VERIFIED | IssueSpotStage.execute() exists, 7 issue_spot tests pass including LLM mock |
| 12 | Issue-spotting detects multiple jurisdictions for parallel analysis | VERIFIED | test_issue_spot_multiple_jurisdictions passes; jurisdictions returned in result |
| 13 | Discovered claims are marked as potential with rationale | VERIFIED | is_potential=spotted.is_potential persisted; test_issue_spot_discovered_claims_are_potential passes |
| 14 | Fact-mapping stage creates many-to-many FactClaimMapping records with composite confidence | VERIFIED | FactMapStage calls compute_composite_confidence; test_fact_map_many_to_many passes |
| 15 | Gap analysis detects all four gap types from analysis state | VERIFIED | unsupported_element, unexplored_claim, weak_mapping, procedural_requirement all implemented; 9 gap tests pass |
| 16 | Gaps are prioritized by impact | VERIFIED | test_gap_priority_ordering passes; priority calculation based on claim confidence |
| 17 | Follow-up questions are consumer-friendly and grouped by topic | VERIFIED | topic_group field used; test_question_topic_grouping passes |
| 18 | Question rationale included when org transparency enabled | VERIFIED | question_transparency toggle implemented; test_question_transparency_enabled/disabled both pass |
| 19 | All gaps result in questions; remaining gaps carry to next iteration | VERIFIED | test_all_gaps_produce_questions passes |
| 20 | AnalysisOrchestrator runs the full iterative loop with checkpoints | VERIFIED | orchestrator.py implements run(), _run_iteration(), _execute_stage() with AnalysisStage checkpoints |
| 21 | Analysis trigger fires automatically on fact threshold and manually | VERIFIED | AnalysisTrigger.check_auto_trigger() and manual_trigger() implemented; 7 trigger tests pass |
| 22 | Full REST API wired into main.py for trigger, status, results, override, audit | VERIFIED | 5 endpoints at /api/v1/analysis, router registered in main.py |

**Score:** 22/22 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/models/analysis.py` | All 8 analysis DB models | VERIFIED | 8 classes inheriting TenantBase; 335+ lines |
| `backend/app/services/analysis/schemas.py` | 15 Pydantic schemas for LLM I/O | VERIFIED | Exactly 15 classes, all key names present |
| `backend/app/services/analysis/convergence.py` | ConvergenceEvaluator with multi-signal logic | VERIFIED | Class + evaluate() + from_org_config() + hysteresis |
| `backend/app/services/analysis/scoring.py` | compute_composite_confidence | VERIFIED | Function + get_confidence_weights helper |
| `backend/app/services/analysis/stages/issue_spot.py` | IssueSpotStage | VERIFIED | Class + execute() + ConceptResolver wiring + is_potential |
| `backend/app/services/analysis/stages/fact_map.py` | FactMapStage | VERIFIED | Class + compute_composite_confidence call + DB persistence |
| `backend/app/services/analysis/stages/research_stub.py` | ResearchStubStage (Phase 6 placeholder) | VERIFIED | Class + FOLIO adjacency logic + graceful fallback — intentional Phase 6 stub per plan |
| `backend/app/services/analysis/stages/gap_analyze.py` | GapAnalyzeStage | VERIFIED | 249 lines; all 4 gap types + coverage_pct |
| `backend/app/services/analysis/stages/question_gen.py` | QuestionGenStage | VERIFIED | 166 lines; topic_group + question_transparency + FollowUpQuestion persistence |
| `backend/app/services/analysis/orchestrator.py` | AnalysisOrchestrator | VERIFIED | run() + resume() + override_convergence() + asyncio.gather + audit_json |
| `backend/app/services/analysis/trigger.py` | AnalysisTrigger | VERIFIED | check_auto_trigger() + manual_trigger() + _is_analysis_running() |
| `backend/app/routers/analysis.py` | REST endpoints | VERIFIED | 5 endpoints; router prefix /api/v1/analysis |
| `backend/app/models/organization.py` | analysis_config_json column | VERIFIED | JSON nullable column added |
| `backend/app/models/__init__.py` | All 8 models re-exported | VERIFIED | All 8 model names in imports and __all__ |
| `backend/tests/test_analysis_models.py` | 12 model creation tests | VERIFIED | 12 tests, all pass |
| `backend/tests/test_analysis_schemas.py` | Schema validation tests | VERIFIED | 32 tests, all pass |
| `backend/tests/test_convergence.py` | Convergence tests (≥8) | VERIFIED | 14 tests, all pass |
| `backend/tests/test_scoring.py` | Scoring tests (≥5) | VERIFIED | 13 tests (exceeds requirement), all pass |
| `backend/tests/test_analysis_stages.py` | Stage tests (≥10 total) | VERIFIED | 16 tests, all pass |
| `backend/tests/test_gap_analysis.py` | Gap + question tests (≥10 total) | VERIFIED | 17 tests, all pass |
| `backend/tests/test_analysis_orchestrator.py` | Orchestrator tests | VERIFIED | 7 tests, all pass |
| `backend/tests/test_analysis_trigger.py` | Trigger + API tests | VERIFIED | 7 tests, all pass |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `convergence.py` | `schemas.py` | `ConvergenceSignals, ConvergenceWeights` imports | WIRED | `from app.services.analysis.schemas import ConvergenceSignals, ConvergenceWeights` confirmed |
| `scoring.py` | `schemas.py` | `ConfidenceWeights` import | WIRED | `from app.services.analysis.schemas import ConfidenceWeights` confirmed |
| `issue_spot.py` | `llm_service.py` | LLMService for structured output | WIRED | `LLMService` referenced in stage constructor and execute() |
| `issue_spot.py` | `folio/concept_resolver.py` | `resolve_concepts` call | WIRED | `from app.services.folio.concept_resolver import resolve_concepts` called per claim |
| `fact_map.py` | `scoring.py` | `compute_composite_confidence` | WIRED | `from app.services.analysis.scoring import compute_composite_confidence` confirmed |
| `gap_analyze.py` | `models/analysis.py` | `AnalysisGap` persistence | WIRED | `AnalysisGap(...)` creation in all 4 gap type paths |
| `question_gen.py` | `models/analysis.py` | `FollowUpQuestion` persistence | WIRED | `FollowUpQuestion(...)` creation confirmed |
| `question_gen.py` | `llm_service.py` | LLM generates questions | WIRED | `LLMService` in constructor + execute() |
| `orchestrator.py` | `stages/issue_spot.py` | `IssueSpotStage.execute()` | WIRED | Dynamic import + instantiation in `_create_stage()` |
| `orchestrator.py` | `stages/gap_analyze.py` | `GapAnalyzeStage.execute()` | WIRED | Dynamic import + instantiation confirmed |
| `orchestrator.py` | `convergence.py` | `ConvergenceEvaluator.evaluate()` | WIRED | `from app.services.analysis.convergence import ConvergenceEvaluator` at module level |
| `trigger.py` | `orchestrator.py` | `AnalysisOrchestrator.run()` | WIRED | `from app.services.analysis.orchestrator import AnalysisOrchestrator` confirmed |
| `routers/analysis.py` | `trigger.py` | `AnalysisTrigger.trigger()` | WIRED | `AnalysisTrigger(db_session=db, orchestrator=orchestrator)` in trigger_analysis endpoint |
| `main.py` | `routers/analysis.py` | Router registration | WIRED | `from app.routers.analysis import router as analysis_router` + `app.include_router(analysis_router)` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `orchestrator.py` | `claims` (loaded from DB) | `_load_claims()` → `select(AnalysisClaim).where(...)` | Yes — DB query | FLOWING |
| `orchestrator.py` | `facts` (loaded from DB) | `select(ExtractedFact).where(...)` | Yes — DB query | FLOWING |
| `gap_analyze.py` | `AnalysisGap` records | Direct DB insertion from computed gap logic | Yes — persisted | FLOWING |
| `question_gen.py` | `FollowUpQuestion` records | LLM output parsed through QuestionGenResult schema | Yes — LLM + DB | FLOWING |
| `routers/analysis.py` | `audit_json` in GET /audit | `select(AnalysisStage).where(...)` → stage.audit_json | Yes — DB query | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All key modules import cleanly | `python -c "from app.services.analysis.schemas import OrchestratorDecision..."` | `ALL IMPORTS OK` | PASS |
| Router prefix registered | `router.prefix` | `/api/v1/analysis` | PASS |
| ConvergenceEvaluator produces expected convergence | High-signal evaluation | `Converged: True, Score: 0.92` | PASS |
| Composite confidence math correct | `compute_composite_confidence(0.8, 0.6, 0.9)` | `0.77` (matches 0.8×0.4 + 0.6×0.3 + 0.9×0.3) | PASS |
| Full test suite runs without regressions | `pytest --tb=short -q` | `418 passed, 3 skipped, 19 warnings` | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| ANALYSIS-01 | Plans 03, 05 | Iterative analysis loop | SATISFIED | AnalysisOrchestrator.run() executes issue-spot → research → fact-map → gap-analyze → question loop; 7 orchestrator tests pass |
| ANALYSIS-02 | Plan 01, 03 | Many-to-many fact-to-claim mapping with confidence | SATISFIED | FactClaimMapping model + FactMapStage; 7 fact_map tests pass |
| ANALYSIS-03 | Plan 04 | Identify gaps (4 types) | SATISFIED | GapAnalyzeStage detects unsupported_element, unexplored_claim, weak_mapping, procedural_requirement; 9 gap tests pass |
| ANALYSIS-04 | Plan 04 | Prioritized consumer-friendly follow-up questions | SATISFIED | QuestionGenStage generates ranked questions via LLM; test_question_priority_ordering passes |
| ANALYSIS-05 | Plan 04 | Questions grouped by topic | SATISFIED | topic_group field; test_question_topic_grouping passes |
| ANALYSIS-06 | Plan 02 | Multi-signal loop termination | SATISFIED | 5 signals in ConvergenceEvaluator.evaluate(); 14 convergence tests pass |
| ANALYSIS-07 | Plans 01, 02 | Configurable weights/thresholds per org | SATISFIED | ConvergenceWeights + ConfidenceWeights + AnalysisConfig in schemas; from_org_config() classmethod |
| ANALYSIS-08 | Plan 03, 05 | Parallel multi-jurisdictional analysis | SATISFIED | asyncio.gather in _run_parallel_jurisdictions(); test_issue_spot_multiple_jurisdictions passes |
| ANALYSIS-09 | Plans 01, 05 | Checkpointed state for pause/resume | SATISFIED | AnalysisStage records created after every stage; orchestrator.resume() loads latest checkpoint |
| ANALYSIS-10 | Plans 01, 05 | Full audit trail per stage | SATISFIED | audit_json populated with stage_name, input_fact_count, claims_produced, sources_consulted, confidence_scores_summary, duration_ms; GET /audit endpoint |

**REQUIREMENTS.md discrepancy (documentation gap, not a code gap):** REQUIREMENTS.md marks ANALYSIS-03, ANALYSIS-04, ANALYSIS-05 as `[ ] Pending` and in the traceability table as "Pending". However, the implementation is complete — GapAnalyzeStage (249 lines) and QuestionGenStage (166 lines) are fully implemented with 17 passing tests. The REQUIREMENTS.md checkboxes and traceability table were not updated after implementation. This is a documentation maintenance issue only.

### Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| `stages/research_stub.py` | Module is named "stub" and deferred to Phase 6 | Info | Intentional — per plan design. Real FOLIO adjacency logic implemented. Phase 6 replaces with full research tools. Not a code quality issue. |
| `orchestrator.py` lines 633, 644 | `return []` | Info | Guard clauses for empty input to `_load_elements()` and `_load_mappings()` — not stubs. Correct defensive logic. |

No blockers or warnings found.

### Human Verification Required

#### 1. WebSocket Progress Broadcasting Under Load

**Test:** Start an analysis run via `POST /api/v1/analysis/{intake_id}/analyze`, connect a WebSocket client to the session endpoint, and observe stage-by-stage progress events.
**Expected:** WebSocket receives a JSON message after each stage completes containing the stage name and run state.
**Why human:** Cannot test without a running server and active WebSocket connection. The wiring (`send_to_session` calls verified in code), but live message delivery requires integration testing.

#### 2. Parallel Jurisdiction Execution Timing

**Test:** Submit a narrative that describes facts spanning two jurisdictions (e.g., employment dispute involving both California and federal law). Verify that fact-map and gap-analyze stages run concurrently for each jurisdiction.
**Expected:** AnalysisStage records show two jurisdiction-labeled fact-map and gap-analyze checkpoints created with overlapping timestamps.
**Why human:** asyncio.gather concurrency cannot be verified by inspection alone — requires live run with DB timestamp comparison.

#### 3. End-to-End Iterative Loop Convergence

**Test:** Run a complete analysis against a seeded intake with 5+ extracted facts and observe the loop terminate via convergence (not hard cap).
**Expected:** AnalysisRun.convergence_score rises across iterations and terminates with status="completed" and convergence_score >= 0.75 before reaching max_iterations.
**Why human:** Multi-iteration behavior requires a full running environment with real LLM calls or a realistic mock sequence.

### Gaps Summary

No gaps found. All 22 observable truths are verified, all artifacts exist and are substantive, all key links are wired, and all 418 tests pass. The only items flagged for human verification are runtime behaviors that cannot be confirmed statically.

The sole documentation artifact requiring attention is the REQUIREMENTS.md file, which still marks ANALYSIS-03, ANALYSIS-04, and ANALYSIS-05 as pending. The code implementing these requirements is complete and tested. REQUIREMENTS.md should be updated to mark these as complete (`[x]`) and "Complete" in the traceability table.

---

_Verified: 2026-04-04T15:45:34Z_
_Verifier: Claude (gsd-verifier)_
