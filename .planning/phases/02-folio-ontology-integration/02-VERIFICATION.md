---
phase: 02-folio-ontology-integration
verified: 2026-03-24T00:00:00Z
status: passed
score: 4/4 must-haves verified
re_verification: false
---

# Phase 2: FOLIO Ontology Integration Verification Report

**Phase Goal:** The system can load the FOLIO ontology, resolve consumer facts to canonical FOLIO concept IRIs, traverse ontology relationships for adjacency discovery, and gracefully handle unmapped concepts
**Verified:** 2026-03-24
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | The system loads the FOLIO ontology at startup via folio-python and uses IRIs as the canonical identifier for every legal concept in the data model | VERIFIED | `main.py` lifespan calls `run_in_executor(None, ensure_owl_fresh)` then `run_in_executor(None, get_folio)`. `folio_service.py` initializes `FOLIO(github_repo_branch=branch)` under a threading lock. All four DB models (`ConceptMapping`, `ConceptGraphNode`, `ConceptGraphEdge`, `UnmappedConceptRecord`) store IRI as `String(512)` primary concept identifier. |
| 2 | Given a consumer's factual description, the system identifies applicable FOLIO Objectives (claims/defenses), Areas of Law, Legal Authority types, and Jurisdictions | VERIFIED | `concept_resolver.py` implements a 3-stage pipeline: (1) embedding similarity via `embedding_service.search(text, top_k=...)`, (2) label/prefix search via `folio.search_by_label()` and `folio.search_by_prefix()`, (3) LLM stage via `folio.parallel_search_by_llm()`. Branch classification walks sub_class_of hierarchy to map concepts to Objectives, Area of Law, Legal Authorities, and Location. `term_expansions.py` provides 35+ domain expansions for enriched queries. Results persisted as `ConceptMapping` records. |
| 3 | The system traverses FOLIO OWL object properties to discover adjacent legal concepts related to an identified issue | VERIFIED | `adjacency.py` calls `folio.get_children(concept_iri, max_depth=...)`, `folio.get_parents(concept_iri, max_depth=...)`, and `folio.find_connections(concept_iri)`. Returns `{"nodes": [...], "edges": [...]}` graph structure (not flat list) with labeled edges including `rdfs:subClassOf` and property names. Unmapped concept variant `discover_adjacent_for_unmapped()` uses nearest mapped concepts as traversal anchors. `persist_concept_graph()` writes `ConceptGraphNode` and `ConceptGraphEdge` records to tenant DB. |
| 4 | When the system encounters a legal concept not in FOLIO, it flags it as "unmapped" and continues analysis rather than dropping it | VERIFIED | `unmapped.py` `handle_unmapped_concept()` generates a local IRI via `folio.generate_iri()`, computes `unmapped_confidence` via `1 - (best_score / threshold)`, stores up to 3 nearest FOLIO concepts, and calls optional LLM branch suggestion. `UnmappedConceptRecord` model persists to tenant DB. `ResolvedConcept.is_unmapped` flag propagates through `ConceptMapping`. `discover_adjacent_for_unmapped()` enables full adjacency traversal using anchor IRIs. |

**Score:** 4/4 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/services/folio/folio_service.py` | Singleton FOLIO loader with thread-safe hot-swap | VERIFIED | 75 lines. Exports `get_folio`, `reload_folio`, `reset_folio`. Double-checked locking with `threading.Lock`. |
| `backend/app/services/folio/owl_cache.py` | ETag-based OWL freshness check, atomic download, rollback | VERIFIED | 202 lines. Exports `ensure_owl_fresh`, `get_owl_status`, `rollback_owl`. Implements HEAD conditional request, XML validation, atomic `.tmp` rename, one-version `.previous` rollback. |
| `backend/app/services/folio/owl_updater.py` | OWLUpdateManager singleton with background check, idle-wait, hot-swap | VERIFIED | 140 lines. Exports `OWLUpdateManager`, `_periodic_owl_check`. Implements `increment_active`/`decrement_active`, `wait_for_idle`, `check_and_update` with EmbeddingService rebuild. |
| `backend/app/models/folio_concepts.py` | ConceptMapping, ConceptGraphNode, ConceptGraphEdge, UnmappedConcept tenant models | VERIFIED | 76 lines. All four SQLAlchemy models defined using `TenantBase` with IRI string columns. |
| `backend/app/services/folio/term_expansions.py` | LEGAL_TERM_EXPANSIONS and BRANCH_SIGNAL_WORDS dicts | VERIFIED | 168 lines. 35+ term expansions, 12 branch signal word groups, `SEARCH_STOPWORDS`, `expand_legal_terms()`, `get_branch_signals()`. |
| `backend/app/services/embedding/service.py` | EmbeddingService with dual-backend abstraction, encode/search/build_index | VERIFIED | Singleton pattern, `_ensure_provider()` and `_ensure_backend()` with FAISS/pgvector routing, `build_index()` batches FOLIO classes at 256/batch. |
| `backend/app/services/embedding/backends/pgvector_backend.py` | PgVectorBackend implementing EmbeddingBackend protocol | VERIFIED | PostgreSQL cosine distance via `<=>` operator, `ensure_table()`, `upsert()`, `search()`. |
| `backend/app/services/embedding/backends/faiss_backend.py` | FAISSBackend implementing EmbeddingBackend protocol | VERIFIED | `IndexFlatIP` on L2-normalized vectors for cosine similarity, `upsert()`, `search()`, `delete_all()`. |
| `backend/app/services/embedding/providers/local.py` | LocalEmbeddingProvider using sentence-transformers | VERIFIED | `all-MiniLM-L6-v2` (384d), `encode()`, `encode_batch()` with `normalize_embeddings=True`. |
| `backend/app/services/folio/concept_resolver.py` | Multi-stage concept resolution pipeline | VERIFIED | 460 lines. Exports `resolve_concepts`, `ConceptResolutionConfig`, `ResolvedConcept`, `persist_resolutions`. Full 3-stage pipeline with early exit on high-confidence embedding match. |
| `backend/app/services/folio/unmapped.py` | Unmapped concept handling with local IRI generation and LLM branch suggestion | VERIFIED | 193 lines. Exports `handle_unmapped_concept`, `UnmappedConceptData`, `persist_unmapped`. IRI via `folio.generate_iri()`, confidence formula, LLM branch suggestion with fallback. |
| `backend/app/services/folio/adjacency.py` | Graph traversal and adjacency discovery via hierarchy and object properties | VERIFIED | 265 lines. Exports `discover_adjacent_concepts`, `discover_adjacent_for_unmapped`, `persist_concept_graph`, `AdjacencyConfig`. Traverses children, parents, object properties (find_connections). |
| `backend/app/routers/folio_admin.py` | Admin API endpoints for OWL management and unmapped concept review | VERIFIED | 120 lines. `router = APIRouter(prefix="/api/v1/admin/folio")`. Endpoints: `/owl/status`, `/owl/update`, `/owl/rollback`, `/unmapped` (paginated), `/config`. All gated by `require_role(Role.ADMIN)`. |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `backend/app/main.py` | `folio_service.py` | `run_in_executor(None, ensure_owl_fresh)` and `run_in_executor(None, get_folio)` in lifespan | WIRED | Lines 41, 44 of main.py confirm both calls. |
| `backend/app/main.py` | `owl_updater.py` | `OWLUpdateManager.get_instance()` + `asyncio.create_task(_periodic_owl_check(...))` | WIRED | Lines 52–54 of main.py confirm task creation with configured interval. |
| `backend/app/main.py` | `/health` | `get_owl_status()` included in health response as `"folio"` key | WIRED | Lines 128–134 of main.py confirm `get_owl_status()` injected into health response. |
| `backend/app/main.py` | `embedding/service.py` | `EmbeddingService.get_instance()` + `run_in_executor(None, emb_service.build_index, folio)` | WIRED | Line 49 of main.py confirms `build_index` called with loaded FOLIO instance. |
| `concept_resolver.py` | `embedding/service.py` | `embedding_service.search(text, top_k=config.max_embedding_candidates)` | WIRED | Line 243 of concept_resolver.py confirms search call with configurable top_k. |
| `concept_resolver.py` | `folio.search_by_label` / `folio.search_by_prefix` / `folio.parallel_search_by_llm` | Stage 2 and 3 folio-python API calls | WIRED | Lines 286, 317, 342 confirm all three folio-python search methods called. |
| `concept_resolver.py` | `term_expansions.py` | `expand_legal_terms(text)` and `get_branch_signals(text)` | WIRED | Lines 23, 199, 200 confirm import and usage in resolution pipeline. |
| `unmapped.py` | `folio.generate_iri()` | Local IRI generation for unmapped concepts | WIRED | Line 90 of unmapped.py confirms direct `folio.generate_iri()` call. |
| `adjacency.py` | `folio.get_children / folio.get_parents / folio.find_connections` | Hierarchy and property traversal | WIRED | Lines 79, 102, 126 confirm all three folio-python traversal APIs called. |
| `adjacency.py` | `folio_concepts.py` | `ConceptGraphNode` and `ConceptGraphEdge` record creation in `persist_concept_graph()` | WIRED | Lines 235–260 confirm both model classes imported and instantiated. |
| `folio_admin.py` | `owl_cache.py` | `get_owl_status()`, `rollback_owl()` called in admin endpoints | WIRED | Lines 23, 36, 51 confirm both cache functions imported and called in route handlers. |
| `backend/app/main.py` | `folio_admin_router` | `app.include_router(folio_admin_router)` | WIRED | Line 121 of main.py confirms router registration. |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| FOLIO-01 | 02-01, 02-03 | System loads FOLIO ontology via folio-python and uses IRIs as canonical identifiers | SATISFIED | `folio_service.py` singleton + lifespan integration. All DB models use IRI strings as concept identifiers. |
| FOLIO-02 | 02-02 | System maps consumer facts to FOLIO Objectives (Claims, Defenses) via LLM + ontology matching | SATISFIED | `concept_resolver.py` 3-stage pipeline resolves text to Objectives branch. Branch classification verified via `_determine_branch()` hierarchy walk. |
| FOLIO-03 | 02-02 | System identifies applicable Areas of Law from FOLIO taxonomy | SATISFIED | `_determine_branch()` maps to "Area of Law" branch root IRI. Stage 2 `search_by_label` and stage 3 LLM search cover all 24 branches. |
| FOLIO-04 | 02-02 | System identifies applicable Legal Authorities types from FOLIO taxonomy | SATISFIED | "Legal Authorities" branch included in `branch_methods` dict in `_determine_branch()`. Full ontology coverage through embedding index over all FOLIO classes. |
| FOLIO-05 | 02-02 | System determines applicable Jurisdictions from FOLIO Location branch | SATISFIED | "Location" branch included in `branch_methods` dict via `get_locations()` method. |
| FOLIO-06 | 02-03 | System gracefully handles concepts not in FOLIO (flags as "unmapped" rather than dropping) | SATISFIED | `unmapped.py` `handle_unmapped_concept()` creates `UnmappedConceptData` with local IRI. `is_unmapped=True` propagates through `ConceptMapping`. `discover_adjacent_for_unmapped()` keeps unmapped concepts in full analysis pipeline. |
| FOLIO-07 | 02-03 | System uses FOLIO ontology relationships (OWL object properties) to discover adjacent legal concepts | SATISFIED | `adjacency.py` calls `folio.find_connections(concept_iri)` for object property traversal plus `get_children`/`get_parents` for hierarchy. Returns `{nodes, edges}` graph structure with named relationship edges. |

All 7 requirements (FOLIO-01 through FOLIO-07) claimed across all three plans are satisfied. No orphaned requirements detected for Phase 2.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/app/services/embedding/providers/cloud.py` | 24–31 | `raise NotImplementedError(...)` in both `encode()` and `encode_batch()` | Info | Intentional future stub for cloud embedding providers. Not used in any active code path; system defaults to `LocalEmbeddingProvider`. Does not block phase goal. |

No blockers or warnings found. The single info-level item is an intentional placeholder for a future feature (cloud embeddings) that is not required for Phase 2.

---

### Human Verification Required

None identified. All four success criteria are verifiable through static analysis of the codebase.

The following behaviors have indirect evidence but do not require human verification at this stage since they depend on runtime conditions (real FOLIO OWL access, LLM availability) that are out of scope for a pre-deployment verification:

**1. End-to-End Concept Resolution with Live FOLIO**
- Test: Submit a consumer narrative describing an eviction ("my landlord locked me out") to `resolve_concepts()`
- Expected: Returns `ResolvedConcept` objects with Objectives IRIs (Unlawful Detainer) and Area of Law IRIs (Landlord-Tenant) with confidence > 0.5
- Why human: Requires live FOLIO OWL load and sentence-transformers model; cannot verify without running the stack

**2. LLM Stage Activation**
- Test: Submit a narrative that produces no high-confidence embedding or label match to verify LLM stage triggers
- Expected: `folio.parallel_search_by_llm()` called; results merged with other stages
- Why human: Requires LLM provider and live FOLIO; LLM stage is conditional on `llm_model is not None`

**3. OWL ETag Hot-Swap Under Load**
- Test: Start active analyses, trigger OWL update, verify idle-wait prevents singleton replacement until analyses complete
- Expected: `OWLUpdateManager.wait_for_idle()` blocks until `active_count == 0` before calling `reload_folio()`
- Why human: Requires concurrent load testing and real network call to GitHub

---

### Gaps Summary

No gaps identified. All phase goals, success criteria, and requirements are satisfied by the implemented codebase.

The phase delivered:
- FOLIO singleton with ETag-based OWL freshness, atomic download, and one-version rollback
- OWLUpdateManager with background periodic check, idle-wait hot-swap, and embedding index rebuild
- Four tenant DB models (ConceptMapping, ConceptGraphNode, ConceptGraphEdge, UnmappedConceptRecord) using IRIs as canonical identifiers
- Dual-backend embedding service (FAISS for SQLite, pgvector for PostgreSQL) with `all-MiniLM-L6-v2` local provider
- Three-stage concept resolution pipeline (embedding similarity, label/prefix search, LLM semantic) with confidence scoring and persistence
- Unmapped concept handler with local IRI generation via `folio.generate_iri()`, nearest-concept tracking, and LLM branch suggestion
- Graph-based adjacency discovery traversing both class hierarchy and OWL object properties, with graph persistence
- Admin API for OWL lifecycle management and unmapped concept review
- Lifespan integration wiring all components together at application startup
- 1,377 lines of substantive tests across 7 test files

---

_Verified: 2026-03-24_
_Verifier: Claude (gsd-verifier)_
