---
phase: 06-legal-research-verification
plan: 04
subsystem: api
tags: [knowledge-base, rag, chunking, folio-tagging, vector-search, insights]

requires:
  - phase: 01-foundation-security
    provides: "Auth, RBAC, tenant isolation, DB engine"
  - phase: 02-folio-ontology-integration
    provides: "EmbeddingService, ConceptResolver, FOLIO loading"
  - phase: 06-legal-research-verification
    provides: "Research adapter framework from Plan 01"
provides:
  - "SemanticChunker for ~500-token chunks with overlap and heading preservation"
  - "FolioTagger for FOLIO concept tagging on chunk headings"
  - "KBRetriever for dual-signal search (vector + FOLIO IRI boosting) with per-org isolation"
  - "InsightsService for secondary/practical knowledge indexed by FOLIO IRI"
  - "KBService for full document lifecycle (upload/update/delete/bulk-import)"
  - "KBDocument and KBChunk SQLAlchemy models"
  - "Admin API at /api/v1/admin/kb with CRUD + bulk-import endpoints"
affects: [06-legal-research-verification, 07-output-export, 10-autonomy-orchestration]

tech-stack:
  added: [zipfile (stdlib), html.parser (stdlib)]
  patterns: [semantic chunking with overlap, dual-signal retrieval, FOLIO IRI boosting, per-org vector index isolation]

key-files:
  created:
    - backend/app/models/knowledge_base.py
    - backend/app/services/knowledge_base/__init__.py
    - backend/app/services/knowledge_base/chunker.py
    - backend/app/services/knowledge_base/folio_tagger.py
    - backend/app/services/knowledge_base/retriever.py
    - backend/app/services/knowledge_base/kb_service.py
    - backend/app/services/research/insights_service.py
    - backend/app/routers/kb_admin.py
    - backend/tests/test_knowledge_base.py
    - backend/tests/test_insights_service.py
    - backend/tests/test_kb_admin.py
  modified:
    - backend/app/models/__init__.py

key-decisions:
  - "Simple whitespace tokenization for chunk token counting (accurate enough for chunking boundaries)"
  - "FolioTagger accepts any async callable as resolver (not just ConceptResolver) for testability"
  - "FOLIO IRI boost multiplier of 1.5x for overlapping IRIs in dual-signal retrieval"
  - "InsightsService demotion factor of 0.5x ensures secondary knowledge ranks below primary per D-08"
  - "HTML extraction uses stdlib html.parser (no BeautifulSoup dependency)"
  - "KB admin router follows screening_admin.py pattern with router-level Depends(require_role)"

patterns-established:
  - "Semantic chunking: paragraph-first splitting with sentence fallback and token-based fallback for boundary-less text"
  - "Dual-signal retrieval: vector similarity + FOLIO IRI overlap boosting for ontology-grounded search"
  - "Insight ranking: primary authorities always above secondary regardless of base scores"

requirements-completed: [RESEARCH-03, RESEARCH-09, RESEARCH-10]

duration: 8min
completed: 2026-04-04
---

# Phase 6 Plan 04: Knowledge Base, Semantic Chunking, Dual-Signal Retrieval, and Insights Service Summary

**Semantic chunking with FOLIO heading tags, dual-signal retrieval (vector + IRI boost), InsightsService for secondary knowledge, and admin API for KB document lifecycle**

## Performance

- **Duration:** 8 min
- **Started:** 2026-04-04T23:15:35Z
- **Completed:** 2026-04-04T23:23:51Z
- **Tasks:** 2
- **Files modified:** 12

## Accomplishments
- Semantic chunker producing ~500-token chunks with 50-token overlap, heading and paragraph boundary respect
- FOLIO tagger resolving chunk headings to ontology IRIs via ConceptResolver for dual-signal retrieval
- Dual-signal retriever combining vector similarity with FOLIO IRI boosting and per-org tenant isolation
- InsightsService for secondary/practical legal knowledge with automatic demotion below primary authorities
- Full document lifecycle service (upload, update, delete, bulk ZIP import) supporting PDF, DOCX, images, HTML, plain text
- Admin API following existing screening_admin pattern with role guard
- 28 passing tests across 3 test files

## Task Commits

Each task was committed atomically:

1. **Task 1: Semantic chunker, FOLIO tagger, dual-signal retriever** - `7682daa` (test) + `f90980b` (feat)
2. **Task 2: KB document lifecycle service + admin API** - `75e5d9b` (test) + `67ac782` (feat)

_Note: TDD tasks have RED (test) and GREEN (feat) commits._

## Files Created/Modified
- `backend/app/models/knowledge_base.py` - KBDocument and KBChunk SQLAlchemy models
- `backend/app/services/knowledge_base/__init__.py` - Package init
- `backend/app/services/knowledge_base/chunker.py` - SemanticChunker with paragraph/heading boundary respect
- `backend/app/services/knowledge_base/folio_tagger.py` - FolioTagger for FOLIO IRI tagging on chunk headings
- `backend/app/services/knowledge_base/retriever.py` - KBRetriever with dual-signal search and per-org isolation
- `backend/app/services/knowledge_base/kb_service.py` - KBService with full document lifecycle pipeline
- `backend/app/services/research/insights_service.py` - InsightsService for secondary knowledge by FOLIO IRI
- `backend/app/routers/kb_admin.py` - Admin API endpoints for KB management
- `backend/app/models/__init__.py` - Added KBDocument, KBChunk re-exports
- `backend/tests/test_knowledge_base.py` - 16 tests for chunker, tagger, retriever
- `backend/tests/test_insights_service.py` - 3 tests for insights service
- `backend/tests/test_kb_admin.py` - 12 tests for KB service and admin API

## Decisions Made
- **Whitespace tokenization** for chunk token counting -- simple and sufficient for boundary decisions
- **FolioTagger resolver abstraction** -- accepts any async callable, not coupled to ConceptResolver class
- **FOLIO IRI boost factor 1.5x** -- strong enough to reorder results while not overwhelming vector similarity
- **Insight demotion 0.5x** -- ensures secondary knowledge always below primary per D-08 hierarchy
- **stdlib html.parser** -- avoids BeautifulSoup dependency for HTML extraction
- **Token-based fallback splitting** -- handles boundary-less text (no sentences, no paragraphs) gracefully

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Long texts without paragraph or sentence boundaries required a token-based fallback in the chunker's sentence splitter (added 100-token segment splitting as fallback)
- Mock session sequential call ordering required `side_effect` lists instead of single `return_value` for update/delete tests

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- KB infrastructure ready for Plan 05 (ResearchStage integration)
- KBRetriever can feed results into research pipeline
- InsightsService ready to receive LLM-generated advocacy tips
- Admin API ready for frontend KB management UI

## Self-Check: PASSED

All 11 created files verified present on disk. All 4 task commits (7682daa, f90980b, 75e5d9b, 67ac782) verified in git log. 28/28 tests passing.

---
*Phase: 06-legal-research-verification*
*Completed: 2026-04-04*
