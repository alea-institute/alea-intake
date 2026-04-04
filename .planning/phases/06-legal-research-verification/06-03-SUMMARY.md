---
phase: 06-legal-research-verification
plan: 03
subsystem: research
tags: [httpx, courtlistener, serpapi, google-scholar, mcp, folio-enrich, citation-verification, result-ranking, adapter-pattern]

# Dependency graph
requires:
  - phase: 06-legal-research-verification plan 01
    provides: "ResearchAdapter ABC, ResearchResult dataclass, ResearchToolRegistry"
  - phase: 06-legal-research-verification plan 02
    provides: "FolioMCPClient singleton, CitationNormalizer with eyecite parsing"
provides:
  - "HTTPAdapter base class with shared httpx client management and DI support"
  - "CourtListenerAdapter querying v4.3 API with correct params"
  - "GoogleScholarAdapter querying SerpAPI with engine=google_scholar"
  - "MCPAdapter wrapping FolioMCPClient for ontology tool calls"
  - "4 commercial stubs (Westlaw, Clio Library, Midpage, Descrybe) with NotConfiguredError"
  - "EnrichClient for folio-enrich HTTP API with graceful degradation"
  - "CitationVerifier with cache-first + parallel multi-source verification"
  - "ResultRanker with 5-signal composite scoring and binding strength"
affects: [06-04-research-orchestrator, 06-05-verification-pipeline, 07-output-export]

# Tech tracking
tech-stack:
  added: []
  patterns: [http-adapter-base-class, di-via-constructor-injection, cache-first-verification, parallel-verification-gather, 5-signal-composite-ranking, binding-strength-determination]

key-files:
  created:
    - backend/app/services/research/adapters/__init__.py
    - backend/app/services/research/adapters/http_adapter.py
    - backend/app/services/research/adapters/courtlistener.py
    - backend/app/services/research/adapters/google_scholar.py
    - backend/app/services/research/adapters/mcp_adapter.py
    - backend/app/services/research/adapters/westlaw.py
    - backend/app/services/research/adapters/clio_library.py
    - backend/app/services/research/adapters/midpage.py
    - backend/app/services/research/adapters/descrybe.py
    - backend/app/services/folio_enrich/__init__.py
    - backend/app/services/folio_enrich/enrich_client.py
    - backend/app/services/research/citation_verifier.py
    - backend/app/services/research/result_ranker.py
    - backend/tests/test_research_adapters.py
    - backend/tests/test_enrich_client.py
    - backend/tests/test_citation_verifier.py
  modified: []

key-decisions:
  - "HTTPAdapter as intermediate base class between ResearchAdapter ABC and concrete HTTP adapters, with shared _get/_post helpers"
  - "All HTTP adapters accept optional httpx.AsyncClient via constructor for DI/testing (Pitfall 7)"
  - "CourtListener citation field parsed as list-or-string (API returns both formats)"
  - "Commercial stubs raise NotConfiguredError rather than returning empty to distinguish 'not configured' from 'no results'"
  - "EnrichClient returns None on connection errors for graceful degradation (Pitfall 4)"
  - "CitationVerifier uses in-memory cache with TTL (24h case law, 7d statutes per D-19)"
  - "Multi-source confidence formula: 1 source=0.7, 2+ sources=0.7+0.15*(n-1) capped at 1.0"
  - "ResultRanker uses 5 weighted signals: relevance(0.30), recency(0.20), jurisdiction(0.25), court_level(0.15), verification(0.10)"
  - "Binding strength: same jurisdiction+authoritative type=binding, different=persuasive, secondary sources=secondary"

patterns-established:
  - "HTTP adapter base class pattern: HTTPAdapter(ResearchAdapter) with shared client management and _get/_post helpers"
  - "NotConfiguredError for unconfigured commercial adapters: explicit error vs silent empty"
  - "Cache-first verification: check in-memory cache (TTL-aware), then parallel live sources via asyncio.gather"
  - "5-signal composite scoring: weighted sum of relevance, recency, jurisdiction match, court level, verification confidence"
  - "Binding strength determination based on jurisdiction match and authority type"

requirements-completed: [RESEARCH-01, RESEARCH-05, RESEARCH-06, RESEARCH-07, RESEARCH-08, RESEARCH-04]

# Metrics
duration: 6min
completed: 2026-04-04
---

# Phase 6 Plan 03: Research Tool Adapters, Citation Verifier, and Result Ranker Summary

**8 research adapters (CourtListener, Google Scholar, MCP, 4 stubs), multi-source citation verifier with cache-first strategy, and 5-signal result ranker with binding strength**

## Performance

- **Duration:** 6 min
- **Started:** 2026-04-04T23:06:17Z
- **Completed:** 2026-04-04T23:13:03Z
- **Tasks:** 2
- **Files modified:** 16

## Accomplishments
- HTTPAdapter base class with shared httpx client, _get/_post helpers, and constructor-based DI for all HTTP adapters
- CourtListenerAdapter querying v4.3 API with q/type=o/court params and 429 rate limit handling
- GoogleScholarAdapter querying via SerpAPI with engine=google_scholar and NotConfiguredError without key
- MCPAdapter wrapping FolioMCPClient.search_concepts for ontology lookups
- 4 commercial stubs (Westlaw, Clio Library, Midpage, Descrybe) raising NotConfiguredError
- EnrichClient for folio-enrich /enrich API with graceful degradation on connection errors
- CitationVerifier with cache-first + parallel multi-source verification and configurable TTL
- ResultRanker with 5-signal composite scoring, binding strength, and optional LLM re-ranking scaffold
- 44 tests passing across all three test files

## Task Commits

Each task was committed atomically:

1. **Task 1: HTTP + MCP adapters and folio-enrich client**
   - `aba3fc0` (test): add failing tests for research adapters and enrich client
   - `4e69a9d` (feat): implement HTTP/MCP adapters, 4 commercial stubs, and folio-enrich client
2. **Task 2: Citation verifier + result ranker**
   - `53c6cd9` (test): add failing tests for CitationVerifier and ResultRanker
   - `5e37711` (feat): implement CitationVerifier and ResultRanker

_Note: TDD tasks have separate test and implementation commits._

## Files Created/Modified
- `backend/app/services/research/adapters/__init__.py` - Adapters package init with all re-exports
- `backend/app/services/research/adapters/http_adapter.py` - HTTPAdapter base with _get/_post, DI, NotConfiguredError
- `backend/app/services/research/adapters/courtlistener.py` - CourtListener v4.3 adapter with search and verify
- `backend/app/services/research/adapters/google_scholar.py` - SerpAPI Google Scholar adapter
- `backend/app/services/research/adapters/mcp_adapter.py` - MCPAdapter wrapping FolioMCPClient
- `backend/app/services/research/adapters/westlaw.py` - Westlaw stub (NotConfiguredError)
- `backend/app/services/research/adapters/clio_library.py` - Clio Library stub (NotConfiguredError)
- `backend/app/services/research/adapters/midpage.py` - Midpage stub (NotConfiguredError)
- `backend/app/services/research/adapters/descrybe.py` - Descrybe stub (NotConfiguredError)
- `backend/app/services/folio_enrich/__init__.py` - folio-enrich package init
- `backend/app/services/folio_enrich/enrich_client.py` - HTTP client for folio-enrich with graceful degradation
- `backend/app/services/research/citation_verifier.py` - Multi-source verifier with cache-first + parallel
- `backend/app/services/research/result_ranker.py` - 5-signal ranker with binding strength
- `backend/tests/test_research_adapters.py` - 30 adapter tests
- `backend/tests/test_enrich_client.py` - 5 enrich client tests
- `backend/tests/test_citation_verifier.py` - 14 verifier + ranker tests (total: 44 new tests, all green)

## Decisions Made
- **HTTPAdapter intermediate base** -- shared httpx client management avoids boilerplate across 6 HTTP adapters
- **DI via constructor injection** -- all adapters accept optional httpx.AsyncClient for testing (Pitfall 7)
- **CourtListener citation as list-or-string** -- API returns both formats; parser handles gracefully
- **NotConfiguredError for stubs** -- explicit distinction from "no results found" allows upstream error handling
- **EnrichClient returns None on errors** -- graceful degradation per Pitfall 4 (folio-enrich may not be running)
- **In-memory cache with TTL** -- simple and fast; D-19 TTLs (24h case law, 7d statutes) prevent stale data
- **Confidence formula** -- 1 source=0.7, 2+=0.85+; multiple confirming sources increase trust per D-05
- **5 weighted signals** -- relevance(0.30), recency(0.20), jurisdiction(0.25), court_level(0.15), verification(0.10)
- **Binding strength** -- same jurisdiction+authoritative = binding, different = persuasive, secondary = secondary per D-17

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed CourtListener citation field list/string parsing**
- **Found during:** Task 1 (CourtListenerAdapter)
- **Issue:** CourtListener API returns citation as a list `["123 F.3d 456"]` not a string; the `or ""` fallback didn't trigger for truthy lists
- **Fix:** Added explicit `isinstance(raw_citation, list)` check before string fallback
- **Files modified:** backend/app/services/research/adapters/courtlistener.py
- **Verification:** Test passes: citation correctly parsed as string from list response
- **Committed in:** 4e69a9d (part of Task 1 feat commit)

---

**Total deviations:** 1 auto-fixed (1 bug fix)
**Impact on plan:** Bug fix necessary for correct citation parsing. No scope creep.

## Issues Encountered
None.

## User Setup Required
None -- no external service configuration required. EnrichClient defaults to localhost:8731 (configurable via FOLIO_ENRICH_URL env var). CourtListener works without API key for basic searches.

## Next Phase Readiness
- All 8 adapters ready for ResearchStage orchestration (Plan 05)
- CitationVerifier ready for verification pipeline integration
- ResultRanker ready for result presentation ordering
- EnrichClient ready for document annotation workflows
- Commercial stubs ready for future credential configuration

## Self-Check: PASSED

---
*Phase: 06-legal-research-verification*
*Completed: 2026-04-04*
