---
phase: 07-output-export
plan: 02
subsystem: output
tags: [jinja2, triage-scoring, action-items, language-adaptation, cirac, templates]

# Dependency graph
requires:
  - phase: 07-output-export
    provides: OutputContext, CIRACSection, TriageResult, ActionItem, GapReport schemas; DataAssembler; GapReportBuilder
provides:
  - TriageScorer with 4-factor weighted routing recommendations
  - ActionItemGenerator with gap-type-to-category mapping and priority classification
  - TemplateEngine rendering OutputContext through 4 Jinja2 templates per profile
  - LanguageAdapter for LLM-driven language complexity adaptation preserving citations
  - 4 Jinja2 templates (CIRAC memo, triage report, action items, gap appendix)
affects: [07-output-export, 08-frontend-output]

# Tech tracking
tech-stack:
  added: []
  patterns: [jinja2-template-rendering, profile-based-section-visibility, multi-factor-triage-scoring, gap-to-action-item-transformation]

key-files:
  created:
    - backend/app/services/output/triage_scorer.py
    - backend/app/services/output/action_item_generator.py
    - backend/app/services/output/template_engine.py
    - backend/app/services/output/language_adapter.py
    - backend/app/services/output/templates/cirac_memo.md.j2
    - backend/app/services/output/templates/triage_report.md.j2
    - backend/app/services/output/templates/action_items.md.j2
    - backend/app/services/output/templates/gap_appendix.md.j2
    - backend/tests/test_output_triage.py
    - backend/tests/test_output_templates.py
  modified:
    - backend/app/services/output/__init__.py

key-decisions:
  - "TriageScorer weights: practice_area=0.35, jurisdiction=0.25, complexity=0.20, org_rules=0.20"
  - "Complexity thresholds: high if >5 claims or >10 gaps, low if <=2 claims and <=3 gaps"
  - "Urgency thresholds: emergency if priority>=9, urgent if >=7, routine otherwise"
  - "Referral generation triggers at completeness < 0.3 with >= 3 gaps in a practice area"
  - "LanguageAdapter._rewrite_text is the LLM integration point; stubbed for now, wired when orchestrator connects"

patterns-established:
  - "Jinja2 FileSystemLoader with trim_blocks/lstrip_blocks for clean Markdown output"
  - "Profile-based section visibility via OutputProfile.sections dict controlling render_full"
  - "Gap-type-to-category mapping: unsupported_element/weak_mapping -> documents_to_gather, unexplored_claim/procedural_requirement -> follow_up_steps"
  - "Citation preservation: extract before LLM rewrite, verify after, authorities never rewritten"

requirements-completed: [OUTPUT-01, OUTPUT-02, OUTPUT-03, OUTPUT-05]

# Metrics
duration: 6min
completed: 2026-04-05
---

# Phase 7 Plan 2: Content Generation & Rendering Summary

**TriageScorer with 4-factor routing, ActionItemGenerator with gap-to-action mapping, Jinja2 TemplateEngine with CIRAC/triage/action/gap templates, and LanguageAdapter for LLM-driven language complexity adaptation per profile**

## Performance

- **Duration:** 6 min
- **Started:** 2026-04-05T02:26:44Z
- **Completed:** 2026-04-05T02:33:00Z
- **Tasks:** 2
- **Files modified:** 11

## Accomplishments
- TriageScorer produces ranked routing recommendations with 4-factor weighted scoring (practice area, jurisdiction, complexity, org rules) per D-02
- ActionItemGenerator transforms gaps into prioritized, categorized action items with cross-linking back to source GapEntry per D-03
- TemplateEngine renders OutputContext through 4 Jinja2 templates with profile-controlled section visibility per D-01/D-04
- CIRAC memo template uses proper heading hierarchy (H1 title, H2 jurisdiction, H3 claim, H4 Issue/Rule/Application/Conclusion) with binding strength and verification indicators
- LanguageAdapter preserves citation strings verbatim during LLM-driven language adaptation per D-05

## Task Commits

Each task was committed atomically:

1. **Task 1: TriageScorer and ActionItemGenerator services** - `fa64e2c` (test) + `3b2ca6d` (feat)
2. **Task 2: TemplateEngine, Jinja2 templates, and LanguageAdapter** - `41caf8e` (test) + `8a5b1ed` (feat)

_Note: TDD tasks have separate test (RED) and implementation (GREEN) commits._

## Files Created/Modified
- `backend/app/services/output/triage_scorer.py` - Multi-factor triage scoring with 4-factor weighted recommendations
- `backend/app/services/output/action_item_generator.py` - Gap-to-action-item transformation with prioritization and categorization
- `backend/app/services/output/template_engine.py` - Jinja2 template engine with profile-based section visibility
- `backend/app/services/output/language_adapter.py` - LLM-driven language complexity adaptation preserving citations
- `backend/app/services/output/templates/cirac_memo.md.j2` - CIRAC format case memo with jurisdiction grouping
- `backend/app/services/output/templates/triage_report.md.j2` - Triage & routing recommendations with score tables
- `backend/app/services/output/templates/action_items.md.j2` - Category-grouped action checklist with priority indicators
- `backend/app/services/output/templates/gap_appendix.md.j2` - Per-claim gap report with completeness bar
- `backend/app/services/output/__init__.py` - Updated re-exports for all 4 new services
- `backend/tests/test_output_triage.py` - 22 tests for TriageScorer and ActionItemGenerator
- `backend/tests/test_output_templates.py` - 17 tests for TemplateEngine and LanguageAdapter

## Decisions Made
- TriageScorer weights: practice_area=0.35, jurisdiction=0.25, complexity=0.20, org_rules=0.20 (from plan spec, covers all D-02 factors)
- Complexity: high if >5 claims or >10 gaps, low if <=2 claims and <=3 gaps (clear thresholds from plan)
- Urgency: emergency if any gap priority >= 9, urgent >= 7, routine otherwise (escalation ladder)
- Referral generation triggers at completeness < 0.3 with >= 3 gaps in a practice area (conservative threshold)
- LanguageAdapter._rewrite_text is the LLM integration point; returns text as-is for now, actual LLM wiring happens when orchestrator connects all services

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- MagicMock `hasattr` always returns True for any attribute, causing test assertion failure for "LLM not called" check. Fixed by using `patch.object` with `assert_not_called()` instead.

## Known Stubs

- `LanguageAdapter._rewrite_text()` in `backend/app/services/output/language_adapter.py` (line 116): Returns original text unchanged. This is intentional -- actual LLM call wiring happens when the orchestrator connects services end-to-end. The interface and citation-preservation logic are complete; only the LLM call itself is deferred.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- All 4 services (TriageScorer, ActionItemGenerator, TemplateEngine, LanguageAdapter) ready for Plan 03 integration
- Plan 03 builds the export adapters (PDF/DOCX/JSON) and API endpoints on top of this rendering layer
- TemplateEngine produces Markdown that Plan 03's exporters will convert to final formats
- LanguageAdapter ready for LLM wiring when orchestrator connects the full pipeline

## Self-Check: PASSED

- All 10 created files verified present on disk
- All 4 commit hashes verified in git log
- 39/39 tests passing

---
*Phase: 07-output-export*
*Completed: 2026-04-05*
