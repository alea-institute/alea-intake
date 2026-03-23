# Phase 2: FOLIO Ontology Integration - Context

**Gathered:** 2026-03-22
**Status:** Ready for planning

<domain>
## Phase Boundary

The system can load the FOLIO ontology, resolve consumer facts to canonical FOLIO concept IRIs across all branches, traverse ontology relationships for adjacency discovery, and gracefully handle unmapped concepts. This phase delivers the ontology integration layer that all downstream analysis phases build on.

</domain>

<decisions>
## Implementation Decisions

### Ontology Loading & Lifecycle
- Replicate the FOLIO loading strategy from folio-enrich and folio-mapper: on startup, check the FOLIO repo on GitHub remote for freshness, download if stale, then load
- folio-enrich pattern: `ensure_owl_fresh()` with ETag-based HTTP conditional check at startup, then periodic background update task via `OWLUpdateManager`
- folio-mapper pattern: background thread warms `FOLIO()` at startup, `start_update_checker()` polls GitHub commits API with HEAD fallback when rate-limited
- Single shared FOLIO instance across all tenants (FOLIO is a public standard — same for everyone)
- Configurable update check interval (default 24h), admin-configurable
- When OWL update arrives: wait for active analyses to finish (idle quiescence), then hot-swap the singleton FOLIO instance. Matches folio-enrich's `OWLUpdateManager` pattern
- Admin API endpoints for: check OWL status, trigger manual update, rollback to previous version. Health endpoint includes OWL cache status
- Configurable OWL branch/tag (default `main`), admin-configurable for deployments tracking specific FOLIO releases

### Embedding Index
- Build embedding index of FOLIO concept labels at startup (in addition to folio-python's built-in search)
- Dual vector store via DB abstraction: pgvector on PostgreSQL, FAISS on SQLite — matches Phase 1's database abstraction pattern
- Embedding model configurable per-org (local vs cloud), continuing the per-org LLM config pattern from Phase 1

### Concept Resolution Strategy
- Multi-stage pipeline: (1) Embedding similarity for fast candidate retrieval, (2) folio-python label/prefix search for exact matches, (3) LLM-powered semantic matching (`search_by_llm`) for ambiguous cases. Combined confidence score from all signals
- Search ALL FOLIO branches — not just Objectives, Areas of Law, Legal Authorities, and Jurisdictions. Full taxonomy: Actor/Player, Asset Type, Communication Modality, Document/Artifact, Engagement Attributes, Event, Financial Concepts and Metrics, Forums and Venues, Governmental Body, Industry and Market, Legal Entity, Location, Service, and all others
- When multiple concepts match: return ranked list with confidence scores (all above threshold). Downstream analysis considers top-N
- Confidence threshold: sensible default with org-configurable override
- Replicate folio-mapper's `LEGAL_TERM_EXPANSIONS` and `BRANCH_SIGNAL_WORDS` domain-aware expansion patterns, in addition to LLM handling natural language variation
- Use `parallel_search_by_llm` to search multiple FOLIO branches simultaneously
- Persist concept resolution results per-intake in the tenant DB: resolved FOLIO IRIs, confidence scores, matched text. Creates the fact-to-concept mapping table for Phase 4

### Adjacency & Relationship Traversal
- Traverse both class hierarchy (subClassOf/parentClassOf) AND OWL object properties for adjacency discovery
- Traverse all FOLIO object properties — no curated subset
- Configurable traversal depth with sensible default (e.g., 2-3 hops), org-configurable override. Phase 5 does deeper exploration
- Use folio-python's `find_connections` for cross-branch relationship discovery (subject-predicate-object triples)
- Return graph structure (nodes + edges) preserving traversal path and relationship labels — not flat list
- Persist concept graph per-intake in tenant DB for later visualization (Phase 9) and audit trail

### Unmapped Concept Handling
- Structured unmapped record: original text, LLM-suggested category, confidence it's unmapped (not just low-confidence match), nearest FOLIO concept(s)
- Unmapped concepts participate fully in analysis pipeline — equal footing with mapped concepts. FOLIO-06 requires this
- Local IRI namespace using folio-python's `generate_iri()` schema (UUID4 -> base64 alphanumeric -> `https://folio.openlegalstandard.org/{value}`), aligned with WebProtege IRI creation
- Org-configurable collection of unmapped concepts (default: collect). Admin can review aggregated unmapped concepts
- Admin can manually submit proposed concepts to the FOLIO repo for consideration (the GitHub submission workflow via feature branch/commits is deferred — Phase 2 only collects and stores)
- For adjacency discovery on unmapped concepts: use LLM suggestions + nearest mapped FOLIO concept(s) to anchor traversal

### Claude's Discretion
- Exact confidence scoring formula for multi-stage matching
- Embedding model default choice
- Graph storage schema design (nodes/edges table structure)
- OWL update timeout and retry parameters
- Exact default traversal depth value
- Internal caching strategy for hot FOLIO queries

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### FOLIO Python library (primary integration library)
- `../folio-python/folio/graph.py` -- `FOLIO` class: singleton loader, search methods (`search_by_label`, `search_by_prefix`, `search_by_llm`, `parallel_search_by_llm`), traversal (`get_subgraph`, `get_children`, `get_parents`, `find_connections`), branch accessors (`get_objectives`, `get_areas_of_law`, `get_legal_authorities`, `get_locations`, etc.), IRI generation (`generate_iri`)
- `../folio-python/folio/models.py` -- `OWLClass` and `OWLObjectProperty` pydantic models (IRI, label, sub_class_of, parent_class_of, alternative_labels, definition, examples, domain, range)
- `../folio-python/folio/__init__.py` -- Public exports: `FOLIO`, `FOLIOTypes`, `FOLIO_TYPE_IRIS`, `OWLClass`, `OWLObjectProperty`, `NSMAP`

### Sibling project loading patterns (replicate these)
- `../folio-enrich/backend/app/services/folio/owl_cache.py` -- ETag-based freshness check, `ensure_owl_fresh()`, atomic download with XML validation, one-version rollback, `get_owl_content_hash()`, `get_owl_status()`
- `../folio-enrich/backend/app/services/folio/owl_updater.py` -- `OWLUpdateManager` singleton: background check, download, wait-for-idle, hot-reload, re-index embeddings, rollback support
- `../folio-enrich/backend/app/main.py` -- Lifespan: `ensure_owl_fresh` -> `FolioService.get_instance()` -> embedding index -> periodic update task
- `../folio-mapper/backend/app/services/folio_service.py` -- Singleton FOLIO loader, domain-aware expansions (`LEGAL_TERM_EXPANSIONS`, `BRANCH_SIGNAL_WORDS`), search stopwords
- `../folio-mapper/backend/app/services/owl_update_service.py` -- GitHub commits API check, HEAD fallback, hot-swap, periodic timer, manual trigger/force update

### Project context
- `.planning/PROJECT.md` -- FOLIO ecosystem context, integration patterns, tech stack constraints
- `.planning/REQUIREMENTS.md` -- FOLIO-01 through FOLIO-07 requirements
- `.planning/ROADMAP.md` -- Phase 2 success criteria and dependencies

### Existing codebase (Phase 1 foundation)
- `backend/app/services/llm_service.py` -- LLMService with per-org config and training opt-out (reuse pattern for embedding model config)
- `backend/app/models/shared.py` -- Organization model with settings JSON field (use for FOLIO config)
- `backend/app/db/tenant.py` -- Tenant schema management (concept data goes in tenant schema)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `LLMService` (backend/app/services/llm_service.py): Per-org LLM provider/model config with training opt-out. Reuse pattern for embedding model configuration
- `Organization.settings` JSON field: Extensible org config — use for FOLIO-specific settings (confidence threshold, traversal depth, embedding model, update branch)
- `alea-llm-client` dependency: Already wired for multi-provider LLM access. Used by folio-python's `search_by_llm`
- `pgvector` dependency: Already in pyproject.toml for vector similarity search
- Tenant schema management: All per-intake data goes in tenant schemas via existing middleware

### Established Patterns
- Singleton services with `get_instance()` (common in folio-enrich/folio-mapper)
- Per-org configuration via Organization settings
- Schema-per-tenant data isolation
- FastAPI lifespan for startup/shutdown tasks
- Async service layer with sync fallbacks via `run_in_executor`

### Integration Points
- FastAPI lifespan: Add FOLIO loading and update checker alongside existing middleware
- Health endpoint: Extend to include OWL cache status
- Admin router: Add FOLIO update management endpoints
- Tenant DB: New tables for concept mappings, graph nodes/edges, unmapped concepts

</code_context>

<specifics>
## Specific Ideas

- Loading strategy must replicate folio-enrich and folio-mapper patterns exactly — startup GitHub freshness check, periodic background update, hot-reload with idle wait
- ALL FOLIO branches searched during concept resolution — the full 22+ branch taxonomy, not just the 4-5 mentioned in requirements
- Domain-aware term expansions (LEGAL_TERM_EXPANSIONS, BRANCH_SIGNAL_WORDS) ported from folio-mapper — consumer narratives use natural language that benefits from these
- Unmapped concept IRIs follow folio-python's `generate_iri()` schema for WebProtege alignment
- Admin unmapped concept submission workflow follows the ontokit-web/ontokit-api pattern (feature branch + commits to FOLIO OWL repo) — but the submission mechanism is deferred, Phase 2 only collects

</specifics>

<deferred>
## Deferred Ideas

- GitHub submission workflow for unmapped concepts (feature branch + commit to FOLIO repo) -- collect and store in Phase 2, submission mechanism in a future phase or ontokit integration
- Embedding model management UI -- Phase 8 admin interface
- Per-org FOLIO branch filtering (restricting which branches an org searches) -- not needed now, all branches searched

</deferred>

---

*Phase: 02-folio-ontology-integration*
*Context gathered: 2026-03-22*
