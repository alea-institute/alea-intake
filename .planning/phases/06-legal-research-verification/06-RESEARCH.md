# Phase 6: Legal Research & Verification - Research

**Researched:** 2026-04-04
**Domain:** Legal research tool integration, citation verification, knowledge base RAG, ALEA ecosystem
**Confidence:** HIGH (core architecture, existing codebase patterns) / MEDIUM (external API specifics, ALEA ecosystem evolution)

## Summary

Phase 6 replaces the existing `research_stub.py` with a full `ResearchStage` that queries pluggable legal research tools (CourtListener, Google Scholar, Westlaw, Clio Library, Midpage, Descrybe) via a dual-mode adapter architecture (MCP + HTTP), verifies all citations against known databases, integrates deeply with the ALEA Institute ecosystem (folio-mcp, folio-enrich, folio-python, folio-api), and provides per-org knowledge bases with RAG. The phase is large -- spanning adapter framework, 6+ tool integrations, a citation verification pipeline, folio-mcp LLM tool integration, folio-enrich pipeline reuse, and a full KB document lifecycle with FAISS/pgvector dual-backend.

The ALEA Institute GitHub organization contains 60+ repos. Of these, 8 are directly relevant to Phase 6: folio-mcp (MCP server for LLM agent ontology access), folio-enrich (document annotation pipeline), folio-python (ontology client, already installed), folio-api (REST API for ontology), alea-llm-client (LLM provider abstraction, already installed), kl3m-data-client (access to legal training data including Case Access Project opinions), folio-mapper (taxonomy alignment tool), and eyecite (used by folio-enrich for citation parsing). Notably, `folio-insights` does NOT exist as a separate repo or PyPI package -- the "insights" concept refers to the SECONDARY/PRACTICAL knowledge (advocacy tips, best practices, pitfalls) that will need to be modeled as a data layer within alea-intake itself, populated via folio-enrich annotations and LLM-generated content.

**Primary recommendation:** Build a ResearchToolAdapter ABC with MCPAdapter and HTTPAdapter implementations sharing a common ResearchResult Pydantic schema. Integrate folio-mcp as an MCP client using the `mcp` Python SDK (v1.27.0). Use httpx for all HTTP adapter calls. Use eyecite for citation string parsing/normalization. Reuse existing EmbeddingService for KB vector indexing and DocumentService for KB document extraction.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Dual-mode adapters: MCP + HTTP with unified ResearchToolAdapter ABC. `query()` method returns common ResearchResult schema. MCPAdapter wraps folio-mcp tool calls. HTTPAdapter wraps direct HTTP calls to CourtListener, Westlaw, etc. Both return the same schema.
- **D-02:** Platform-level tool registry AND org-level tool activation. Platform admin defines available tools globally with pre-registered adapters. Orgs bring their own tools by providing credentials via admin API. Free/open tools (CourtListener, Google Scholar) work out of the box. Commercial tools (Westlaw, Clio Library, Midpage, Descrybe) require org-provided API keys.
- **D-03:** All mentioned tools ship as adapter stubs in platform registry: CourtListener, Google Scholar (free, pre-configured), Westlaw, Clio Library, Midpage, Descrybe (require org credentials). Org admins can add any research database by providing adapter type + endpoint + credentials.
- **D-04:** ResearchStage replaces research_stub.py in the analysis orchestrator. Queries all org-configured tools in parallel (asyncio.gather), merges results, runs citation verification, stores ResearchAuthority records. Research results feed back into gap analysis for re-iteration -- research-discovered gaps generate new questions.
- **D-05:** Multi-source verification with confidence. Every authority citation checked against: (1) CourtListener/RECAP (case law), (2) congress.gov/state legislature sites (statutes), (3) folio-insights citation index if available. Multiple verifications increase confidence. Unverifiable citations flagged but included with "unverified -- could not confirm via [sources checked]" warning.
- **D-06:** Local citation cache (ResearchAuthority DB table) with live refresh. Store verified citations with: citation string, verification_status, verification_source, verified_at, jurisdiction, authority_type. Reuse across intakes. Cache returns immediate results; live API query runs in parallel for freshness. New/different results merged in.
- **D-07:** Researcher must survey ALL repos at github.com/alea-institute/ to identify integration opportunities for Phase 6. Known integrations: folio-insights (practical/secondary knowledge), folio-enrich (document annotation pipeline), folio-mcp (LLM agent tool), folio-api (REST API), folio-python (library). Other tools integrated as applicable.
- **D-08:** Research tools (cases, statutes, regulations) are PRIMARY authority for legal elements. folio-insights provides SECONDARY/PRACTICAL knowledge (advocacy tips, best practices, pitfalls, "don't speak when the judge is speaking"). Hierarchy: primary sources > secondary sources.
- **D-09:** folio-enrich pipeline reused (not just called as API) with two modes: (1) end-user-facing: backend pipeline only, annotations improve user experience invisibly; (2) org-facing: UI-visible annotations for precision/recall validation by org admins.
- **D-10:** folio-mcp integrated as LLM agent tool in the analysis orchestrator. LLM calls include folio-mcp tools in tool schema. When LLM needs ontology info (e.g., "elements of negligence in California"), it makes MCP tool calls to folio-mcp. Used during issue-spotting, exploration, and research stages.
- **D-11:** Dual-backend RAG reusing Phase 2 EmbeddingService (FAISS/pgvector). Per-org vector index for tenant isolation. Upload -> extract -> chunk -> FOLIO-tag -> embed -> index.
- **D-12:** Extended format support: PDF, DOCX, images (reuse Phase 3 extractors) + HTML and plain text.
- **D-13:** Semantic chunking with overlap (~500 tokens, 50-token overlap). Respect section boundaries (headings, paragraphs). FOLIO concept tagging on chunk headings -- headings containing FOLIO-tagged terms (e.g., "Complaint", "Lease", "Arrest") create strong retrieval signals. Dual retrieval: vector similarity + FOLIO IRI matching for ontology-grounded boosting.
- **D-14:** Full document lifecycle: upload -> extract -> chunk -> FOLIO-tag -> embed -> index. On update: re-extract, re-chunk, re-embed (incremental if possible). On delete: remove chunks from index + DB. Bulk import via ZIP/folder. Version tracking per document.
- **D-15:** Multi-signal relevance scoring. Deduplicate by citation string normalization. Score by: (1) relevance to claim elements, (2) recency (newer authorities weighted higher), (3) jurisdictional match (same jurisdiction > persuasive), (4) court level (Supreme > Appeals > Trial), (5) verification confidence. LLM re-ranks final list for presentation.
- **D-16:** FOLIO Legal Authority branch as canonical taxonomy: Case Law, Statutes, Regulations, Constitutional Provisions, Administrative Rulings, Court Rules, Executive Orders, Treaties, Model Codes, Restatements, Secondary Sources. Each type gets default weight (binding > persuasive > secondary). Jurisdiction + court level further refine weight.
- **D-17:** Output groups authorities by type (statutes first, then case law, then secondary). Each shows: binding vs persuasive for the relevant jurisdiction, verification status, relevance score. Binding authorities from correct jurisdiction highlighted.
- **D-18:** Per-org usage tracking with configurable budget caps. Track API call counts and estimated costs per org per tool. Monthly budget caps per tool -- when reached, tool disabled for remainder of period. Free tools exempt. Usage visible in admin dashboard.
- **D-19:** TTL cache per (query_hash, tool_name, jurisdiction) -- default 24h for case law, 7d for statutes. Cache returns immediate results; live API query runs in parallel for freshness. New/different results from live query merged in.

### Claude's Discretion
- Specific adapter implementation details for each research tool
- Citation string normalization algorithm (Bluebook format parsing)
- folio-enrich pipeline reuse architecture details
- KB chunk size tuning and overlap optimization
- MCP client implementation for folio-mcp tool calls
- Rate limiting implementation (token bucket, sliding window, etc.)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RESEARCH-01 | System queries pluggable legal research tools via MCP tool registry and HTTP adapters | D-01 adapter ABC + MCPAdapter/HTTPAdapter; folio-mcp v0.4.1 for MCP; httpx for HTTP; `mcp` SDK v1.27.0 for MCP client |
| RESEARCH-02 | Organizations configure which research tools they have access to | D-02/D-03 platform registry + org activation; OrganizationConfig settings pattern; admin API following screening_admin pattern |
| RESEARCH-03 | System integrates with folio-insights for advocacy knowledge | D-08 secondary knowledge; folio-insights NOT a separate repo -- model as InsightsService internally; populate via folio-enrich annotations + LLM |
| RESEARCH-04 | System integrates with folio-enrich for document annotation | D-09 folio-enrich pipeline reuse; available at github.com/alea-institute/folio-enrich (not PyPI); HTTP API at POST /enrich |
| RESEARCH-05 | For each identified claim, system researches required legal elements per jurisdiction | D-04 ResearchStage replaces research_stub; folio-mcp tools search_concepts/get_taxonomy_branch for element discovery; LLM re-ranks |
| RESEARCH-06 | System finds relevant case law, statutes, regulations, constitutional provisions | D-03/D-16 CourtListener API v4.3 for case law, authority type taxonomy from FOLIO Legal Authority branch |
| RESEARCH-07 | Ground truth verification: LLM suggestions verified against known databases | D-05 multi-source verification pipeline; CourtListener citations API; eyecite v2.7.6 for citation parsing |
| RESEARCH-08 | Each authority gets a verified/unverified flag with verification source | D-06 ResearchAuthority DB table with verification_status, verification_source, verified_at fields |
| RESEARCH-09 | Admin-configurable knowledge base with RAG over curated legal documents | D-11/D-13 dual-backend RAG via EmbeddingService; per-org FAISS/pgvector index; semantic chunking with FOLIO tagging |
| RESEARCH-10 | Organizations can upload custom documents to their knowledge base | D-12/D-14 extended format support; reuse DocumentService extractors; full lifecycle (upload/update/delete) |
| INTEGRATE-05 | folio-mcp integration for LLM agent tool-use during analysis | D-10 MCP client in orchestrator; `mcp` Python SDK for tool calls to folio-mcp; 12 tools available |

</phase_requirements>

## ALEA Institute Ecosystem Survey

**Survey date:** 2026-04-04
**Total repos found:** 60+
**Method:** `gh api orgs/alea-institute/repos --paginate`

### Directly Relevant to Phase 6 (INTEGRATE)

| Repo | Purpose | Integration Mode | Priority |
|------|---------|-----------------|----------|
| **folio-mcp** | MCP server exposing 12 FOLIO ontology tools for AI agents | MCP client calls from orchestrator | CRITICAL |
| **folio-enrich** | Multi-stage document annotation pipeline (18 stages, citations, entities, concepts) | HTTP API calls + pipeline pattern reuse | CRITICAL |
| **folio-python** | Python client for FOLIO ontology (already installed v0.3.3) | Direct library import (existing) | CRITICAL |
| **folio-api** | REST API at folio.openlegalstandard.org (public, open CORS) | HTTP fallback for MCP; concept lookups | HIGH |
| **alea-llm-client** | Multi-provider LLM abstraction (already installed v0.3.3) | Direct library import (existing) | HIGH |
| **kl3m-data-client** | Python client for KL3M legal datasets in S3 (Case Access Project opinions) | Potential supplementary data source | MEDIUM |
| **folio-mapper** | Maps external taxonomies to FOLIO concepts | Pattern reference for org KB FOLIO-tagging | LOW |
| **eyecite** | Legal citation parser (used by folio-enrich internally) | Direct use for citation normalization | HIGH |

### Reviewed but NOT Relevant to Phase 6

| Repo | Why Not |
|------|---------|
| folio-research | Empty repo (no code) |
| generative-folio | Not found / 404 on tree |
| folio-data-generator | FOLIO data generation for testing |
| folio-claude-plugin / folio-cursor-plugin | IDE plugins, not backend integration |
| kl3m-data / kl3m-data-api / kl3m-services | Training infrastructure, not runtime legal research |
| alea-preprocess / alea-preprocess-original | Data preprocessing for training |
| alea-graph | Knowledge graph management app (TypeScript) |
| alea-knowledge-graphs | No code (metadata only) |
| nupunkt / cheesecloth | NLP utilities (sentence boundary, text quality) |
| ontokit-api | OWL ontology curation API (separate concern) |
| laam | Linux kernel model experiment |
| All kl3m-* research/paper/tokenizer repos | Academic/research, not integration targets |

### Key Finding: folio-insights Does NOT Exist

**"folio-insights" is NOT a separate repository or PyPI package.** The CONTEXT.md D-07 lists it as a known integration, but no such repo exists in the ALEA org. The concept of "insights" (advocacy tips, best practices, pitfalls -- D-08) must be modeled as an internal data layer within alea-intake. Options:

1. **InsightsService** -- internal service that stores and retrieves secondary/practical knowledge per legal concept
2. **Populated by:** (a) folio-enrich metadata annotations, (b) LLM-generated practical knowledge, (c) admin-curated content in the org KB
3. **Indexed by:** FOLIO IRI so that when a claim maps to a FOLIO concept, associated insights are retrievable

This is a Claude's Discretion area per CONTEXT.md. **Recommendation:** Model insights as KB documents tagged with a special `source_type="insight"` in the knowledge base, allowing the same RAG infrastructure to serve both primary authorities and secondary insights.

## Standard Stack

### Core (New Dependencies)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| mcp | 1.27.0 | MCP client SDK for folio-mcp tool calls | Official Python SDK for Model Context Protocol |
| eyecite | 2.7.6 | Legal citation parsing and normalization | Industry standard; used by CourtListener, folio-enrich; tested on 55M+ citations |
| folio-mcp | 0.4.1 | MCP server for FOLIO ontology (subprocess/server) | ALEA ecosystem; 12 tools for concept search/traversal |

### Already Installed (Reuse)

| Library | Version | Purpose | Reuse Point |
|---------|---------|---------|-------------|
| folio-python | 0.3.3 | FOLIO ontology client | ConceptResolver, branch taxonomy, authority types |
| alea-llm-client | 0.3.3 | Multi-provider LLM client | LLMService for re-ranking, element research |
| httpx | 0.28.1 | Async HTTP client | All HTTP adapter calls (CourtListener, folio-enrich, etc.) |
| faiss-cpu | 1.13.0 | Vector similarity search | KB RAG index (FAISS backend) |
| sentence-transformers | 5.0.0 | Text embedding | KB document chunk embedding |
| sqlalchemy | 2.0.48+ | Async ORM | ResearchAuthority model, KB models |
| pydantic | 2.12.0+ | Schema validation | ResearchResult, adapter schemas |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| mcp SDK | Raw stdio/HTTP protocol | mcp SDK handles transport, serialization, reconnection |
| eyecite | Custom regex citation parser | eyecite covers 55M+ citation formats; custom would miss edge cases |
| httpx | aiohttp | httpx already installed, supports both sync/async, cleaner API |
| Token bucket rate limiter | Redis-based rate limiter | Token bucket is simpler for in-process; Redis needed only at scale |

**New dependency installation:**
```bash
pip install mcp>=1.27.0 eyecite>=2.7.6
```

**Version verification (2026-04-04):**
- mcp: 1.27.0 (latest on PyPI)
- eyecite: 2.7.6 (latest on PyPI, released June 2025)
- folio-mcp: 0.4.1 (latest on PyPI -- run as subprocess via `uvx folio-mcp`, NOT installed as dep)

## Architecture Patterns

### Recommended Project Structure

```
backend/app/
  services/
    research/
      __init__.py
      adapters/
        __init__.py
        base.py              # ResearchToolAdapter ABC, ResearchResult schema
        mcp_adapter.py       # MCPAdapter (wraps folio-mcp tool calls)
        http_adapter.py      # HTTPAdapter base for REST API tools
        courtlistener.py     # CourtListenerAdapter(HTTPAdapter)
        google_scholar.py    # GoogleScholarAdapter(HTTPAdapter)
        westlaw.py           # WestlawAdapter(HTTPAdapter) -- stub
        clio_library.py      # ClioLibraryAdapter(HTTPAdapter) -- stub
        midpage.py           # MidpageAdapter(HTTPAdapter) -- stub
        descrybe.py          # DescrybeAdapter(HTTPAdapter) -- stub
      tool_registry.py       # Platform tool registry + org activation
      research_stage.py      # ResearchStage (replaces research_stub.py)
      citation_verifier.py   # Multi-source citation verification pipeline
      citation_normalizer.py # eyecite-based Bluebook citation normalization
      result_ranker.py       # Multi-signal relevance scoring + LLM re-ranking
      insights_service.py    # Secondary/practical knowledge retrieval
      usage_tracker.py       # Per-org API usage tracking + budget caps
    knowledge_base/
      __init__.py
      kb_service.py          # KB document lifecycle (upload/update/delete)
      chunker.py             # Semantic chunking with overlap
      folio_tagger.py        # FOLIO concept tagging on chunk headings
      retriever.py           # Dual-signal retrieval (vector + FOLIO IRI)
      kb_admin_service.py    # Admin operations (bulk import, stats)
    folio_enrich/
      __init__.py
      enrich_client.py       # HTTP client for folio-enrich API
      pipeline_adapter.py    # Pipeline pattern reuse for in-process enrichment
    mcp/
      __init__.py
      folio_mcp_client.py    # MCP client wrapper for folio-mcp server
  models/
    research.py              # ResearchAuthority, ResearchToolConfig, ResearchUsage
    knowledge_base.py        # KBDocument, KBChunk, KBDocumentVersion
  routers/
    research_admin.py        # Admin endpoints for research tool config
    kb_admin.py              # Admin endpoints for KB management
```

### Pattern 1: ResearchToolAdapter ABC

**What:** Abstract base class for all research tool adapters with unified output schema.
**When to use:** Every external research tool integration.

```python
# backend/app/services/research/adapters/base.py
from abc import ABC, abstractmethod
from pydantic import BaseModel, Field
from enum import Enum

class AuthorityType(str, Enum):
    CASE_LAW = "case_law"
    STATUTE = "statute"
    REGULATION = "regulation"
    CONSTITUTIONAL = "constitutional"
    ADMINISTRATIVE_RULING = "administrative_ruling"
    COURT_RULE = "court_rule"
    EXECUTIVE_ORDER = "executive_order"
    TREATY = "treaty"
    MODEL_CODE = "model_code"
    RESTATEMENT = "restatement"
    SECONDARY_SOURCE = "secondary_source"

class ResearchResult(BaseModel):
    """Unified research result from any adapter."""
    citation: str
    title: str
    authority_type: AuthorityType
    jurisdiction: str | None = None
    court_level: str | None = None  # supreme, appeals, trial
    date_decided: str | None = None  # ISO date
    relevance_snippet: str | None = None
    full_text_url: str | None = None
    source_tool: str  # which adapter produced this
    raw_metadata: dict = Field(default_factory=dict)

class ResearchQuery(BaseModel):
    """Unified query to research tools."""
    claim_name: str
    elements: list[str] = Field(default_factory=list)
    jurisdiction: str | None = None
    authority_types: list[AuthorityType] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    date_after: str | None = None

class ResearchToolAdapter(ABC):
    """Base class for all research tool adapters."""
    tool_name: str
    requires_credentials: bool = False

    @abstractmethod
    async def query(self, research_query: ResearchQuery) -> list[ResearchResult]:
        """Execute a research query and return unified results."""
        ...

    @abstractmethod
    async def verify_citation(self, citation: str) -> dict:
        """Verify a citation string exists. Returns {verified, source, metadata}."""
        ...

    async def health_check(self) -> bool:
        """Check if the tool is accessible."""
        return True
```

### Pattern 2: MCP Client for folio-mcp

**What:** Wrap the `mcp` Python SDK to call folio-mcp tools from the analysis orchestrator.
**When to use:** When the LLM needs ontology information during analysis.

```python
# backend/app/services/mcp/folio_mcp_client.py
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

class FolioMCPClient:
    """MCP client for folio-mcp server."""

    def __init__(self, mode: str = "api"):
        # mode: "api" (default, calls public API) or "local" (local OWL)
        self._mode = mode
        self._session: ClientSession | None = None

    async def connect(self):
        """Start folio-mcp as subprocess and connect via stdio."""
        server_params = StdioServerParameters(
            command="uvx",
            args=["folio-mcp"] + (["--local"] if self._mode == "local" else []),
        )
        # The mcp SDK manages the subprocess lifecycle
        self._read, self._write = await stdio_client(server_params).__aenter__()
        self._session = await ClientSession(self._read, self._write).__aenter__()
        await self._session.initialize()

    async def search_concepts(self, query: str, limit: int = 10) -> list[dict]:
        result = await self._session.call_tool("search_concepts", {
            "query": query, "limit": limit
        })
        return result.content

    async def get_concept(self, iri: str) -> dict:
        result = await self._session.call_tool("get_concept", {"iri": iri})
        return result.content

    async def get_taxonomy_branch(self, branch: str, max_depth: int = 3) -> dict:
        result = await self._session.call_tool("get_taxonomy_branch", {
            "branch_name": branch, "max_depth": max_depth
        })
        return result.content

    async def close(self):
        if self._session:
            await self._session.__aexit__(None, None, None)
```

### Pattern 3: Citation Verification Pipeline

**What:** Multi-source citation verification with confidence scoring.
**When to use:** After research tools return results, before presentation.

```python
# Verification flow per citation:
# 1. Normalize citation string via eyecite
# 2. Check local cache (ResearchAuthority table)
# 3. If cached + fresh: return cached result immediately
# 4. In parallel: query verification sources
#    - CourtListener /api/rest/v4/search/?q={citation}&type=o
#    - CourtListener /api/rest/v4/opinions-cited/ for citation graph
# 5. Aggregate verification results
# 6. Update cache with new verification status
# 7. Return verified/unverified flag with sources checked
```

### Pattern 4: KB Dual-Signal Retrieval

**What:** Combine vector similarity with FOLIO IRI matching for ontology-grounded retrieval.
**When to use:** Knowledge base search during research stage.

```python
# Retrieval flow:
# 1. Embed query text via EmbeddingService
# 2. Vector similarity search over per-org index (top_k=20)
# 3. Extract FOLIO IRIs from query context (via ConceptResolver)
# 4. Boost chunks whose folio_iris overlap with query FOLIO IRIs
# 5. Re-rank combined results
# 6. Return top N chunks with provenance
```

### Anti-Patterns to Avoid

- **Synchronous external API calls:** All adapter calls MUST be async via httpx.AsyncClient. Never block the event loop.
- **Unbounded parallel queries:** Use asyncio.gather with return_exceptions=True and explicit timeouts. A slow/down tool should not block the entire research stage.
- **Storing API keys in plaintext:** Use the existing encryption service (AES-256-GCM) for org-provided credentials.
- **Monolithic ResearchStage:** Keep the stage thin -- delegate to adapters, verifier, ranker as separate services.
- **Tight coupling to folio-enrich internals:** Interact via HTTP API only. Do NOT import folio-enrich Python modules directly.
- **Global FAISS index for KB:** Each org MUST have its own index for tenant isolation. Use org_id namespacing.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Citation parsing | Custom regex for U.S. citations | eyecite v2.7.6 | 55M+ citation formats; Bluebook, vendors, reporters |
| MCP protocol handling | Raw JSON-RPC over stdio | mcp SDK v1.27.0 | Handles transport, serialization, tool discovery |
| Vector similarity search | Custom cosine similarity | FAISS/pgvector via EmbeddingService | Battle-tested, GPU-capable, already integrated |
| Document text extraction | Custom PDF/DOCX parsers | DocumentService (Phase 3) | Already supports PDF, DOCX, OCR |
| FOLIO concept matching | String matching on concept labels | ConceptResolver (Phase 2) | Multi-stage pipeline with embedding+label+LLM |
| LLM provider abstraction | Per-provider API calls | alea-llm-client via LLMService | Already handles OpenAI, Anthropic, Google, VLLM |
| HTTP request handling | urllib/requests | httpx (already installed) | Async support, connection pooling, timeouts |

**Key insight:** Phase 6 is an integration phase. The majority of heavy lifting is already built (EmbeddingService, DocumentService, ConceptResolver, LLMService) or available in the ALEA ecosystem (folio-mcp, folio-enrich, eyecite). The primary engineering challenge is the adapter framework, the orchestration of parallel tool queries, and the citation verification pipeline.

## Common Pitfalls

### Pitfall 1: CourtListener API Rate Limiting
**What goes wrong:** CourtListener enforces 5,000 queries/hour for authenticated users. Parallel research across multiple intakes can exhaust this quickly.
**Why it happens:** Each claim generates multiple queries (element research, citation verification, authority search).
**How to avoid:** Implement the TTL cache (D-19) aggressively. Deduplicate queries across claims in the same intake. Use query_hash as cache key. Batch citation verification calls.
**Warning signs:** 429 responses from CourtListener API.

### Pitfall 2: MCP Client Lifecycle Management
**What goes wrong:** folio-mcp runs as a subprocess. Leaked subprocesses accumulate if not properly cleaned up.
**Why it happens:** The mcp SDK uses context managers for subprocess lifecycle. If the orchestrator crashes or the session isn't properly closed, the subprocess persists.
**How to avoid:** Use async context managers properly. Register cleanup in FastAPI lifespan. Consider a singleton FolioMCPClient per application (not per request).
**Warning signs:** Orphaned `uvx folio-mcp` processes; increasing memory usage over time.

### Pitfall 3: FAISS Index Per-Org Isolation
**What goes wrong:** KB documents from one org appear in another org's search results.
**Why it happens:** FAISS is an in-memory index. Without explicit per-org namespacing, vectors from different orgs mix.
**How to avoid:** Maintain separate FAISS indices per org_id (file-backed, loaded on demand). For pgvector, use the existing tenant schema isolation.
**Warning signs:** Cross-tenant data leakage in KB search results.

### Pitfall 4: folio-enrich Pipeline Timeout
**What goes wrong:** folio-enrich runs 18 pipeline stages including multiple LLM calls. A single document enrichment can take 30-60 seconds.
**Why it happens:** The pipeline is thorough but slow -- parallel stages help, but LLM stages are inherently latency-bound.
**How to avoid:** Call folio-enrich asynchronously (fire-and-forget with polling). Don't block the research stage on enrichment results. Use the SSE streaming endpoint for progress.
**Warning signs:** Research stage timeout; slow intake processing.

### Pitfall 5: Citation Normalization Ambiguity
**What goes wrong:** The same case has multiple citation formats (official reporter, regional reporter, Westlaw, LexisNexis). Without normalization, the same authority appears multiple times.
**Why it happens:** Different research tools return different citation formats for the same case.
**How to avoid:** Use eyecite to parse all citations into a canonical form. Deduplicate by normalized citation before scoring. CourtListener's parallel citations API can resolve alternate citations.
**Warning signs:** Duplicate authorities in results; "5 cases found" that are actually 2 unique cases.

### Pitfall 6: Google Scholar Has No Official API
**What goes wrong:** Building a Google Scholar adapter that relies on HTML scraping.
**Why it happens:** Google Scholar has NO official API for programmatic access. Only third-party services (SerpAPI) provide API access, and they cost money.
**How to avoid:** The Google Scholar adapter should use SerpAPI (org-provided API key) or be clearly marked as requiring a third-party API service. Do not scrape Google Scholar directly.
**Warning signs:** 403/429 from Google; CAPTCHAs; terms of service violations.

### Pitfall 7: Commercial Tool Stubs Blocking Tests
**What goes wrong:** Tests fail because commercial tool adapters (Westlaw, Clio Library) try to make real API calls.
**Why it happens:** No mock/stub boundary in the adapter code.
**How to avoid:** Adapters accept an httpx.AsyncClient in constructor (dependency injection). Tests inject a mock client. The adapter ABC should be designed for testability from day one.
**Warning signs:** Tests requiring API keys; flaky tests due to network calls.

## Code Examples

### CourtListener Search API Call

```python
# Source: https://www.courtlistener.com/help/api/rest/search/
import httpx

async def search_courtlistener(
    query: str,
    token: str,
    jurisdiction: str | None = None,
) -> dict:
    """Search CourtListener for case law opinions."""
    async with httpx.AsyncClient() as client:
        params = {
            "q": query,
            "type": "o",  # opinions (case law)
        }
        if jurisdiction:
            params["court"] = jurisdiction
        resp = await client.get(
            "https://www.courtlistener.com/api/rest/v4/search/",
            params=params,
            headers={"Authorization": f"Token {token}"},
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.json()
```

### eyecite Citation Parsing

```python
# Source: https://github.com/freelawproject/eyecite
from eyecite import get_citations

text = "See Smith v. Jones, 123 F.3d 456, 789 (9th Cir. 2020)."
citations = get_citations(text)
for cite in citations:
    # cite.corrected_citation() -> normalized form
    # cite.groups -> reporter, volume, page
    print(f"Found: {cite}")
```

### MCP Client Tool Call (mcp SDK)

```python
# Source: https://github.com/modelcontextprotocol/python-sdk
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def call_folio_mcp_tool():
    server_params = StdioServerParameters(
        command="uvx",
        args=["folio-mcp"],
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            # List available tools
            tools = await session.list_tools()
            # Call search_concepts
            result = await session.call_tool(
                "search_concepts",
                {"query": "negligence", "limit": 5}
            )
```

### folio-enrich HTTP Integration

```python
# Source: https://github.com/alea-institute/folio-enrich
import httpx

ENRICH_BASE = "http://localhost:8731"

async def enrich_document(text: str) -> str:
    """Submit document for enrichment, return job_id."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{ENRICH_BASE}/enrich",
            json={"content": text},
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json()["job_id"]

async def get_enrichment_results(job_id: str) -> dict:
    """Poll for enrichment results."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{ENRICH_BASE}/enrich/{job_id}",
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json()
```

### folio-mcp Available Tools Reference

```
Tool                   Parameters              Purpose
----                   ----------              -------
search_concepts        query, limit=10         Fuzzy concept name search
search_definitions     query, limit=10         Search by definition content
query_concepts         text/structural filters Advanced multi-filter query
query_properties       label, domain, range    Search OWL object properties
get_concept            iri                     Full concept details
export_concept         iri, format             Export as markdown/JSON-LD/OWL
list_branches          (none)                  List all 24 taxonomy branches
get_taxonomy_branch    branch_name, max_depth  Extract branch concepts
get_children           iri, max_depth          Subordinate concepts
get_parents            iri, max_depth          Parent concepts
get_properties         (none)                  List all OWL properties
find_connections       subject, property, obj  Semantic triple lookup
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Solr-based CourtListener search | ElasticSearch v4.3 + semantic search | 2025 (v4.0-v4.3) | Better relevance, supports `semantic=true` param |
| Custom MCP JSON-RPC implementation | Official `mcp` Python SDK | 2024-2025 (v1.0+) | Standard transport, reconnection, tool discovery |
| SOLI ontology naming | Renamed to FOLIO | 2024-2025 | Same ontology, new name; update all references |
| Direct LLM calls for citation check | eyecite + CourtListener verification | Ongoing | Eliminates hallucinated citations |
| Single research source | Multi-tool parallel + merge + verify | Phase 6 (new) | Higher recall, confidence through cross-verification |

**Deprecated/outdated:**
- CourtListener API v3: Fully deprecated. Use v4.3 exclusively.
- CourtListener anonymous access: v4.3 requires authentication (401 for unauthenticated).
- SOLI name: Now FOLIO. All ALEA repos and APIs use "folio" naming.

## Open Questions

1. **folio-enrich Deployment Model**
   - What we know: folio-enrich is a standalone FastAPI app (not a PyPI package). It requires spaCy models, its own LLM config, and runs on port 8731.
   - What's unclear: Should alea-intake run its own folio-enrich instance, or connect to a shared deployment? Docker compose?
   - Recommendation: Configure folio-enrich URL as an env var (`FOLIO_ENRICH_URL`). For development, run as a separate Docker container. For production, deploy alongside alea-intake. Graceful degradation if unavailable.

2. **Midpage MCP vs HTTP**
   - What we know: Midpage launched an MCP connection in Feb 2026. They also have traditional API access.
   - What's unclear: Whether Midpage's MCP is publicly available or only via their platform integrations.
   - Recommendation: Build MidpageAdapter as HTTPAdapter initially. If their MCP becomes available, wrap it as MCPAdapter.

3. **CourtListener API Key Provisioning**
   - What we know: CourtListener requires authentication (free account). Rate limit is 5,000/hour.
   - What's unclear: Whether a platform-level CourtListener account is sufficient, or if each org needs their own.
   - Recommendation: Platform provides a default CourtListener API token for free-tier access. Orgs can override with their own token for higher limits.

4. **Westlaw/Clio Library API Access**
   - What we know: Thomson Reuters launched a developer portal with 137+ APIs. Clio Library is part of Clio Work enterprise.
   - What's unclear: Exact API endpoints, authentication flows, rate limits, pricing for Westlaw/Clio Library APIs.
   - Recommendation: Build adapter stubs with the correct interface. Populate implementation when API access is obtained. Mark as "credential required" in tool registry.

5. **folio-mcp Subprocess vs Long-Running**
   - What we know: folio-mcp can run as subprocess (`uvx folio-mcp`) or connect to public API.
   - What's unclear: Performance characteristics of subprocess spawning per request vs. a long-running MCP server.
   - Recommendation: Run folio-mcp as a singleton long-running subprocess started at application lifespan. Connect once, reuse session across requests.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12+ | All | Checked (3.13) | 3.13 | -- |
| folio-python | FOLIO ontology | Installed | 0.3.3 | -- |
| alea-llm-client | LLM calls | Installed | 0.3.3 | -- |
| httpx | HTTP adapters | Installed | 0.28.1 | -- |
| FAISS | KB vector index | Installed | 1.13.0 | -- |
| folio-enrich | Document annotation | NOT installed (git only) | -- | HTTP API to separate instance; graceful degradation |
| folio-mcp | MCP ontology tools | NOT installed | 0.4.1 on PyPI | `uvx folio-mcp` or `pip install folio-mcp` |
| mcp SDK | MCP client | NOT installed | 1.27.0 on PyPI | Must install |
| eyecite | Citation parsing | NOT installed | 2.7.6 on PyPI | Must install |
| CourtListener API | Case law search | External service | v4.3 | Free account required; rate limited |
| Docker | folio-enrich deployment | Available | -- | Manual process start |

**Missing dependencies with no fallback:**
- `mcp` SDK must be installed for INTEGRATE-05
- `eyecite` must be installed for citation normalization

**Missing dependencies with fallback:**
- folio-enrich: Can run as separate Docker container or skip gracefully
- folio-mcp: Can install via pip or run via uvx

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ with pytest-asyncio 0.24+ |
| Config file | `backend/pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `cd backend && python -m pytest tests/test_research*.py tests/test_kb*.py -x --timeout=30` |
| Full suite command | `cd backend && python -m pytest tests/ -x --timeout=30` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RESEARCH-01 | Pluggable tool adapters query via MCP + HTTP | unit | `pytest tests/test_research_adapters.py -x` | No -- Wave 0 |
| RESEARCH-02 | Org tool configuration via admin API | unit+integration | `pytest tests/test_research_admin.py -x` | No -- Wave 0 |
| RESEARCH-03 | folio-insights integration | unit | `pytest tests/test_insights_service.py -x` | No -- Wave 0 |
| RESEARCH-04 | folio-enrich integration | unit | `pytest tests/test_enrich_client.py -x` | No -- Wave 0 |
| RESEARCH-05 | Per-claim element research | unit | `pytest tests/test_research_stage.py -x` | No -- Wave 0 |
| RESEARCH-06 | Find case law, statutes, regulations | unit | `pytest tests/test_research_adapters.py::test_courtlistener -x` | No -- Wave 0 |
| RESEARCH-07 | Citation verification against known DBs | unit | `pytest tests/test_citation_verifier.py -x` | No -- Wave 0 |
| RESEARCH-08 | Verified/unverified flag per authority | unit | `pytest tests/test_research_models.py -x` | No -- Wave 0 |
| RESEARCH-09 | KB with RAG over curated documents | unit | `pytest tests/test_knowledge_base.py -x` | No -- Wave 0 |
| RESEARCH-10 | Org document upload to KB | unit+integration | `pytest tests/test_kb_admin.py -x` | No -- Wave 0 |
| INTEGRATE-05 | folio-mcp LLM tool-use | unit | `pytest tests/test_folio_mcp_client.py -x` | No -- Wave 0 |

### Sampling Rate

- **Per task commit:** `cd backend && python -m pytest tests/test_research*.py tests/test_kb*.py tests/test_citation*.py tests/test_enrich*.py tests/test_folio_mcp*.py tests/test_insights*.py -x --timeout=30`
- **Per wave merge:** `cd backend && python -m pytest tests/ -x --timeout=30`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_research_adapters.py` -- covers RESEARCH-01, RESEARCH-06
- [ ] `tests/test_research_admin.py` -- covers RESEARCH-02
- [ ] `tests/test_insights_service.py` -- covers RESEARCH-03
- [ ] `tests/test_enrich_client.py` -- covers RESEARCH-04
- [ ] `tests/test_research_stage.py` -- covers RESEARCH-05
- [ ] `tests/test_citation_verifier.py` -- covers RESEARCH-07
- [ ] `tests/test_research_models.py` -- covers RESEARCH-08
- [ ] `tests/test_knowledge_base.py` -- covers RESEARCH-09
- [ ] `tests/test_kb_admin.py` -- covers RESEARCH-10
- [ ] `tests/test_folio_mcp_client.py` -- covers INTEGRATE-05
- [ ] Framework install: `pip install mcp>=1.27.0 eyecite>=2.7.6` -- new dependencies

## External API Reference

### CourtListener API v4.3

| Endpoint | Method | Purpose | Auth |
|----------|--------|---------|------|
| `/api/rest/v4/search/?q={query}&type=o` | GET | Search case law opinions | Token |
| `/api/rest/v4/opinions/{id}/` | GET | Get specific opinion text | Token |
| `/api/rest/v4/clusters/{id}/` | GET | Get opinion cluster (case metadata) | Token |
| `/api/rest/v4/courts/` | GET | List courts | Token |
| `/api/rest/v4/opinions-cited/?citing_opinion={id}` | GET | Forward citations (what case cites) | Token |
| `/api/rest/v4/opinions-cited/?cited_opinion={id}` | GET | Backward citations (what cites case) | Token |

**Rate limit:** 5,000 requests/hour per authenticated user.
**Key response fields:** `results[].caseName`, `results[].citation`, `results[].court`, `results[].dateFiled`, `results[].snippet`
**Important:** Prefer `html_with_citations` field over `plain_text` for opinion text.

### folio-enrich API

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `POST /enrich` | POST | Submit document for enrichment (returns job_id) |
| `GET /enrich/{job_id}` | GET | Get enrichment results and status |
| `GET /enrich/{job_id}/stream` | GET (SSE) | Real-time progress streaming |
| `GET /enrich/{job_id}/export?format=json` | GET | Export results in various formats |
| `GET /concepts/{iri_hash}` | GET | Look up FOLIO concept |

**Default port:** 8731
**Key response:** Annotations with FOLIO IRIs, confidence scores, entity extraction, citation parsing.

### folio-mcp Tools

**Connection:** MCP over stdio (subprocess) or HTTP to folio.openlegalstandard.org
**12 tools available:** search_concepts, search_definitions, query_concepts, query_properties, get_concept, export_concept, list_branches, get_taxonomy_branch, get_children, get_parents, get_properties, find_connections
**3 prompts:** classify-document, identify-area-of-law, classify-entity

## Sources

### Primary (HIGH confidence)
- CourtListener REST API v4.3 documentation -- https://www.courtlistener.com/help/api/rest/
- CourtListener Case Law API -- https://www.courtlistener.com/help/api/rest/case-law/
- CourtListener Citations API -- https://www.courtlistener.com/help/api/rest/citations/
- CourtListener Search API -- https://www.courtlistener.com/help/api/rest/search/
- folio-mcp README (GitHub) -- https://github.com/alea-institute/folio-mcp
- folio-enrich README (GitHub) -- https://github.com/alea-institute/folio-enrich
- folio-api README (GitHub) -- https://github.com/alea-institute/folio-api
- folio-python README (GitHub) -- https://github.com/alea-institute/folio-python
- alea-llm-client README (GitHub) -- https://github.com/alea-institute/alea-llm-client
- MCP Python SDK (GitHub) -- https://github.com/modelcontextprotocol/python-sdk
- eyecite (GitHub) -- https://github.com/freelawproject/eyecite
- PyPI version checks: mcp 1.27.0, eyecite 2.7.6, folio-mcp 0.4.1, folio-python 0.3.3, alea-llm-client 0.3.3

### Secondary (MEDIUM confidence)
- kl3m-data-client README -- https://github.com/alea-institute/kl3m-data-client (Case Access Project data)
- folio-mapper README -- https://github.com/alea-institute/folio-mapper
- Midpage MCP announcement -- https://www.midpage.ai/integrations
- Descrybe legal research toolkit -- https://descrybe.ai/
- Westlaw API developer portal -- https://www.lawnext.com/2024/04/thomson-reuters-launches-developer-portal.html

### Tertiary (LOW confidence)
- Google Scholar API access via SerpAPI -- no official Google API exists; third-party only
- Clio Library API specifics -- Clio Work enterprise feature; exact API docs not publicly available
- Descrybe API specifics -- no public API documentation found
- Westlaw API endpoint specifics -- developer portal requires account; exact endpoints unverified

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all packages verified on PyPI with current versions; existing codebase patterns well-understood
- Architecture: HIGH -- adapter pattern follows established stage architecture; integration points well-documented in existing code
- External APIs: MEDIUM -- CourtListener well-documented; commercial tools (Westlaw, Clio Library, Midpage, Descrybe) have limited public API docs
- ALEA ecosystem: HIGH -- all 60+ repos surveyed; integration points for folio-mcp, folio-enrich, folio-python verified via README
- Pitfalls: HIGH -- based on direct API documentation review and known architectural constraints

**Research date:** 2026-04-04
**Valid until:** 2026-05-04 (30 days -- stable domain, external APIs may evolve)
