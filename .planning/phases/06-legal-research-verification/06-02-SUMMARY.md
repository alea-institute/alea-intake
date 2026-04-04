---
phase: 06-legal-research-verification
plan: 02
subsystem: research
tags: [mcp, eyecite, folio-mcp, citation-parsing, bluebook, singleton, deduplication]

# Dependency graph
requires:
  - phase: 01-foundation-security
    provides: "FastAPI app structure, EmbeddingService singleton pattern"
  - phase: 06-legal-research-verification plan 01
    provides: "ResearchResult dataclass from base.py adapter framework"
provides:
  - "FolioMCPClient singleton wrapping all 12 folio-mcp tools via mcp SDK"
  - "CitationNormalizer with eyecite-based Bluebook citation parsing"
  - "NormalizedCitation Pydantic model"
  - "Citation deduplication by normalized (volume, reporter, page)"
  - "Deterministic SHA-256 query hash for research result caching"
affects: [06-03-research-orchestrator, 06-05-verification-pipeline]

# Tech tracking
tech-stack:
  added: [mcp>=1.27.0, eyecite>=2.7.6]
  patterns: [mcp-singleton-subprocess, eyecite-citation-parsing, reporter-whitespace-normalization, cache-key-hashing]

key-files:
  created:
    - backend/app/services/mcp/__init__.py
    - backend/app/services/mcp/folio_mcp_client.py
    - backend/app/services/research/citation_normalizer.py
    - backend/tests/test_folio_mcp_client.py
    - backend/tests/test_citation_normalizer.py
  modified:
    - backend/pyproject.toml

key-decisions:
  - "FolioMCPClient uses __aenter__/__aexit__ on stdio_client and ClientSession directly (not wrapping in asynccontextmanager) for explicit cleanup control"
  - "Reporter whitespace normalization via regex re.sub for are_same_authority comparison (F. 3d == F.3d)"
  - "Unparseable citations in deduplicate_results are preserved as-is (appended after deduped results)"
  - "compute_query_hash normalizes inputs to lowercase before hashing for case-insensitive cache keys"

patterns-established:
  - "MCP client singleton: get_instance/reset_instance with threading.Lock, matching EmbeddingService pattern"
  - "Citation normalization pipeline: eyecite parse -> extract groups -> normalize reporter -> canonical form"
  - "Deduplication by normalized citation key with highest-score retention"

requirements-completed: [INTEGRATE-05, RESEARCH-07]

# Metrics
duration: 4min
completed: 2026-04-04
---

# Phase 6 Plan 02: MCP Client + Citation Normalizer Summary

**FolioMCPClient singleton wrapping all 12 folio-mcp tools via mcp SDK, plus CitationNormalizer with eyecite-based Bluebook parsing for deduplication and cache keys**

## Performance

- **Duration:** 4 min
- **Started:** 2026-04-04T22:58:41Z
- **Completed:** 2026-04-04T23:03:05Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- FolioMCPClient singleton with all 12 folio-mcp tool wrappers, async context manager, and proper subprocess cleanup
- CitationNormalizer parsing Bluebook citations via eyecite with reporter whitespace normalization
- Deduplication of ResearchResults by normalized citation and deterministic SHA-256 cache key computation
- mcp>=1.27.0 and eyecite>=2.7.6 installed as new dependencies
- 49 tests total (22 MCP client + 27 citation normalizer), all passing

## Task Commits

Each task was committed atomically:

1. **Task 1: Install dependencies + FolioMCPClient singleton**
   - `540a189` (test): add failing tests for FolioMCPClient singleton
   - `39fcb23` (feat): implement FolioMCPClient singleton wrapping all 12 folio-mcp tools
2. **Task 2: CitationNormalizer with eyecite-based parsing**
   - `31cb1c4` (test): add failing tests for CitationNormalizer
   - `144e6dd` (feat): implement CitationNormalizer with eyecite-based Bluebook parsing

_Note: TDD tasks have separate test and implementation commits._

## Files Created/Modified
- `backend/pyproject.toml` - Added mcp>=1.27.0 and eyecite>=2.7.6 dependencies
- `backend/app/services/mcp/__init__.py` - MCP services package init
- `backend/app/services/mcp/folio_mcp_client.py` - FolioMCPClient singleton wrapping 12 folio-mcp tools via mcp SDK
- `backend/app/services/research/citation_normalizer.py` - CitationNormalizer + NormalizedCitation using eyecite
- `backend/tests/test_folio_mcp_client.py` - 22 tests for MCP client (mocked SDK, no real subprocess)
- `backend/tests/test_citation_normalizer.py` - 27 tests for citation parsing, dedup, and cache keys

## Decisions Made
- **FolioMCPClient uses direct __aenter__/__aexit__ on SDK context managers** for explicit cleanup control rather than wrapping in asynccontextmanager
- **Reporter whitespace normalization via regex** to handle "F. 3d" vs "F.3d" variations in are_same_authority
- **Unparseable citations preserved in deduplication** -- appended after deduped results rather than dropped
- **Case-insensitive cache key hashing** -- inputs lowercased before SHA-256 for consistent caching

## Deviations from Plan

None -- plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None -- no external service configuration required.

## Next Phase Readiness
- FolioMCPClient ready for Plans 03 (research orchestrator) and 05 (verification pipeline) to consume
- CitationNormalizer ready for D-05/D-15 deduplication and D-19 cache key computation
- Lifespan integration (connecting FolioMCPClient at startup) deferred to Plan 05 per plan spec

## Self-Check: PASSED

All 5 created files exist on disk. All 4 commit hashes found in git log.

---
*Phase: 06-legal-research-verification*
*Completed: 2026-04-04*
