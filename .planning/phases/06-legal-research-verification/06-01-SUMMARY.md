---
phase: 06-legal-research-verification
plan: 01
subsystem: api
tags: [research, courtlistener, citation-verification, adapter-pattern, httpx]

requires:
  - phase: 01-foundation-security
    provides: "Auth, RBAC, tenant isolation, encryption, DB engine"
  - phase: 02-folio-ontology-integration
    provides: "FOLIO concept IRIs for linking authorities to claims"
provides:
  - "Pluggable research tool adapter ABC (ResearchAdapter)"
  - "ResearchToolRegistry singleton for adapter management and query dispatch"
  - "CourtListener REST API v4 adapter with search and citation lookup"
  - "CitationVerifier for ground-truth LLM citation checking"
  - "Authority, ResearchResult, ResearchToolConfig, CitationVerification DB models"
  - "Research API endpoints (query, verify, list/configure tools)"
affects: [06-legal-research-verification, 07-output-export, 10-autonomy-orchestration]

tech-stack:
  added: [httpx (async HTTP for CourtListener API)]
  patterns: [adapter pattern with ABC + registry singleton, citation verification pipeline, per-org tool configuration]

key-files:
  created:
    - backend/app/services/research/base.py
    - backend/app/services/research/registry.py
    - backend/app/services/research/courtlistener.py
    - backend/app/services/research/verification.py
    - backend/app/services/research/__init__.py
    - backend/app/models/research.py
    - backend/app/schemas/research.py
    - backend/app/routers/research.py
    - backend/tests/test_research.py
  modified:
    - backend/app/models/__init__.py
    - backend/app/config.py
    - backend/app/main.py

key-decisions:
  - "ResearchAdapter ABC uses async discover/fetch/verify contract for uniform tool integration"
  - "ResearchToolRegistry is a singleton with query_all for multi-tool dispatch and deduplication"
  - "CourtListener uses httpx.AsyncClient with context manager for proper connection lifecycle"
  - "CitationVerifier tries each registered tool in sequence until one confirms the citation"
  - "Per-org tool config stores encrypted API keys using existing LargeBinary pattern"
  - "Registry wired into app lifespan alongside FOLIO and embedding services"

patterns-established:
  - "Pluggable adapter pattern: ABC -> Registry -> concrete adapters for external service integration"
  - "Citation verification: verify-before-present pipeline for LLM-suggested authorities"
  - "Per-org tool configuration: ResearchToolConfig model in tenant schema"

requirements-completed: [RESEARCH-01, RESEARCH-02, RESEARCH-05, RESEARCH-06, RESEARCH-07, RESEARCH-08]

duration: 7min
completed: 2026-04-04
---

# Phase 6 Plan 01: Research Tool Adapter Framework and Citation Verification Summary

**Pluggable research adapter pattern with CourtListener v4 integration, citation verification pipeline, and per-org tool configuration**

## Performance

- **Duration:** 7 min
- **Started:** 2026-04-04T22:47:00Z
- **Completed:** 2026-04-04T22:54:00Z
- **Tasks:** 3
- **Files modified:** 12

## Accomplishments
- Pluggable research tool infrastructure with abstract adapter, singleton registry, and query dispatch/dedup
- CourtListener REST API v4 adapter for US case law search and citation lookup
- Citation verification service enforcing ground-truth checks before presenting LLM-suggested authorities
- Per-org research tool configuration with encrypted API keys and enabled/disabled state
- 34 passing tests covering models, ABC contract, registry, mocked HTTP, verification, schemas

## Task Commits

Each task was committed atomically:

1. **Task 1: Research DB models, schemas, and config settings** - `4c64931` (feat)
2. **Task 2: Research adapter ABC, registry, and CourtListener adapter** - `b478cf1` (feat)
3. **Task 3: Research API endpoints and test suite** - `4853b1f` (feat)

## Files Created/Modified
- `backend/app/services/research/base.py` - ResearchAdapter ABC, ResearchQuery, ResearchResult dataclasses
- `backend/app/services/research/registry.py` - ResearchToolRegistry singleton with query dispatch and dedup
- `backend/app/services/research/courtlistener.py` - CourtListener REST API v4 adapter
- `backend/app/services/research/verification.py` - CitationVerifier with batch and persist-to-DB support
- `backend/app/services/research/__init__.py` - Package re-exports
- `backend/app/models/research.py` - Authority, ResearchResult, ResearchToolConfig, CitationVerification models
- `backend/app/schemas/research.py` - Pydantic request/response schemas
- `backend/app/routers/research.py` - Research API endpoints (query, verify, list/configure tools)
- `backend/app/models/__init__.py` - Added research model re-exports
- `backend/app/config.py` - Added courtlistener_base_url, research_timeout, max_results settings
- `backend/app/main.py` - Registered research router and wired registry into lifespan
- `backend/tests/test_research.py` - 34 tests for full coverage

## Decisions Made
- **ResearchAdapter ABC** uses async discover/fetch/verify contract -- uniform interface for all research tools
- **Registry singleton** manages adapters and provides query_all with citation-level deduplication (keeps highest relevance)
- **CourtListener adapter** uses httpx.AsyncClient with context manager pattern for connection lifecycle
- **CitationVerifier** tries each registered tool sequentially -- first confirmation wins
- **Per-org tool config** uses LargeBinary for encrypted API keys (consistent with OrganizationConfig pattern)
- **Registry wired in lifespan** between embedding index build and DB engine init

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- httpx.Response mock needed explicit `request` parameter for `raise_for_status()` to work -- fixed by adding `request=httpx.Request(...)` to mock responses

## User Setup Required

None - no external service configuration required. CourtListener API works without an API key for basic searches (rate-limited). Organizations can configure API keys via the admin endpoint for higher rate limits.

## Next Phase Readiness
- Research adapter framework ready for additional adapters (Westlaw, Midpage, Descrybe) in Plan 06-02+
- folio-mcp integration (INTEGRATE-05) can be built as another adapter in subsequent plan
- Knowledge base with RAG (RESEARCH-09, RESEARCH-10) needs its own plan
- folio-insights integration (RESEARCH-03) and folio-enrich integration (RESEARCH-04) need separate plans

## Self-Check: PASSED

All 9 created files verified present on disk. All 3 task commits (4c64931, b478cf1, 4853b1f) verified in git log. 34/34 tests passing.

---
*Phase: 06-legal-research-verification*
*Completed: 2026-04-04*
