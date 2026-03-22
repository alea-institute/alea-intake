# Technology Stack

**Project:** ALEA Intake
**Researched:** 2026-03-22
**Overall confidence:** HIGH -- stack aligns with proven FOLIO ecosystem patterns and verified current library versions

## Recommended Stack

### Python Runtime

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| Python | >=3.12,<4.0 | Runtime | folio-python requires >=3.10; folio-enrich requires >=3.11; 3.12 gives performance improvements and better error messages; alea-llm-client supports up to 3.13; avoid 3.14 until ecosystem-wide support stabilizes | HIGH |
| uv | latest | Package management | Used by folio-python (see pyproject.toml `[tool.uv]`); faster than pip, deterministic lockfiles, workspace support for monorepo if needed | HIGH |

### Backend Framework

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| FastAPI | >=0.115.0 | Web framework | Mandated by PROJECT.md constraints; consistent with folio-enrich and folio-mapper backends; native SSE support added in 0.135.0; async-first design matches our streaming and concurrent jurisdiction analysis needs | HIGH |
| uvicorn[standard] | >=0.40.0 | ASGI server | Standard FastAPI deployment server; used by folio-enrich; `[standard]` extra includes uvloop + httptools for production performance; 0.40.0+ drops Python 3.9 (compatible with our >=3.12 target) | HIGH |
| Pydantic | >=2.8.2 | Data validation | Core to FastAPI; folio-python pins >=2.8.2; alea-llm-client uses pydantic; shared model definitions across the stack | HIGH |
| pydantic-settings | >=2.13.0 | Configuration | Used by folio-enrich (>=2.7.0); handles env vars, .env files, multi-environment configs; critical for deployment flexibility (cloud vs self-hosted) | HIGH |

### Database & ORM

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| SQLAlchemy | >=2.0.48 | ORM / query builder | Industry standard async ORM; supports both PostgreSQL (asyncpg) and SQLite (aiosqlite) through dialect abstraction; 2.0 style with native async support; abstracts the dual-database requirement cleanly | HIGH |
| Alembic | >=1.18.0 | Database migrations | Official SQLAlchemy migration tool; auto-generates migration scripts; supports both PostgreSQL and SQLite targets | HIGH |
| asyncpg | >=0.30.0 | PostgreSQL async driver | Fastest Python PostgreSQL driver; used as SQLAlchemy async dialect for the PostgreSQL backend | HIGH |
| aiosqlite | >=0.22.0 | SQLite async driver | Async bridge to sqlite3; used as SQLAlchemy async dialect for the lightweight/self-hosted backend; 0.22.0+ fixes connection lifecycle issues | HIGH |
| pgvector | >=0.4.2 | PostgreSQL vector search | SQLAlchemy integration for pgvector extension; enables RAG vector similarity search in PostgreSQL deployments; version 0.4.2 is current as of Dec 2025 | HIGH |
| faiss-cpu | >=1.8 | SQLite vector search | Used by folio-enrich for embedding search; provides vector similarity search for SQLite deployments where pgvector is unavailable; well-tested in the ecosystem | HIGH |

### LLM Integration

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| alea-llm-client | >=0.3.0 | Multi-provider LLM client | Mandated by PROJECT.md; ALEA Institute's unified LLM abstraction; supports OpenAI, Anthropic, Google, xAI, VLLM; minimal deps (httpx + pydantic only); provides complete/chat/json/pydantic/responses methods with sync and async variants; already used by folio-python for semantic matching | HIGH |
| httpx | >=0.28.0 | HTTP client | Core dependency of alea-llm-client and folio-python (>=0.27.2); used for all HTTP integrations (legal research APIs, CMS connectors, folio-enrich/folio-insights service calls); async support built-in | HIGH |

### Ontology & Knowledge

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| folio-python | >=0.2.1 | FOLIO ontology client | Direct library import for ontology queries (taxonomy navigation, concept search, IRI resolution); lightweight enough to embed; mandated integration pattern in PROJECT.md | HIGH |
| folio-python[search] | >=0.2.1 | Semantic search | Adds rapidfuzz + marisa-trie + alea-llm-client for fuzzy search and LLM-powered semantic matching against FOLIO concepts | HIGH |
| rdflib | >=7.0.0 | RDF/OWL processing | Used by folio-enrich for RDF export; needed for any direct OWL ontology manipulation, SPARQL queries, or ontology relationship traversal beyond what folio-python exposes | MEDIUM |
| lxml | >=5.2.2 | XML parsing | Core dependency of folio-python for OWL/XML parsing; already required transitively | HIGH |

**Do NOT use owlready2** -- Despite being a capable OWL library, folio-python is the canonical FOLIO interface. Owlready2 has known issues with punned entities that could conflict with FOLIO's ontology structure. Using both would create competing ontology access patterns.

### ASR / Voice Transcription

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| faster-whisper | >=3.8.0 | Local ASR (default) | 4x faster than OpenAI Whisper with same accuracy; CTranslate2 engine; CPU-compatible for self-hosted deployments; actively maintained (3.8.2 as of Mar 2026); pluggable as the local/free tier | HIGH |
| deepgram-sdk | >=6.0.0 | Cloud ASR (premium) | Best-in-class cloud ASR; real-time WebSocket streaming; Python SDK v6 current; pluggable as the accuracy/speed premium tier | MEDIUM |
| assemblyai | >=0.41.0 | Cloud ASR (alternative) | Secondary cloud ASR option; strong async support; pluggable as an alternative to Deepgram | LOW |

**ASR adapter pattern:** Define an `ASRProvider` protocol/ABC. Implementations for faster-whisper (local), Deepgram (cloud), and AssemblyAI (cloud). Organizations configure which provider they use. Start with faster-whisper as default (no API key required, works self-hosted).

### Real-Time Streaming

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| sse-starlette | >=2.0.0 | Server-Sent Events | Used by folio-enrich for streaming job updates; proven pattern in the ecosystem; FastAPI 0.135+ has native SSE but sse-starlette provides more control (disconnect detection, cooperative shutdown); use for LLM streaming, analysis progress, transcription progress | HIGH |
| WebSockets (Starlette native) | -- | Bidirectional streaming | Built into FastAPI/Starlette; use for voice transcription real-time sessions where bidirectional communication is needed (audio chunks up, partial transcripts down); no additional dependency needed | HIGH |

**Use SSE for:** LLM analysis streaming, progress updates, job status (server-to-client unidirectional).
**Use WebSockets for:** Real-time voice transcription sessions (bidirectional audio streaming).

### Security & Encryption

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| cryptography | >=44.0.0 | Field-level encryption | Industry-standard Python crypto library; Fernet symmetric encryption for PII field-level encryption at rest; AES-128-CBC + HMAC-SHA256 authentication; handles key rotation | HIGH |
| python-jose[cryptography] | >=3.3.0 | JWT tokens | JWT encoding/decoding for API authentication; uses cryptography backend | MEDIUM |
| passlib[bcrypt] | >=1.7.4 | Password hashing | bcrypt-based password hashing for user authentication | MEDIUM |
| python-multipart | >=0.0.9 | Form/file parsing | Required by FastAPI for file uploads (document upload, audio upload) | HIGH |

### Audit & Logging

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| structlog | >=24.0.0 | Structured logging | JSON-structured audit logs; contextual logging for tracing intake sessions through the analysis pipeline; supports log processors for PII redaction before logging | HIGH |
| Python stdlib `logging` | -- | Log infrastructure | structlog integrates with stdlib logging; no additional dependency | HIGH |

**Do NOT use** a separate audit logging library. Build audit logging as a SQLAlchemy event listener pattern -- every model change gets an audit record with timestamp, user, action, field-level diffs. This is a domain concern, not a library concern.

### Document Processing

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| PyMuPDF (pymupdf) | >=1.24.0 | PDF extraction | Used by folio-enrich; fast PDF text extraction with layout preservation | HIGH |
| python-docx | >=1.0.0 | Word doc extraction | Used by folio-enrich; extracts text from .docx uploads | HIGH |
| beautifulsoup4 | >=4.12.0 | HTML parsing | Used by folio-enrich; parses HTML content from web-sourced documents | HIGH |

### Testing

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| pytest | >=8.0 | Test framework | Used across all FOLIO projects; standard Python testing | HIGH |
| pytest-asyncio | >=0.25.0 | Async test support | Used by folio-enrich (>=0.25.0); required for testing async FastAPI endpoints | HIGH |
| httpx | (same) | API testing | FastAPI's `TestClient` uses httpx; async test client for integration tests | HIGH |

---

### Frontend Framework

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| React | ^19.0.0 | UI framework | Mandated by PROJECT.md; used by folio-mapper; React 19 stable since 19.2.1 (Dec 2025); >70% of new React projects in 2026 use React 19 | HIGH |
| TypeScript | ^5.7.0 | Type safety | Used by folio-mapper; type safety across API contracts (shared Pydantic <-> TypeScript types) | HIGH |
| Vite | ^6.0.0 | Build tool | Used by folio-mapper; 98% satisfaction rate (State of JS 2025); fast HMR, native ESM | HIGH |

### Frontend State & Data

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| Zustand | ^5.0.0 | Client state | Used by folio-mapper; minimal API, React 19 compatible; manages UI state (current intake step, form state, analysis progress) | HIGH |
| TanStack Query | ^5.94.0 | Server state | De facto React data fetching library; handles caching, background refetching, optimistic updates for API interactions; React version stays on v5 (v6 is Svelte-only) | HIGH |
| React Router | ^7.13.0 | Routing | Latest stable; non-breaking upgrade from v6; handles multi-step intake wizard routing, admin views, analysis views | HIGH |

### Frontend Visualization

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| @xyflow/react | ^12.10.0 | Graph visualization | Used by folio-mapper for taxonomy graphs; perfect for the "graph exploration" fact-mapping view showing connections between facts, issues, and legal authorities | HIGH |
| elkjs | ^0.11.0 | Graph layout | Used by folio-mapper alongside xyflow; automatic graph layout algorithms (layered, force-directed) for ontology relationship visualization | HIGH |

### Frontend Styling

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| Tailwind CSS | ^3.4.0 | Utility CSS | Use v3.4 (NOT v4) because folio-mapper uses v3.4 with PostCSS config pattern; v4 has major breaking changes (Rust engine, CSS-first config, removed class aliases); ecosystem consistency with folio-mapper outweighs v4's performance gains; migrate to v4 later when the ecosystem settles | HIGH |
| PostCSS | ^8.4.0 | CSS processing | Required by Tailwind v3; used by folio-mapper | HIGH |
| autoprefixer | ^10.4.0 | CSS prefixing | Required by Tailwind v3 PostCSS pipeline; used by folio-mapper | HIGH |

**Why NOT Tailwind v4:** Despite being the latest release, v4 fundamentally changes the configuration model (JS config -> CSS @theme), renames utility classes (bg-gradient-to-* -> bg-linear-to-*), and moves the PostCSS plugin to @tailwindcss/postcss. folio-mapper uses v3. Ecosystem consistency within the FOLIO project family matters more than chasing the newest version. Upgrade to v4 as a deliberate future migration once folio-mapper upgrades.

### Frontend Testing

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| Vitest | ^2.1.0 | Test runner | Used by folio-mapper; Vite-native, fast, compatible with Jest API | HIGH |
| @testing-library/react | ^16.1.0 | Component testing | Used by folio-mapper; tests components from user perspective | HIGH |
| @testing-library/jest-dom | ^6.6.0 | DOM assertions | Used by folio-mapper; custom matchers for DOM state | HIGH |
| jsdom | ^25.0.0 | DOM environment | Used by folio-mapper; provides DOM for Vitest | HIGH |

### Frontend Utilities

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| react-dropzone | ^14.3.0 | File upload UI | Used by folio-mapper; drag-and-drop file upload for documents and audio files | HIGH |

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not Alternative |
|----------|-------------|-------------|---------------------|
| LLM Client | alea-llm-client | LangChain / LlamaIndex | Mandated by project constraints; alea-llm-client is lightweight (2 deps) vs LangChain's massive dependency tree; already proven in folio-python ecosystem |
| LLM Client | alea-llm-client | litellm | alea-llm-client is the ALEA Institute's own library; litellm adds unnecessary dependency when we already have provider abstraction |
| ORM | SQLAlchemy 2.0 | Tortoise ORM | SQLAlchemy is the industry standard; Alembic migration support; dual-dialect (PostgreSQL + SQLite) is well-tested; larger ecosystem |
| ORM | SQLAlchemy 2.0 | SQLModel | SQLModel is a thin wrapper on SQLAlchemy by the same FastAPI author; adds abstraction without clear benefit for this project's complexity level; direct SQLAlchemy gives more control for the dual-database pattern |
| State Management | Zustand | Redux Toolkit | Zustand is simpler, less boilerplate, already used in folio-mapper; Redux's strict patterns are overkill for this application's state complexity |
| State Management | Zustand | Jotai | Zustand is already proven in the ecosystem; atomic state (Jotai) is useful but not needed here; Zustand handles both simple and complex state well |
| Data Fetching | TanStack Query | SWR | TanStack Query has richer feature set (mutations, infinite queries, devtools); better for the complex server state in intake analysis |
| Ontology | folio-python + rdflib | owlready2 | folio-python is the canonical FOLIO client; owlready2 has punned entity issues; mixing two OWL libraries creates confusion |
| Vector Search | pgvector + FAISS | ChromaDB / Weaviate | pgvector integrates directly into PostgreSQL (no separate service); FAISS is already used by folio-enrich; ChromaDB/Weaviate add infrastructure complexity for a self-hostable system |
| Vector Search | pgvector + FAISS | Qdrant | Same rationale; Qdrant is excellent but requires a separate service; pgvector is zero-additional-infra for PostgreSQL users |
| ASR Local | faster-whisper | OpenAI Whisper | faster-whisper is 4x faster with same accuracy; lower memory; CPU-viable for self-hosted |
| ASR Local | faster-whisper | whisperx | whisperx adds diarization and word timestamps via pyannote-audio; consider as a future upgrade if speaker identification is needed, but adds significant complexity and pyannote license constraints |
| Streaming | SSE + WebSocket | Socket.IO | Native SSE + WebSocket cover all needs; Socket.IO adds unnecessary abstraction and a JS client dependency; sse-starlette is already battle-tested in folio-enrich |
| CSS Framework | Tailwind v3 | Tailwind v4 | Breaking changes vs ecosystem consistency with folio-mapper; upgrade later as a coordinated effort |
| CSS Framework | Tailwind v3 | CSS Modules / vanilla CSS | Tailwind is already used in folio-mapper; utility-first approach enables rapid UI development |
| Build Tool | Vite | webpack / Turbopack | Vite is the standard for React projects in 2026; already used in folio-mapper; 98% satisfaction |
| Routing | React Router v7 | TanStack Router | React Router is the established choice; v7 is stable and mature; TanStack Router is newer and less proven at scale |
| Graph Viz | @xyflow/react | D3.js | xyflow provides higher-level React-native graph components; already used in folio-mapper; D3 requires more custom code for interactive node-based UIs |
| Graph Viz | @xyflow/react | vis.js / Cytoscape.js | xyflow has better React integration; already in the ecosystem; Cytoscape.js is more academic/bioinformatics-focused |
| Encryption | cryptography (Fernet) | PyCryptodome | cryptography is the modern standard; Fernet provides authenticated encryption out of the box; PyCryptodome is lower-level and easier to misuse |
| Logging | structlog | loguru | structlog produces machine-parseable JSON; better for audit trail requirements; integrates with stdlib logging ecosystem |
| Package Manager | pnpm | npm / yarn | folio-mapper uses pnpm; workspace support for monorepo packages; faster and more disk-efficient |

## Stack Architecture Notes

### Dual Database Abstraction Pattern

The dual PostgreSQL/SQLite requirement is the most architecturally significant stack decision. Use SQLAlchemy's dialect system with a repository pattern:

```python
# Abstract repository
class IntakeRepository(Protocol):
    async def save_session(self, session: IntakeSession) -> str: ...
    async def vector_search(self, embedding: list[float], k: int) -> list[Document]: ...

# PostgreSQL implementation uses pgvector for vector search
# SQLite implementation uses FAISS for vector search
# Both use SQLAlchemy for relational data
```

The vector search abstraction must be separate from the ORM layer because pgvector is a PostgreSQL extension (SQL-level) while FAISS is an in-process library (Python-level).

### LLM Provider Abstraction

alea-llm-client already handles multi-provider abstraction. The intake system wraps it with domain-specific concerns:

```python
# alea-llm-client handles: provider selection, API calls, response parsing
# Intake system handles: prompt construction, FOLIO context injection,
#   streaming dispatch, token budget management, privilege-aware filtering
```

### Frontend Monorepo Decision

folio-mapper uses a pnpm monorepo with `packages/` (core, ui) and `apps/` (web, desktop). For alea-intake, start with a **flat single-app structure** (not monorepo) unless a shared component library or desktop app is planned. Premature monorepo structure adds overhead.

```
frontend/
  src/
    components/
    features/     # feature-based organization
    hooks/
    lib/          # api client, utils
    stores/       # zustand stores
    types/
  package.json
  vite.config.ts
  tailwind.config.js
```

## Installation

### Backend

```bash
# Core backend
uv add fastapi "uvicorn[standard]" pydantic pydantic-settings
uv add sqlalchemy alembic asyncpg aiosqlite pgvector
uv add httpx alea-llm-client folio-python "folio-python[search]"
uv add sse-starlette
uv add cryptography python-jose passlib python-multipart
uv add structlog
uv add rdflib lxml

# ASR (local default)
uv add faster-whisper

# ASR (cloud, optional)
uv add deepgram-sdk  # optional
uv add assemblyai    # optional

# Document processing
uv add pymupdf python-docx beautifulsoup4

# Vector search (SQLite backend)
uv add faiss-cpu

# Dev dependencies
uv add --dev pytest pytest-asyncio pytest-cov
uv add --dev black ruff mypy
```

### Frontend

```bash
# Core
pnpm add react react-dom zustand @tanstack/react-query react-router

# Visualization
pnpm add @xyflow/react elkjs react-dropzone

# Dev dependencies
pnpm add -D typescript vite @vitejs/plugin-react
pnpm add -D tailwindcss@3 postcss autoprefixer
pnpm add -D @types/react @types/react-dom
pnpm add -D vitest @testing-library/react @testing-library/jest-dom jsdom
```

## Version Pinning Strategy

Use **minimum version pins with caret ranges** (e.g., `>=0.3.0` in Python, `^5.0.0` in JS) to get security patches while avoiding surprise major version bumps. Lock files (uv.lock, pnpm-lock.yaml) provide reproducible builds. Only pin exact versions for libraries with known breaking minor releases.

## Sources

- [alea-llm-client on PyPI](https://pypi.org/project/alea-llm-client/) -- v0.3.0, supports OpenAI/Anthropic/Google/xAI/VLLM
- [FastAPI PyPI](https://pypi.org/project/fastapi/) -- v0.135.1, native SSE support added in 0.135.0
- [SQLAlchemy 2.0.48 release](https://www.sqlalchemy.org/blog/2025/05/14/sqlalchemy-2.0.41-released/) -- async support matured
- [pgvector-python GitHub](https://github.com/pgvector/pgvector-python) -- v0.4.2, SQLAlchemy integration
- [faiss-cpu PyPI](https://pypi.org/project/faiss-cpu/) -- v1.13.2+
- [faster-whisper GitHub](https://github.com/SYSTRAN/faster-whisper) -- v3.8.2, CTranslate2-based
- [deepgram-sdk PyPI](https://pypi.org/project/deepgram-sdk/) -- v6.0.1
- [sse-starlette GitHub](https://github.com/sysid/sse-starlette) -- v3.3.3
- [Alembic docs](https://alembic.sqlalchemy.org/) -- v1.18.4
- [aiosqlite PyPI](https://pypi.org/project/aiosqlite/) -- v0.22.1
- [pydantic-settings PyPI](https://pypi.org/project/pydantic-settings/) -- v2.13.1
- [cryptography docs](https://cryptography.io/en/latest/fernet/) -- v46.0.5, Fernet symmetric encryption
- [React Router releases](https://github.com/remix-run/react-router/releases) -- v7.13.1
- [TanStack Query npm](https://www.npmjs.com/package/@tanstack/react-query) -- v5.94.5
- [@xyflow/react npm](https://www.npmjs.com/package/@xyflow/react) -- v12.10.1
- [Tailwind CSS v4 upgrade guide](https://tailwindcss.com/docs/upgrade-guide) -- documents breaking changes vs v3
- [uvicorn PyPI](https://pypi.org/project/uvicorn/) -- v0.41.0
- folio-python pyproject.toml -- ecosystem dependency versions
- folio-enrich pyproject.toml -- ecosystem dependency versions and patterns
- folio-mapper package.json files -- frontend ecosystem patterns
