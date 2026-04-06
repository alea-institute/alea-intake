---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: verifying
stopped_at: Completed 10-03-PLAN.md
last_updated: "2026-04-06T20:08:24.475Z"
last_activity: 2026-04-06
progress:
  total_phases: 11
  completed_phases: 10
  total_plans: 42
  completed_plans: 42
  percent: 89
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-22)

**Core value:** When a person describes a legal situation, the system must correctly identify all relevant legal issues -- including ones the person doesn't know to mention -- and produce a structured analysis mapping their facts to claims, elements, and authorities across applicable jurisdictions.
**Current focus:** Phase 10 — autonomy-orchestration-modes

## Current Position

Phase: 11
Plan: Not started
Status: Phase complete — ready for verification
Last activity: 2026-04-06

Progress: [============================================------]  89%

## Performance Metrics

**Velocity:**

- Total plans completed: 7
- Average duration: 7min
- Total execution time: 0.73 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-foundation-security | 5 | 37min | 7min |
| 02-folio-ontology-integration | 2 | 19min | 10min |

**Recent Trend:**

- Last 5 plans: 5min, 6min, 6min, 9min, 10min
- Trend: stable

*Updated after each plan completion*
| Phase 01 P02 | 11min | 2 tasks | 15 files |
| Phase 01 P04 | 12min | 2 tasks | 13 files |
| Phase 01 P05 | 6min | 2 tasks | 18 files |
| Phase 02 P01 | 9min | 2 tasks | 14 files |
| Phase 02 P03 | 10min | 2 tasks | 8 files |
| Phase 02 P02 | 10min | 2 tasks | 13 files |
| Phase 05 P01 | 16min | 2 tasks | 11 files |
| Phase 05 P02 | 11min | 2 tasks | 8 files |
| Phase 06 P02 | 4min | 2 tasks | 6 files |
| Phase 06 P03 | 6min | 2 tasks | 16 files |
| Phase 06 P04 | 8min | 2 tasks | 12 files |
| Phase 06 P05 | 9min | 2 tasks | 8 files |
| Phase 07 P01 | 6min | 2 tasks | 8 files |
| Phase 07 P02 | 6min | 2 tasks | 11 files |
| Phase 07 P03 | 10min | 2 tasks | 11 files |
| Phase 08 P01 | 12min | 3 tasks | 23 files |
| Phase 08 P02 | 8min | 3 tasks | 33 files |
| Phase 08 P03 | 8min | 2 tasks | 17 files |
| Phase 08 P04 | 11min | 3 tasks | 27 files |
| Phase 08 P06 | 13min | 3 tasks | 57 files |
| Phase 08 P05 | 10min | 4 tasks | 25 files |
| Phase 09 P01 | 10min | 2 tasks | 17 files |
| Phase 09 P03 | 5min | 2 tasks | 6 files |
| Phase 09 P04 | 9min | 2 tasks | 8 files |
| Phase 09 P05 | 6min | 2 tasks | 5 files |
| Phase 10 P01 | 6min | 2 tasks | 14 files |
| Phase 10 P02 | 5min | 2 tasks | 6 files |
| Phase 10 P03 | 6min | 2 tasks | 17 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: 11 phases derived from 85 requirements at fine granularity
- [Roadmap]: Phases 2 and 3 can execute in parallel (both depend only on Phase 1)
- [Roadmap]: LLM client integration (INTEGRATE-04) placed in Phase 1 as foundational infrastructure
- [Roadmap]: folio-mcp integration (INTEGRATE-05) placed in Phase 6 alongside research tools
- [01-01]: Used pydantic[email] extra for EmailStr validation
- [01-01]: TenantMiddleware skips public routes -- no tenant required for /health, /docs, auth
- [01-01]: Test fixtures use aiosqlite in-memory; schema isolation is no-op on SQLite
- [01-01]: LargeBinary columns for PII fields ready for encryption layer in Plan 03
- [Phase 01-03]: AES-256-GCM via AESGCM primitive, not Fernet (Fernet is AES-128-CBC)
- [Phase 01-03]: Standalone functions + EncryptionContext instead of SQLAlchemy TypeDecorator for request-scoped DEK support
- [Phase 01-03]: Key auto-generation with 0o600 permissions for zero-config dev setup
- [Phase 01]: Added jti claim to refresh tokens for uniqueness across same-second rotations
- [Phase 01]: Fixed SQLite schema_translate_map: schemaless table copies for DDL, connection-level execution_options for DML
- [Phase 01]: require_role checks DB user.role (authoritative) not JWT role claim (informational)
- [Phase 01-05]: LLMService uses _PROVIDER_MODEL_MAP for provider-to-class resolution (openai, anthropic, google, vllm)
- [Phase 01-05]: Three-level training opt-out: API-tier access, provider headers, local_only policy enforcement
- [Phase 01-05]: Organization CRUD uses shared session (orgs are in shared schema, not tenant schemas)
- [Phase 01-05]: Frontend uses Tailwind 3.x (not 4.x) for PostCSS compatibility
- [Phase 01-04]: Audit middleware uses separate DB session (engine.begin()) for transaction isolation
- [Phase 01-04]: Temp-file SQLite for async_client fixture (in-memory doesn't support multi-connection audit middleware)
- [Phase 01-04]: ConsentMiddleware decodes JWT independently for user_id (not relying on request.state from auth dependency)
- [Phase 01-04]: Deletion preview hash uses SHA-256 of preview data for stale-detection confirmation
- [Phase 01-04]: Seeded Organization in async_client fixture for admin endpoint testing
- [Phase 02-01]: folio_owl_branch defaults to "main" overriding folio-python's "2.0.0" default
- [Phase 02-01]: OWL cache uses standalone cache_dir (./data/folio_cache) not folio-python's ~/.folio/cache
- [Phase 02-01]: ensure_owl_fresh returns bool (not raises) for graceful degradation on network errors
- [Phase 02-01]: EmbeddingService.rebuild_index call guarded by ImportError for forward compatibility with Plan 02-02
- [Phase 02-03]: Unmapped confidence formula: 1-(best_match/threshold) clamped [0,1]
- [Phase 02-03]: Adjacency returns graph structure {nodes, edges} not flat list
- [Phase 02-03]: Unmapped concept adjacency uses nearest mapped concepts as traversal anchors
- [Phase 02-03]: Admin endpoints use router-level Depends(require_role(Role.ADMIN))
- [Phase 02-02]: FAISSBackend uses IndexFlatIP on normalized vectors for cosine similarity
- [Phase 02-02]: Concept resolution weights: embedding=0.3, label=0.3, LLM=0.4; single-stage penalty=0.7
- [Phase 02-02]: High-confidence embedding match (>0.85) skips LLM stage to save cost/latency
- [Phase 02-02]: Lifespan calls build_index(folio) between FOLIO load and periodic updater start
- [Phase 05]: SimpleNamespace mocks for TriggerMatcher tests (avoids SQLAlchemy __new__ state issues)
- [Phase 05]: Graceful degradation in lifespan seed loading (try/except for mocked test envs)
- [Phase 05]: Created analysis/schemas.py in worktree since Phase 4 code not yet merged
- [Phase 05]: Lazy imports for FOLIO adjacency in exploration layers to break circular import chain
- [Phase 05]: asyncio.gather with return_exceptions=True for graceful degradation in parallel exploration branches
- [Phase 05]: Unresolvable concepts preserved with synthetic keys rather than being silently dropped
- [Phase 06-02]: FolioMCPClient uses direct __aenter__/__aexit__ on SDK context managers for explicit cleanup control
- [Phase 06-02]: Reporter whitespace normalization via regex for are_same_authority (F. 3d == F.3d)
- [Phase 06-02]: Unparseable citations preserved in deduplication (appended after deduped results)
- [Phase 06-02]: Case-insensitive cache key hashing (inputs lowercased before SHA-256)
- [Phase 06]: HTTPAdapter intermediate base class with shared httpx client management and DI support
- [Phase 06]: CitationVerifier uses in-memory cache with TTL (24h case law, 7d statutes) and parallel multi-source verification
- [Phase 06]: ResultRanker uses 5 weighted signals: relevance(0.30), recency(0.20), jurisdiction(0.25), court_level(0.15), verification(0.10)
- [Phase 06]: Binding strength: same jurisdiction+authoritative = binding, different = persuasive, secondary = secondary per D-17
- [Phase 06]: Simple whitespace tokenization for chunk token counting (sufficient for boundary decisions)
- [Phase 06]: FOLIO IRI boost factor 1.5x for dual-signal retrieval; insight demotion 0.5x per D-08 hierarchy
- [Phase 06]: stdlib html.parser for HTML extraction (avoids BeautifulSoup dependency)
- [Phase 06]: ResearchStage uses asyncio.gather with return_exceptions=True for parallel tool queries
- [Phase 06]: UsageTracker in-memory for MVP; production persists to ResearchToolConfig DB
- [Phase 06]: FolioMCPClient lifespan connection graceful -- unavailability doesn't block startup
- [Phase 07]: Binding strength classification: statutes/regulations/constitutional/rules = binding, case_law = persuasive, secondary = secondary
- [Phase 07]: Claims with jurisdiction=None grouped under 'General' key in claims_by_jurisdiction
- [Phase 07]: Format-neutral OutputContext as single Pydantic model for all downstream rendering
- [Phase 07]: TriageScorer weights: practice_area=0.35, jurisdiction=0.25, complexity=0.20, org_rules=0.20
- [Phase 07]: Complexity thresholds: high if >5 claims or >10 gaps, low if <=2 claims and <=3 gaps
- [Phase 07]: Referral generation triggers at completeness < 0.3 with >= 3 gaps in a practice area
- [Phase 07]: LanguageAdapter._rewrite_text is the LLM integration point; stubbed for now, wired when orchestrator connects
- [Phase 07]: WeasyPrint for PDF generation via CSS Paged Media (not reportlab or wkhtmltopdf)
- [Phase 07]: Export render caching on OutputDocument model for subsequent requests
- [Phase 07]: CSS custom properties for org branding injection in PDF export
- [Phase 08-01]: Seeded components.json directly (shadcn@2.3.0 CLI prompts unavoidably) with new-york+zinc+lucide
- [Phase 08-01]: Dev server port 8923 (md5 hash of alea-intake % 1300 + 8700) — stable across sessions
- [Phase 08-01]: Button installed via direct write (not shadcn CLI TTY) to match new-york registry spec
- [Phase 08-01]: ui-vendor manualChunks left dynamic (Radix primitives auto-chunked by Vite heuristics)
- [Phase 08-01]: Bundle budget enforced at 200KB gzipped main chunk (D-35); baseline 56KB
- [Phase 08-01]: tsconfig split into app/node references with @/* path alias (shadcn+Vite standard)
- [Phase 08-02]: ThemeProvider syncs on defaultTheme prop change (useEffect) for async org-data loading
- [Phase 08-02]: Refresh coalescing via module-scoped refreshPromise prevents thundering-herd on concurrent 401s
- [Phase 08-02]: apiFetch uses window.location.href='/login' hard redirect on refresh failure (no router dep)
- [Phase 08-02]: 5-language stub files (zh/vi/ko/tl/ru) copy English to prevent Suspense hang (Pitfall 7)
- [Phase 08-02]: jsdom origin http://localhost:3000; MSW handlers use absolute URLs matching this origin
- [Phase 08]: Inline token minting in OAuth callback using create_access_token/create_refresh_token directly (AuthService lacks mint_tokens_for_user)
- [Phase 08]: In-memory nonce store for MVP; production should use Redis for multi-worker safety
- [Phase 08]: OAuth routes exempted from TenantMiddleware via path prefix match
- [Phase 08]: queueMicrotask for WebSocket mock (survives fake timers unlike setTimeout)
- [Phase 08]: ConnectionBanner uses shared common namespace error keys for copy consistency
- [Phase 08]: ChatInput disabled when wsStatus !== connected (prevents sending into void)
- [Phase 08]: matchMedia + scrollIntoView polyfills in vitest.setup.ts for jsdom compat
- [Phase 08]: Extended rehype-sanitize schema for GFM table elements in MarkdownMemo
- [Phase 08]: Tailwind spacing tokens renamed from -custom suffix to short names (sm, md, lg)
- [Phase 08]: AppShell canonical location moved to shared/components/AppShell.tsx
- [Phase 08]: Admin tabs: 5 of 7 are intentional stubs; Organization + SetupWizard fully functional
- [Phase 08]: Virtual list threshold 100: below uses standard table, above uses @tanstack/react-virtual
- [Phase 08]: RecordPlugin mimeType set at create-time not startRecording (TypeScript type constraint)
- [Phase 08]: SafetyBanner uses button with role=alert for clickable non-dismissible critical banner
- [Phase 08]: AnalysisProgressPanel uses enabled:false React Query (WebSocket-only data source)
- [Phase 08]: ChatInput conditionally renders modality surfaces (voice/document) instead of always showing textarea
- [Phase 09]: Message content decoded as raw UTF-8 bytes for MVP; production should use EncryptionContext
- [Phase 09]: Registered Intake/IntakeSession/Message/ExtractedFact/FactSourceSpan in models __init__ (were missing)
- [Phase 09]: Visualization Zustand store: shared filters + per-view state slices, URL sync via replaceState
- [Phase 09]: Okabe-Ito colorblind-safe palette for all categorical visualization colors
- [Phase 09]: Cell lookup uses Map<factId-elementId, MatrixCell> with highest-confidence-wins for duplicate mappings
- [Phase 09]: Collapse state managed in local useState (not Zustand) to avoid cross-view state leakage
- [Phase 09]: Sweep-line boundary algorithm resolves overlapping annotations into flat non-overlapping segments (avoids Pitfall 4)
- [Phase 09]: useLayoutEffect for chip positioning (DOM measurements need synchronous layout read)
- [Phase 09]: claimNameMap memoized with useMemo to prevent infinite effect loops from Map recreation
- [Phase 09]: Top-level jspdf import for vi.mock test compatibility; export functions accept pre-filtered data for inherent filter respect
- [Phase 10]: asyncio.Event for zero-cost pipeline pause/resume (no polling, instant wake)
- [Phase 10]: Interceptor pattern: optional wrapper injected into orchestrator __init__, wraps _execute_stage
- [Phase 10]: Mutable _config on interceptor enables mid-intake mode switch at next stage boundary (D-05)
- [Phase 10]: Email notification is stub-only per D-07 (WebSocket primary channel)
- [Phase 10]: Race condition protection: resolve after timeout raises ValueError (Pitfall 2)
- [Phase 10]: Module-scoped ApprovalQueue singleton with set/get for test injection and lifespan init
- [Phase 10]: Audit event_type names aligned with D-10 spec: auto_proceeded, stage_skipped, mode_changed (past tense)
- [Phase 10]: Router-level Depends(require_role) for blanket role enforcement on autonomy endpoints
- [Phase 10]: Local state sync pattern for AutonomySettings: useEffect copies server config, presets apply locally, save is explicit
- [Phase 10]: ReviewStatusState stored in Zustand WSStore (co-locates with connection status, avoids new store)

### Pending Todos

None yet.

### Blockers/Concerns

None yet.

## Session Continuity

Last session: 2026-04-06T20:07:08.983Z
Stopped at: Completed 10-03-PLAN.md
Resume file: None
