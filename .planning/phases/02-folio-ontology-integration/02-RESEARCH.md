# Phase 2: FOLIO Ontology Integration - Research

**Researched:** 2026-03-22
**Domain:** OWL ontology loading, semantic concept resolution, graph traversal, embedding-based vector search
**Confidence:** HIGH

## Summary

Phase 2 integrates the FOLIO ontology (18,300+ legal concepts across 24 branches) into the alea-intake system. The core library is folio-python v0.2.1, which provides OWL parsing, class/property indexing, label search (via rapidfuzz), prefix search (via marisa-trie), LLM-powered semantic search (via alea-llm-client), and graph traversal (subgraph, children, parents, find_connections). Two sibling projects -- folio-enrich and folio-mapper -- have battle-tested patterns for OWL loading, freshness checking, hot-reload, and embedding-based search that this phase must replicate.

The phase delivers five core capabilities: (1) singleton FOLIO ontology loading with GitHub freshness checks and hot-reload, (2) multi-stage concept resolution (embedding similarity + label/prefix search + LLM semantic matching), (3) class hierarchy and object property traversal for adjacency discovery, (4) unmapped concept handling with local IRI generation, and (5) admin API for OWL lifecycle management. The embedding index component requires a dual-backend abstraction (pgvector on PostgreSQL, FAISS on SQLite) consistent with Phase 1's database abstraction pattern.

**Primary recommendation:** Replicate folio-enrich's OWLUpdateManager pattern (async singleton, ETag-based freshness, idle-wait-then-swap) and folio-mapper's domain-aware search expansions. Use sentence-transformers for local embedding with configurable cloud fallback. All data models use FOLIO IRIs as the canonical foreign key.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Replicate the FOLIO loading strategy from folio-enrich and folio-mapper: on startup, check the FOLIO repo on GitHub remote for freshness, download if stale, then load
- folio-enrich pattern: `ensure_owl_fresh()` with ETag-based HTTP conditional check at startup, then periodic background update task via `OWLUpdateManager`
- folio-mapper pattern: background thread warms `FOLIO()` at startup, `start_update_checker()` polls GitHub commits API with HEAD fallback when rate-limited
- Single shared FOLIO instance across all tenants (FOLIO is a public standard -- same for everyone)
- Configurable update check interval (default 24h), admin-configurable
- When OWL update arrives: wait for active analyses to finish (idle quiescence), then hot-swap the singleton FOLIO instance. Matches folio-enrich's `OWLUpdateManager` pattern
- Admin API endpoints for: check OWL status, trigger manual update, rollback to previous version. Health endpoint includes OWL cache status
- Configurable OWL branch/tag (default `main`), admin-configurable for deployments tracking specific FOLIO releases
- Build embedding index of FOLIO concept labels at startup (in addition to folio-python's built-in search)
- Dual vector store via DB abstraction: pgvector on PostgreSQL, FAISS on SQLite -- matches Phase 1's database abstraction pattern
- Embedding model configurable per-org (local vs cloud), continuing the per-org LLM config pattern from Phase 1
- Multi-stage pipeline: (1) Embedding similarity for fast candidate retrieval, (2) folio-python label/prefix search for exact matches, (3) LLM-powered semantic matching (`search_by_llm`) for ambiguous cases. Combined confidence score from all signals
- Search ALL FOLIO branches -- not just Objectives, Areas of Law, Legal Authorities, and Jurisdictions. Full taxonomy: Actor/Player, Asset Type, Communication Modality, Document/Artifact, Engagement Attributes, Event, Financial Concepts and Metrics, Forums and Venues, Governmental Body, Industry and Market, Legal Entity, Location, Service, and all others
- When multiple concepts match: return ranked list with confidence scores (all above threshold). Downstream analysis considers top-N
- Confidence threshold: sensible default with org-configurable override
- Replicate folio-mapper's `LEGAL_TERM_EXPANSIONS` and `BRANCH_SIGNAL_WORDS` domain-aware expansion patterns, in addition to LLM handling natural language variation
- Use `parallel_search_by_llm` to search multiple FOLIO branches simultaneously
- Persist concept resolution results per-intake in the tenant DB: resolved FOLIO IRIs, confidence scores, matched text. Creates the fact-to-concept mapping table for Phase 4
- Traverse both class hierarchy (subClassOf/parentClassOf) AND OWL object properties for adjacency discovery
- Traverse all FOLIO object properties -- no curated subset
- Configurable traversal depth with sensible default (e.g., 2-3 hops), org-configurable override. Phase 5 does deeper exploration
- Use folio-python's `find_connections` for cross-branch relationship discovery (subject-predicate-object triples)
- Return graph structure (nodes + edges) preserving traversal path and relationship labels -- not flat list
- Persist concept graph per-intake in tenant DB for later visualization (Phase 9) and audit trail
- Structured unmapped record: original text, LLM-suggested category, confidence it's unmapped (not just low-confidence match), nearest FOLIO concept(s)
- Unmapped concepts participate fully in analysis pipeline -- equal footing with mapped concepts. FOLIO-06 requires this
- Local IRI namespace using folio-python's `generate_iri()` schema (UUID4 -> base64 alphanumeric -> `https://folio.openlegalstandard.org/{value}`), aligned with WebProtege IRI creation
- Org-configurable collection of unmapped concepts (default: collect). Admin can review aggregated unmapped concepts
- Admin can manually submit proposed concepts to the FOLIO repo for consideration (the GitHub submission workflow via feature branch/commits is deferred -- Phase 2 only collects and stores)
- For adjacency discovery on unmapped concepts: use LLM suggestions + nearest mapped FOLIO concept(s) to anchor traversal

### Claude's Discretion
- Exact confidence scoring formula for multi-stage matching
- Embedding model default choice
- Graph storage schema design (nodes/edges table structure)
- OWL update timeout and retry parameters
- Exact default traversal depth value
- Internal caching strategy for hot FOLIO queries

### Deferred Ideas (OUT OF SCOPE)
- GitHub submission workflow for unmapped concepts (feature branch + commit to FOLIO repo) -- collect and store in Phase 2, submission mechanism in a future phase or ontokit integration
- Embedding model management UI -- Phase 8 admin interface
- Per-org FOLIO branch filtering (restricting which branches an org searches) -- not needed now, all branches searched
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FOLIO-01 | System loads FOLIO ontology via folio-python and uses IRIs as canonical identifiers for all legal concepts | OWL loading singleton, ETag freshness, hot-reload, FOLIO class with IRI-based indexing |
| FOLIO-02 | System maps consumer facts to FOLIO Objectives (Claims, Defenses) via LLM + ontology matching | Multi-stage pipeline (embedding + label search + search_by_llm), LEGAL_TERM_EXPANSIONS, BRANCH_SIGNAL_WORDS |
| FOLIO-03 | System identifies applicable Areas of Law from FOLIO taxonomy | parallel_search_by_llm across all branches including Area of Law, get_areas_of_law() accessor |
| FOLIO-04 | System identifies applicable Legal Authorities types from FOLIO taxonomy | parallel_search_by_llm, get_legal_authorities() accessor, branch signal words |
| FOLIO-05 | System determines applicable Jurisdictions from FOLIO Location branch | get_locations() accessor, Location branch search, country field on OWLClass |
| FOLIO-06 | System gracefully handles concepts not in FOLIO (flags as "unmapped" rather than dropping) | generate_iri() for local IRIs, unmapped concept record structure, full pipeline participation |
| FOLIO-07 | System uses FOLIO ontology relationships (OWL object properties) to discover adjacent legal concepts | get_subgraph, get_children, get_parents, find_connections, object_properties traversal, graph persistence |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| folio-python | 0.2.1 | FOLIO ontology loading, parsing, search, traversal | First-party library by ALEA Institute; canonical FOLIO API |
| folio-python[search] | 0.2.1 | rapidfuzz + marisa-trie + alea-llm-client search extras | Required for label search, prefix search, LLM search |
| alea-llm-client | >=0.3.0 | Multi-provider LLM access for semantic matching | Already in project; required by folio-python's search_by_llm |
| pgvector | 0.4.2 | PostgreSQL vector similarity search | Already in project; pgvector extension for embedding storage |
| faiss-cpu | 1.13.2 | SQLite-mode FAISS vector search fallback | Industry standard for in-memory vector search; SQLite backend |
| sentence-transformers | 5.3.0 | Local embedding model for concept label encoding | Standard embedding library; configurable model selection |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| httpx | >=0.28.0 | HTTP client for GitHub API freshness checks | Already in project; used by folio-python and OWL cache |
| lxml | >=5.2.2 | XML parsing for OWL validation | Transitive via folio-python; used for XML validation on download |
| numpy | (via sentence-transformers) | Vector operations for embedding similarity | Transitive dependency; used for cosine similarity computation |
| rapidfuzz | >=3.10.0 | Fuzzy string matching for label search | Via folio-python[search]; WRatio and partial_token_set_ratio |
| marisa-trie | >=1.2.0 | Prefix trie for efficient prefix search | Via folio-python[search]; compact trie over 18k+ labels |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| sentence-transformers (local) | OpenAI embeddings API | Lower latency vs. cloud dependency; local is default, cloud is org-configurable |
| FAISS (SQLite mode) | Annoy, hnswlib | FAISS is the ecosystem standard from folio-enrich; consistency trumps marginal perf |
| rapidfuzz (label search) | Levenshtein, thefuzz | folio-python uses rapidfuzz internally; no reason to diverge |

**Installation (new dependencies for Phase 2):**
```bash
cd backend
uv add "folio-python[search]>=0.2.1" "faiss-cpu>=1.13.0" "sentence-transformers>=5.0.0"
```

**Note:** `folio-python[search]` transitively installs `rapidfuzz`, `marisa-trie`, and `alea-llm-client`. The `alea-llm-client` and `pgvector` are already in pyproject.toml from Phase 1.

## Architecture Patterns

### Recommended Project Structure
```
backend/app/
  services/
    folio/
      __init__.py              # Re-exports: FolioService, OWLUpdateManager
      folio_service.py         # Singleton FOLIO loader, concept resolution pipeline
      owl_cache.py             # ETag-based freshness check, atomic download, rollback
      owl_updater.py           # OWLUpdateManager: background check, idle-wait, hot-swap
      concept_resolver.py      # Multi-stage resolution pipeline
      adjacency.py             # Graph traversal and adjacency discovery
      unmapped.py              # Unmapped concept handling, local IRI generation
      term_expansions.py       # LEGAL_TERM_EXPANSIONS, BRANCH_SIGNAL_WORDS (ported from folio-mapper)
    embedding/
      __init__.py
      service.py               # EmbeddingService: encode, search, dual-backend abstraction
      providers/
        __init__.py
        local.py               # sentence-transformers provider
        cloud.py               # OpenAI/other cloud embedding provider
      backends/
        __init__.py
        pgvector_backend.py    # PostgreSQL pgvector storage
        faiss_backend.py       # FAISS in-memory storage (SQLite mode)
  models/
    folio_concepts.py          # ConceptMapping, ConceptGraphNode, ConceptGraphEdge, UnmappedConcept
  routers/
    folio_admin.py             # Admin API: OWL status, trigger update, rollback, unmapped review
```

### Pattern 1: Singleton FOLIO Service with Hot-Reload
**What:** A module-level singleton that loads the FOLIO ontology on first access, with thread-safe hot-swap capability when OWL updates arrive.
**When to use:** Always -- single shared FOLIO instance across all tenants.
**Example:**
```python
# Source: folio-mapper/backend/app/services/folio_service.py (adapted)
import threading
from folio import FOLIO, FOLIO_TYPE_IRIS, FOLIOTypes

_folio_instance: FOLIO | None = None
_folio_lock = threading.Lock()

def get_folio() -> FOLIO:
    """Get the cached FOLIO singleton. Loads from GitHub on first call."""
    global _folio_instance
    if _folio_instance is not None:
        return _folio_instance
    with _folio_lock:
        if _folio_instance is not None:
            return _folio_instance
        _folio_instance = FOLIO(github_repo_branch="main")
        return _folio_instance

def reload_folio(new_instance: FOLIO) -> None:
    """Hot-swap the FOLIO singleton. Thread-safe."""
    global _folio_instance
    with _folio_lock:
        _folio_instance = new_instance
```

### Pattern 2: ETag-Based OWL Cache with Atomic Write
**What:** Before loading FOLIO at startup, check GitHub for freshness via HTTP conditional request (If-None-Match). Download only if stale, validate XML, then atomic write with one-version rollback.
**When to use:** Every startup and periodic background check.
**Example:**
```python
# Source: folio-enrich/backend/app/services/folio/owl_cache.py (adapted)
def ensure_owl_fresh() -> None:
    """Check cached OWL freshness; download if stale."""
    meta = _load_metadata()
    headers = {}
    if meta.get("etag") and _CACHE_FILE.exists():
        headers["If-None-Match"] = meta["etag"]

    head_resp = httpx.Client(timeout=30).head(_OWL_URL, headers=headers)
    if head_resp.status_code == 304:
        return  # Up to date

    # Download, validate XML, atomic write with rollback
    content = httpx.Client(timeout=30).get(_OWL_URL).content
    etree.fromstring(content)  # Validate XML

    if _CACHE_FILE.exists():
        _CACHE_FILE.rename(_PREVIOUS_FILE)  # One-version backup
    tmp = _CACHE_FILE.with_suffix(".owl.tmp")
    tmp.write_bytes(content)
    tmp.rename(_CACHE_FILE)
```

### Pattern 3: Multi-Stage Concept Resolution Pipeline
**What:** Three-stage resolution: (1) embedding similarity for fast candidate retrieval, (2) folio-python label/prefix search for exact/fuzzy matches, (3) LLM semantic matching for ambiguous cases. Combined confidence score from all signals.
**When to use:** When mapping consumer narrative text to FOLIO concepts.
**Example:**
```python
# Concept resolution pipeline (new for alea-intake)
async def resolve_concepts(
    text: str,
    folio: FOLIO,
    embedding_service: EmbeddingService,
    llm: BaseAIModel,
    config: ConceptResolutionConfig,
) -> list[ResolvedConcept]:
    # Stage 1: Embedding similarity (fast, broad recall)
    embedding_candidates = await embedding_service.search(text, top_k=20)

    # Stage 2: Label/prefix search (exact + fuzzy matching)
    label_matches = folio.search_by_label(text, limit=10)
    prefix_matches = folio.search_by_prefix(text) if len(text) >= 3 else []

    # Stage 3: LLM semantic matching (for ambiguous/complex text)
    if not high_confidence_match(embedding_candidates, label_matches):
        llm_results = await folio.parallel_search_by_llm(
            text, limit=10, include_reason=True
        )

    # Combine scores from all stages
    return merge_and_score(embedding_candidates, label_matches, llm_results, config)
```

### Pattern 4: Dual-Backend Embedding Store
**What:** Abstract the vector store behind an interface that uses pgvector on PostgreSQL and FAISS on SQLite, matching Phase 1's database abstraction pattern.
**When to use:** For all embedding storage and similarity search operations.
**Example:**
```python
# Embedding backend abstraction
class EmbeddingBackend(Protocol):
    async def upsert(self, iri: str, vector: list[float], metadata: dict) -> None: ...
    async def search(self, query_vector: list[float], top_k: int) -> list[SearchResult]: ...
    async def delete_all(self) -> None: ...

class PgVectorBackend(EmbeddingBackend):
    """Uses pgvector extension on PostgreSQL."""
    ...

class FAISSBackend(EmbeddingBackend):
    """Uses FAISS in-memory index with pickle persistence for SQLite mode."""
    ...
```

### Pattern 5: Graph Persistence for Concept Relationships
**What:** Store concept graph nodes and edges per-intake in tenant DB, preserving traversal paths and relationship labels for Phase 9 visualization.
**When to use:** After adjacency discovery, persist the graph for each intake.
**Example:**
```python
# Tenant-schema models for concept graph
class ConceptGraphNode(TenantBase):
    __tablename__ = "concept_graph_nodes"
    id: Mapped[int] = mapped_column(primary_key=True)
    intake_id: Mapped[int] = mapped_column(ForeignKey("intakes.id"))
    iri: Mapped[str] = mapped_column(String(512))         # Full FOLIO IRI
    label: Mapped[str] = mapped_column(String(512))
    branch: Mapped[str | None] = mapped_column(String(100))
    is_unmapped: Mapped[bool] = mapped_column(default=False)
    confidence: Mapped[float | None] = mapped_column()
    metadata_json: Mapped[dict | None] = mapped_column(JSON)

class ConceptGraphEdge(TenantBase):
    __tablename__ = "concept_graph_edges"
    id: Mapped[int] = mapped_column(primary_key=True)
    intake_id: Mapped[int] = mapped_column(ForeignKey("intakes.id"))
    source_iri: Mapped[str] = mapped_column(String(512))
    target_iri: Mapped[str] = mapped_column(String(512))
    relationship: Mapped[str] = mapped_column(String(256))  # e.g., "rdfs:subClassOf", property label
    traversal_depth: Mapped[int] = mapped_column(default=0)
```

### Anti-Patterns to Avoid
- **Loading FOLIO per-request:** FOLIO is ~18MB XML with 18k+ classes. Load once as singleton, never per-request. Parse time is ~2-5 seconds.
- **Blocking the event loop with FOLIO operations:** All FOLIO operations (loading, parsing, search_by_label) are synchronous. Always use `run_in_executor` for these in async contexts.
- **Searching only 4-5 branches:** The CONTEXT.md explicitly states ALL 24 FOLIO branches must be searched. Do not filter to just Objectives, Areas of Law, Legal Authorities, and Jurisdictions.
- **Dropping unmapped concepts:** FOLIO-06 requires unmapped concepts participate fully in the analysis pipeline. Never silently discard them.
- **Custom IRI schemes:** Use folio-python's `generate_iri()` which produces `https://folio.openlegalstandard.org/{base64_alphanumeric}` -- aligned with WebProtege. Do not invent a separate namespace.
- **Flat concept lists instead of graphs:** The CONTEXT.md requires graph structure (nodes + edges) preserving traversal paths. Do not flatten to a simple list.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| OWL parsing | Custom XML parser for FOLIO.owl | `folio-python` FOLIO class | 18k+ classes with complex XML (restrictions, properties, triples); folio-python handles all edge cases |
| Fuzzy label matching | Custom Levenshtein/edit distance | `folio.search_by_label()` via rapidfuzz | WRatio scorer handles partial matches, token reordering; pre-indexed trie for prefix search |
| LLM-powered search | Custom prompt engineering for concept matching | `folio.search_by_llm()` and `parallel_search_by_llm()` | Handles prompt formatting, JSON schema, result parsing, deduplication, multi-branch parallel gather |
| IRI generation | Custom UUID scheme | `folio.generate_iri()` | WebProtege-aligned format (UUID4 -> base64 alphanumeric), uniqueness check against existing IRIs |
| IRI normalization | Custom URL parsing | `FOLIO.normalize_iri()` | Handles legacy SOLI URLs, folio: prefix, lmss: prefix, bare hashes, full URLs |
| GitHub freshness check | Custom HTTP polling | Adapted `ensure_owl_fresh()` from folio-enrich | ETag-based conditional requests, XML validation, atomic write, rollback support |
| Domain-aware search expansion | Custom NLP pipeline | Ported `LEGAL_TERM_EXPANSIONS` and `BRANCH_SIGNAL_WORDS` from folio-mapper | Battle-tested mappings of legal terms to FOLIO branch signal words |

**Key insight:** The folio-python library and sibling projects (folio-enrich, folio-mapper) provide mature, tested implementations for nearly every capability this phase needs. The primary engineering work is assembling these patterns into a cohesive service layer with the multi-stage pipeline and dual-backend embedding store.

## Common Pitfalls

### Pitfall 1: FOLIO Loading Blocks Startup
**What goes wrong:** `FOLIO()` constructor downloads and parses an ~18MB OWL file synchronously. If called in the FastAPI lifespan without threading, it blocks the event loop for 3-10 seconds.
**Why it happens:** folio-python's `FOLIO.__init__` is synchronous -- it calls `load_owl()` and `parse_owl()` inline.
**How to avoid:** Run `FOLIO()` in `run_in_executor` during lifespan startup. Pre-ensure freshness via `ensure_owl_fresh()` in executor first, then construct FOLIO instance.
**Warning signs:** Startup timeouts, unresponsive health endpoint during boot.

### Pitfall 2: LLM Search Rate Limits
**What goes wrong:** `parallel_search_by_llm` fires one LLM API call per FOLIO branch (24 branches). With rate-limited providers this can cause 429 errors or extreme latency.
**Why it happens:** `asyncio.gather` across 24 search sets sends 24 concurrent LLM requests.
**How to avoid:** Use a semaphore to limit concurrent LLM calls. Consider searching only branches with embedding-stage candidates above a threshold. Cache results for common queries.
**Warning signs:** LLM API 429 responses, concept resolution taking >30 seconds.

### Pitfall 3: Hot-Swap Race Conditions
**What goes wrong:** Hot-swapping the FOLIO singleton while a concept resolution pipeline is mid-execution causes inconsistent state (e.g., IRI lookup against the wrong instance).
**Why it happens:** The singleton reference is replaced atomically, but in-flight operations hold references to the old instance's data structures.
**How to avoid:** Follow folio-enrich's OWLUpdateManager pattern: wait for active analyses to reach idle state before swapping. The old instance stays in memory until all references are released.
**Warning signs:** KeyError on IRI lookups after an update, inconsistent graph traversal results.

### Pitfall 4: Embedding Index Stale After OWL Update
**What goes wrong:** After a FOLIO OWL update adds/removes concepts, the embedding index still has the old concept set, causing missed matches or phantom results.
**Why it happens:** The embedding index is built at startup but not automatically rebuilt on hot-swap.
**How to avoid:** OWLUpdateManager must explicitly rebuild the embedding index after hot-swapping FOLIO. Both folio-enrich and folio-mapper do this.
**Warning signs:** Concepts present in FOLIO but not found by embedding search; deleted concepts still appearing in results.

### Pitfall 5: SQLite + FAISS vs PostgreSQL + pgvector Behavioral Differences
**What goes wrong:** FAISS uses L2 distance by default while pgvector can use cosine similarity. Different distance metrics yield different rankings.
**Why it happens:** Backend implementations use different default distance functions.
**How to avoid:** Normalize all embeddings to unit vectors and use cosine similarity (or inner product on normalized vectors) in both backends. FAISS `IndexFlatIP` on normalized vectors = cosine similarity. pgvector's `<=>` operator = cosine distance.
**Warning signs:** Same query returning different top-K results on PostgreSQL vs SQLite.

### Pitfall 6: Excessive Traversal Depth
**What goes wrong:** With 18k+ classes and dense hierarchy, traversal depth > 3 can explode combinatorially, returning thousands of concepts and taking seconds.
**Why it happens:** FOLIO has branches with 8+ levels of depth. Unrestricted traversal visits the entire subtree.
**How to avoid:** Default traversal depth of 2 hops. Configurable per-org. folio-python's DEFAULT_SEARCH_MAX_DEPTH is 2. Phase 5 does deeper exploration.
**Warning signs:** Adjacency discovery returning >500 concepts; response times >5 seconds.

## Code Examples

### Loading FOLIO at Startup (Lifespan Integration)
```python
# Source: adapted from folio-enrich/backend/app/main.py lifespan pattern
from contextlib import asynccontextmanager
import asyncio
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan with FOLIO loading and update checker."""
    from app.services.folio.owl_cache import ensure_owl_fresh
    from app.services.folio.folio_service import get_folio
    from app.services.folio.owl_updater import OWLUpdateManager
    from app.services.embedding.service import EmbeddingService

    loop = asyncio.get_event_loop()

    # Step 1: Ensure OWL cache is fresh
    await loop.run_in_executor(None, ensure_owl_fresh)

    # Step 2: Load FOLIO singleton
    folio = await loop.run_in_executor(None, get_folio)

    # Step 3: Build embedding index
    emb_service = EmbeddingService.get_instance()
    await loop.run_in_executor(None, emb_service.build_index, folio)

    # Step 4: Start periodic update checker
    update_manager = OWLUpdateManager.get_instance()
    update_task = asyncio.create_task(_periodic_owl_check(update_manager))

    # Existing startup: engine init, etc.
    from app.db.engine import get_engine
    get_engine()

    yield

    # Shutdown
    update_task.cancel()
    from app.db.engine import dispose_engine
    await dispose_engine()
```

### Concept Resolution with Multi-Stage Pipeline
```python
# Source: new for alea-intake, combining folio-python APIs
from folio import FOLIO, OWLClass
from dataclasses import dataclass

@dataclass
class ResolvedConcept:
    iri: str
    label: str
    branch: str
    confidence: float
    source: str  # "embedding", "label_match", "llm", "combined"
    matched_text: str
    is_unmapped: bool = False

async def resolve_text_to_concepts(
    text: str,
    folio: FOLIO,
    embedding_svc,
    config: dict,
) -> list[ResolvedConcept]:
    # Apply domain-aware term expansions
    expanded_queries = expand_legal_terms(text)

    # Stage 1: Embedding similarity (broad recall)
    emb_results = await embedding_svc.search(text, top_k=20)

    # Stage 2: Label + prefix search (exact/fuzzy)
    label_results = []
    for query in [text] + expanded_queries:
        label_results.extend(folio.search_by_label(query, limit=10))

    # Stage 3: LLM semantic (if no high-confidence match yet)
    llm_results = []
    if not any(r.confidence > config.get("high_confidence_threshold", 0.85)
               for r in merge_candidates(emb_results, label_results)):
        llm_results = await folio.parallel_search_by_llm(
            text, limit=10, include_reason=True
        )

    # Combine and score
    return combine_and_rank(emb_results, label_results, llm_results, config)
```

### Adjacency Discovery with Graph Persistence
```python
# Source: folio-python graph.py find_connections + get_children/get_parents
from folio import FOLIO, OWLClass, OWLObjectProperty

def discover_adjacent_concepts(
    folio: FOLIO,
    concept_iri: str,
    max_depth: int = 2,
) -> dict:
    """Discover adjacent concepts via hierarchy and object properties."""
    nodes = []
    edges = []

    # Hierarchy traversal (subClassOf / parentClassOf)
    children = folio.get_children(concept_iri, max_depth=max_depth)
    parents = folio.get_parents(concept_iri, max_depth=max_depth)

    for child in children:
        nodes.append({"iri": child.iri, "label": child.label})
        edges.append({
            "source": concept_iri, "target": child.iri,
            "relationship": "rdfs:subClassOf", "depth": 1,
        })

    # Object property traversal via find_connections
    connections = folio.find_connections(concept_iri)
    for subject, prop, obj in connections:
        nodes.append({"iri": obj.iri, "label": obj.label})
        edges.append({
            "source": subject.iri, "target": obj.iri,
            "relationship": prop.label, "depth": 1,
        })

    return {"nodes": deduplicate(nodes), "edges": edges}
```

### Unmapped Concept Handling
```python
# Source: folio-python generate_iri() + new unmapped handling
from folio import FOLIO

@dataclass
class UnmappedConcept:
    local_iri: str
    original_text: str
    suggested_branch: str | None
    unmapped_confidence: float  # Confidence it's genuinely unmapped
    nearest_concepts: list[ResolvedConcept]  # Closest FOLIO matches

async def handle_unmapped(
    text: str,
    folio: FOLIO,
    low_confidence_matches: list[ResolvedConcept],
    llm,
) -> UnmappedConcept:
    """Create structured unmapped record with local IRI."""
    local_iri = folio.generate_iri()

    # LLM suggests which branch this concept would belong to
    suggested_branch = await llm_suggest_branch(text, llm)

    return UnmappedConcept(
        local_iri=local_iri,
        original_text=text,
        suggested_branch=suggested_branch,
        unmapped_confidence=compute_unmapped_confidence(low_confidence_matches),
        nearest_concepts=low_confidence_matches[:3],
    )
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| SOLI (SALI LMSS) | FOLIO (Federated Open Legal Information Ontology) | 2024 rebrand | All IRIs now use `folio.openlegalstandard.org`; folio-python handles legacy `soli:` prefix normalization |
| folio-python 0.1.x | folio-python 0.2.x | Recent | Added `parallel_search_by_llm`, `find_connections`, `generate_iri`, configurable branches |
| Single-branch search | Multi-branch parallel search | folio-python 0.2.0 | `parallel_search_by_llm` uses `asyncio.gather` across branch search sets |
| Manual OWL download | ETag-based conditional fetch | folio-enrich pattern | Only downloads ~18MB when content actually changed; saves bandwidth/time |
| Default branch "2.0.0" | Configurable branch | folio-python config | `DEFAULT_GITHUB_REPO_BRANCH = "2.0.0"` in folio-python config.py; alea-intake should default to "main" per CONTEXT.md |

**Important version note:** folio-python's `config.py` sets `DEFAULT_GITHUB_REPO_BRANCH = "2.0.0"` but the CONTEXT.md decision specifies defaulting to `"main"`. The FolioService must explicitly pass `github_repo_branch="main"` (or admin-configured value) when constructing the FOLIO instance, overriding the library default.

**Deprecated/outdated:**
- `soli:` IRI prefix: Legacy from SALI LMSS era. `FOLIO.normalize_iri()` handles backward compatibility.
- `lmss:` IRI prefix: Even older legacy. Also handled by normalize_iri().

## Open Questions

1. **Embedding model size vs. quality tradeoff**
   - What we know: sentence-transformers offers models from 22M params (all-MiniLM-L6-v2, 384d) to 335M params (all-mpnet-base-v2, 768d). Legal domain models exist but are less common.
   - What's unclear: Which model gives best legal concept matching accuracy at acceptable latency.
   - Recommendation: Default to `all-MiniLM-L6-v2` (fast, small, 384d) for local deployments. Allow org-configurable override. Cloud embedding (OpenAI text-embedding-3-small) as alternative. The exact model is at Claude's discretion per CONTEXT.md.

2. **Confidence scoring formula**
   - What we know: Three signal sources (embedding similarity 0-1, label match 0-100, LLM relevance 1-10) need to be combined into a single confidence score.
   - What's unclear: Optimal weighting between sources.
   - Recommendation: Normalize all scores to 0.0-1.0 range. Weighted combination: embedding 0.3, label 0.3, LLM 0.4 (LLM weighted higher for semantic accuracy). Threshold default 0.5. This is at Claude's discretion per CONTEXT.md.

3. **Active analysis tracking for idle-wait**
   - What we know: OWLUpdateManager needs to wait for active analyses to finish before hot-swap. Phase 2 does not build the full analysis pipeline (that's Phase 4).
   - What's unclear: How to track "active analyses" before Phase 4 exists.
   - Recommendation: Implement a simple active-analysis counter (AtomicInteger or asyncio Lock-guarded counter) that Phase 4 will increment/decrement. In Phase 2, the counter is always 0, so hot-swap proceeds immediately.

4. **Intake model dependency**
   - What we know: ConceptMapping, ConceptGraphNode, ConceptGraphEdge all reference an `intake_id` foreign key. But the Intake model doesn't exist yet (Phase 3 creates it).
   - What's unclear: How to define these models without the Intake table.
   - Recommendation: Define the FK as a plain Integer column (no SQLAlchemy ForeignKey constraint) with a comment noting Phase 3 will add the Intake model. Or create a minimal Intake stub model in Phase 2 that Phase 3 extends.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio 0.24.x |
| Config file | `backend/pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `cd backend && python -m pytest tests/ -x -q --timeout=30` |
| Full suite command | `cd backend && python -m pytest tests/ -v --timeout=60` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FOLIO-01 | Load FOLIO ontology, IRI canonical identifiers | integration | `pytest tests/test_folio_service.py::test_folio_loads -x` | Wave 0 |
| FOLIO-01 | OWL freshness check and cache | unit | `pytest tests/test_owl_cache.py -x` | Wave 0 |
| FOLIO-01 | Hot-reload with idle-wait | unit | `pytest tests/test_owl_updater.py -x` | Wave 0 |
| FOLIO-02 | Map facts to FOLIO Objectives | integration | `pytest tests/test_concept_resolver.py::test_resolve_objectives -x` | Wave 0 |
| FOLIO-03 | Identify Areas of Law | integration | `pytest tests/test_concept_resolver.py::test_resolve_areas_of_law -x` | Wave 0 |
| FOLIO-04 | Identify Legal Authorities | integration | `pytest tests/test_concept_resolver.py::test_resolve_legal_authorities -x` | Wave 0 |
| FOLIO-05 | Determine Jurisdictions | integration | `pytest tests/test_concept_resolver.py::test_resolve_jurisdictions -x` | Wave 0 |
| FOLIO-06 | Handle unmapped concepts | unit | `pytest tests/test_unmapped.py -x` | Wave 0 |
| FOLIO-07 | Traverse OWL relationships | integration | `pytest tests/test_adjacency.py -x` | Wave 0 |
| FOLIO-07 | Graph persistence | integration | `pytest tests/test_concept_graph.py -x` | Wave 0 |
| - | Embedding dual-backend | unit | `pytest tests/test_embedding_service.py -x` | Wave 0 |
| - | Admin OWL endpoints | integration | `pytest tests/test_folio_admin.py -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `cd backend && python -m pytest tests/ -x -q --timeout=30`
- **Per wave merge:** `cd backend && python -m pytest tests/ -v --timeout=60`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_folio_service.py` -- covers FOLIO-01 (loading, singleton, IRI access)
- [ ] `tests/test_owl_cache.py` -- covers FOLIO-01 (freshness check, download, rollback)
- [ ] `tests/test_owl_updater.py` -- covers FOLIO-01 (background update, hot-swap, idle-wait)
- [ ] `tests/test_concept_resolver.py` -- covers FOLIO-02, FOLIO-03, FOLIO-04, FOLIO-05 (multi-stage pipeline)
- [ ] `tests/test_unmapped.py` -- covers FOLIO-06 (unmapped handling, local IRI generation)
- [ ] `tests/test_adjacency.py` -- covers FOLIO-07 (hierarchy + property traversal)
- [ ] `tests/test_concept_graph.py` -- covers FOLIO-07 (graph node/edge persistence)
- [ ] `tests/test_embedding_service.py` -- covers embedding dual-backend abstraction
- [ ] `tests/test_folio_admin.py` -- covers admin API endpoints
- [ ] `tests/conftest.py` additions: FOLIO mock fixture, embedding service mock fixture

**Testing strategy for FOLIO-dependent tests:** The full FOLIO ontology requires a ~18MB download and 3-5 second parse. For unit tests, use a mock FOLIO instance with a small subset of classes (10-20). For integration tests that verify real ontology behavior, use a `@pytest.mark.integration` marker and allow longer timeouts. The conftest should provide both `mock_folio` (fast, no network) and `real_folio` (cached, network on first run) fixtures.

## Sources

### Primary (HIGH confidence)
- folio-python source code (local: `../folio-python/folio/graph.py`, `models.py`, `config.py`, `__init__.py`) -- Complete API surface verified by direct code reading
- folio-python pyproject.toml -- Version 0.2.1, dependency: `folio-python[search]` includes rapidfuzz, marisa-trie, alea-llm-client
- folio-enrich source code (local: `../folio-enrich/backend/app/services/folio/owl_cache.py`, `owl_updater.py`, `../app/main.py`) -- ETag-based freshness, OWLUpdateManager, lifespan pattern
- folio-mapper source code (local: `../folio-mapper/backend/app/services/folio_service.py`, `owl_update_service.py`) -- Singleton loader, LEGAL_TERM_EXPANSIONS, BRANCH_SIGNAL_WORDS, GitHub commits API check
- alea-intake existing codebase (local) -- Phase 1 patterns: LLMService, OrganizationConfig, TenantBase/SharedBase, conftest.py

### Secondary (MEDIUM confidence)
- PyPI package versions verified via `pip index versions`: faiss-cpu 1.13.2, sentence-transformers 5.3.0
- folio-python config.py `DEFAULT_GITHUB_REPO_BRANCH = "2.0.0"` -- verified by direct code reading; alea-intake must override to "main"

### Tertiary (LOW confidence)
- Embedding model quality comparisons (all-MiniLM-L6-v2 vs all-mpnet-base-v2 for legal domain) -- based on general ML knowledge, not legal-domain-specific benchmarks

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries verified from source code; versions confirmed via PyPI
- Architecture: HIGH -- patterns directly adapted from production sibling projects (folio-enrich, folio-mapper)
- Pitfalls: HIGH -- identified from actual code patterns and known folio-python behavior
- Embedding strategy: MEDIUM -- dual-backend pattern is sound but optimal model choice for legal domain needs validation
- Confidence scoring formula: LOW -- proposed weighting is reasonable but unvalidated

**Research date:** 2026-03-22
**Valid until:** 2026-04-22 (30 days; folio-python is stable at 0.2.x)
