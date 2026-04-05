---
phase: 07-output-export
plan: 01
subsystem: output
tags: [pydantic, sqlalchemy, cirac, gap-analysis, output-profiles]

# Dependency graph
requires:
  - phase: 04-core-analysis-pipeline
    provides: AnalysisClaim, ClaimElement, FactClaimMapping, AnalysisGap, FollowUpQuestion models
  - phase: 06-legal-research-verification
    provides: Authority model with citation verification and binding strength
provides:
  - OutputContext unified data structure for rendering
  - CIRACSection per-claim CIRAC-format section model
  - OutputProfile with three built-in profile constants (law_firm, legal_aid, court_self_help)
  - DataAssembler service loading all upstream data into OutputContext
  - GapReportBuilder for inline + appendix gap analysis
  - OutputDocument DB model for persisting rendered output
  - OrgBranding and per-org output configuration
affects: [07-output-export, 08-frontend-output]

# Tech tracking
tech-stack:
  added: []
  patterns: [format-neutral data contracts, binding-strength authority ordering, jurisdiction grouping]

key-files:
  created:
    - backend/app/services/output/schemas.py
    - backend/app/services/output/data_assembler.py
    - backend/app/services/output/gap_report_builder.py
    - backend/app/models/output.py
    - backend/tests/test_output_schemas.py
    - backend/tests/test_output_data_assembler.py
  modified:
    - backend/app/models/organization.py
    - backend/app/models/__init__.py

key-decisions:
  - "Binding strength classification: statutes/regulations/constitutional/rules = binding, case_law = persuasive, secondary = secondary"
  - "Claims with jurisdiction=None grouped under 'General' key in claims_by_jurisdiction"
  - "Module-level model imports in test file to ensure table registration before async_engine fixture"

patterns-established:
  - "Format-neutral OutputContext: all rendering derives from this single Pydantic model"
  - "Authority ordering: binding_strength priority (binding=0, persuasive=1, secondary=2) then relevance_score desc"
  - "GapReportBuilder as static method accepting raw data, no DB dependency"

requirements-completed: [OUTPUT-01, OUTPUT-04, OUTPUT-05]

# Metrics
duration: 6min
completed: 2026-04-05
---

# Phase 7 Plan 1: Output Data Layer Summary

**Format-neutral Pydantic data contracts (OutputContext, CIRACSection, OutputProfile) with DataAssembler querying all upstream analysis/research into unified output and GapReportBuilder for inline+appendix gap analysis**

## Performance

- **Duration:** 6 min
- **Started:** 2026-04-05T02:18:28Z
- **Completed:** 2026-04-05T02:24:30Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments
- OutputContext schema captures full analysis/research graph (claims, elements, mappings, gaps, authorities, facts) in format-neutral Pydantic model
- Three built-in OutputProfile defaults (law_firm, legal_aid, court_self_help) with section visibility and language level controls matching D-04 specification
- DataAssembler loads all upstream data into OutputContext grouped by jurisdiction with authorities sorted by binding strength
- GapReportBuilder produces per-claim inline gaps and consolidated Gap Report Appendix with completeness score

## Task Commits

Each task was committed atomically:

1. **Task 1: Output Pydantic schemas, OutputDocument DB model, and OutputProfile configuration** - `3238553` (feat)
2. **Task 2: DataAssembler and GapReportBuilder services** - `cbcf512` (feat)

## Files Created/Modified
- `backend/app/services/output/schemas.py` - 13 Pydantic models + 3 profile constants for format-neutral output data contracts
- `backend/app/services/output/data_assembler.py` - DataAssembler service querying all upstream analysis/research models into OutputContext
- `backend/app/services/output/gap_report_builder.py` - GapReportBuilder for per-claim and consolidated gap analysis
- `backend/app/services/output/__init__.py` - Output service package init
- `backend/app/models/output.py` - OutputDocument DB model with markdown, PDF, DOCX, JSON columns
- `backend/app/models/organization.py` - Added output_config_json JSON column to OrganizationConfig
- `backend/app/models/__init__.py` - Added OutputDocument re-export
- `backend/tests/test_output_schemas.py` - 14 tests for schemas, profiles, DB model, branding
- `backend/tests/test_output_data_assembler.py` - 12 tests for DataAssembler and GapReportBuilder

## Decisions Made
- Binding strength classification: statutes/regulations/constitutional/rules = binding, case_law = persuasive, secondary = secondary (simplified heuristic; real implementation would check court hierarchy)
- Claims with jurisdiction=None grouped under "General" key in claims_by_jurisdiction dict
- Module-level model imports in test file to ensure Intake/ExtractedFact tables are registered with TenantBase metadata before async_engine fixture creates tables

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Table registration ordering: Intake and ExtractedFact models were not re-exported from `models/__init__.py`, so they weren't registered with TenantBase metadata when the conftest async_engine fixture created tables. Fixed by adding explicit module-level imports in the test file (consistent with other test files that use these models).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- OutputContext schema ready for Plan 02 (Markdown template rendering + LLM language adaptation)
- DataAssembler provides the "data in" layer; Plan 02 builds the "render" layer on top
- GapReportBuilder output feeds directly into template rendering for gap appendix
- OutputDocument model ready to persist rendered output from Plan 02/03

---
*Phase: 07-output-export*
*Completed: 2026-04-05*
