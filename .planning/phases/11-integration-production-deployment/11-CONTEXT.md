# Phase 11: Integration & Production Deployment - Context

**Gathered:** 2026-04-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Final phase — CMS sync connectors, multi-tenant/single-tenant deployment from same codebase, configurable persistence modes, production monitoring (OpenTelemetry), security hardening, tenant provisioning, Alembic migrations, and open-source distribution (MIT license, Markdown skills marketplace).

</domain>

<decisions>
## Implementation Decisions

### Deployment Model
- **D-01:** Hybrid deployment — ALEA offers optional hosted instance for orgs that don't want to manage infrastructure, PLUS self-hosted option. Two paths from same codebase.
- **D-02:** Same codebase, env-var-driven topology. DEPLOYMENT_MODE env var: "multi_tenant" (shared infra, org-scoped schemas) or "single_tenant" (one org, simplified config). Multi-tenant uses PostgreSQL with schema isolation. Single-tenant can use SQLite or Postgres.
- **D-03:** Published artifacts: Docker images (GHCR/DockerHub), docker-compose.yml (single-tenant quick start), Helm chart (Kubernetes multi-tenant), install.sh one-liner (self-hosted setup). All config via env vars.
- **D-04:** Alembic migrations + rolling Docker updates. Auto-detect schema version on startup, run pending migrations automatically. Self-hosted: docker-compose pull + restart. ALEA-hosted: Kubernetes rolling update. Rollback via Alembic downgrade.

### CMS Connector Architecture (INTEGRATE-01, 02, 03)
- **D-05:** Build for both adapter pattern with bidirectional sync queue AND webhook-driven sync — since CMS systems may support only one method. CMSAdapter ABC with push/pull/sync methods. Each CMS (Clio, MyCase, Legal Server) implements the adapter.
- **D-06:** Sync scope is org-configurable. Orgs decide what data flows to their CMS. Recommended: intake metadata + contacts + output documents. Analysis internals optional. ALEA does NOT store customer data — organizations deploy the code and manage their own data.

### Persistence Modes (DEPLOY-05)
- **D-07:** Org-level setting with automatic lifecycle management. Three modes: (1) Ephemeral — data auto-deleted after session or configurable TTL. (2) Persistent — full case tracking, retained until right-to-delete. (3) CMS-integrated — synced to CMS on completion, local retention per org policy.
- **D-08:** Ephemeral deletion scope: delete all PII + analysis (messages, facts, claims, mappings, documents, audio, memos, consumer PII). Keep anonymized audit trail + screening trigger counts (protocol effectiveness metrics). Uses Phase 1 right-to-delete cascade.

### Monitoring & Observability (DEPLOY-06)
- **D-09:** Full APM via OpenTelemetry. Distributed tracing across all services. Structured JSON logging (structlog) with correlation IDs per intake. Prometheus-compatible /metrics endpoint: request latency, active intakes, analysis stage durations, LLM call counts/costs, screening trigger rates. Extended /health endpoint: DB, FOLIO OWL, folio-mcp, LLM provider, queue depths. Operators use their own dashboarding (Grafana, Datadog, etc.).

### Tenant Provisioning
- **D-10:** Both self-service signup + admin approval AND fully self-service (no approval) — ALEA toggles between. On approval/signup: DB schema created, default protocols seeded, admin credentials emailed. First login triggers setup wizard (Phase 8 D-34).

### Security Hardening
- **D-11:** Full production security suite. Rate limiting (per-IP + per-org), strict CORS (production origin only), CSP headers (script-src self), HSTS, secrets via env vars, API key rotation support, session fixation protection, input sanitization middleware, request size limits. All config via env vars for per-deployment tuning.

### Open-Source Distribution
- **D-12:** MIT License. Organizations can use, modify, deploy without restriction. ALEA retains copyright. Most adoption-friendly for legal organizations.
- **D-13:** Core skills bundled (DV screening, general intake templates), community marketplace for extras. Skills are Markdown definitions, not code. Organizations can create private skills. Community skills registry (like npm for legal intake).

### Claude's Discretion
- CMS API field mapping details (Clio API schema, MyCase API schema, Legal Server API schema)
- Helm chart structure and values.yaml defaults
- OpenTelemetry instrumentation scope (which spans to trace)
- Alembic migration directory structure
- Rate limiting algorithm (token bucket, sliding window)
- Skills registry implementation (Git-based, HTTP API, or bundled JSON index)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Dependencies
- `.planning/phases/01-foundation-security/01-CONTEXT.md` — Auth, encryption, tenant isolation, Docker, right-to-delete
- `.planning/phases/07-output-export/07-CONTEXT.md` — Output generation (synced to CMS)
- `.planning/phases/08-frontend-application/08-CONTEXT.md` — Frontend build, admin UI, setup wizard

### Existing Code
- `backend/app/middleware/tenant.py` — TenantMiddleware (schema isolation)
- `backend/app/services/deletion_service.py` — DeletionService (right-to-delete cascade for ephemeral mode)
- `backend/app/main.py` — Lifespan, router registration, health endpoint
- `backend/app/config.py` — Settings (env-var-driven config)
- `backend/app/db/engine.py` — DB engine (PostgreSQL + SQLite dual backend)

### Requirements
- `.planning/REQUIREMENTS.md` — INTEGRATE-01, 02, 03, DEPLOY-02, 03, 05, 06

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **TenantMiddleware**: Already handles schema isolation — extend for multi/single tenant mode
- **DeletionService**: Right-to-delete cascade — reuse for ephemeral mode auto-deletion
- **Settings (Pydantic)**: Env-var-driven config — extend with DEPLOYMENT_MODE, CMS, monitoring settings
- **Docker containers**: Already built in Phase 1 — extend Compose and add Helm chart

### Integration Points
- CMS connectors consume Phase 7 output documents
- Persistence mode hooks into existing DB lifecycle
- Monitoring wraps existing FastAPI app with OpenTelemetry middleware
- Security hardening adds production middleware to existing app

</code_context>

<specifics>
## Specific Ideas

- ALEA is a nonprofit providing open-source software — NOT a data custodian
- Organizations own their data entirely
- Skills are Markdown, not code — accessible to non-developers
- MIT license for maximum adoption in the legal sector
- "Build both, org/ALEA decides" continues from prior phases

</specifics>

<deferred>
## Deferred Ideas

None — this is the final phase. Everything needed for v1.0 is in scope.

</deferred>

---

*Phase: 11-integration-production-deployment*
*Context gathered: 2026-04-06*
