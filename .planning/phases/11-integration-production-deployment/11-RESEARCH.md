# Phase 11: Integration & Production Deployment - Research

**Researched:** 2026-04-03
**Domain:** CMS connectors, multi-tenant/single-tenant deployment, persistence modes, OpenTelemetry, security hardening, tenant provisioning, Alembic migrations, open-source distribution
**Confidence:** HIGH

## Summary

Phase 11 is the final phase of ALEA Intake v1.0, covering seven pending requirements (INTEGRATE-01, 02, 03, DEPLOY-02, 03, 05, 06). The codebase already has substantial infrastructure in place: TenantMiddleware with schema isolation, DeletionService for right-to-delete cascades, dual-backend DB engine (PostgreSQL+SQLite), Docker containers, Alembic configured with multi-schema env.py, and env-var-driven Settings via Pydantic. The phase adds CMS connectors (Clio, MyCase, Legal Server), formalizes multi-tenant vs single-tenant deployment modes, implements configurable persistence (ephemeral/persistent/CMS-integrated), adds full OpenTelemetry observability, hardens security for production, enhances tenant provisioning with self-service flows, production-ready Alembic migration automation, and packages for open-source distribution with MIT license.

The architecture pattern is straightforward: extend existing infrastructure rather than build from scratch. CMS connectors follow the adapter ABC pattern already established with research tool adapters (Phase 6). Persistence modes hook into the existing DeletionService. Monitoring wraps the existing FastAPI app. Security adds middleware layers. The Helm chart and docker-compose extensions are new artifacts but follow well-established community patterns.

**Primary recommendation:** Structure this phase as seven work streams (CMS connectors, deployment modes, persistence, monitoring, security hardening, tenant provisioning, distribution/packaging) with monitoring and security hardening as independent parallelizable work, CMS connectors as the heaviest implementation effort, and distribution packaging as the final capstone.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Hybrid deployment -- ALEA offers optional hosted instance for orgs that don't want to manage infrastructure, PLUS self-hosted option. Two paths from same codebase.
- **D-02:** Same codebase, env-var-driven topology. DEPLOYMENT_MODE env var: "multi_tenant" (shared infra, org-scoped schemas) or "single_tenant" (one org, simplified config). Multi-tenant uses PostgreSQL with schema isolation. Single-tenant can use SQLite or Postgres.
- **D-03:** Published artifacts: Docker images (GHCR/DockerHub), docker-compose.yml (single-tenant quick start), Helm chart (Kubernetes multi-tenant), install.sh one-liner (self-hosted setup). All config via env vars.
- **D-04:** Alembic migrations + rolling Docker updates. Auto-detect schema version on startup, run pending migrations automatically. Self-hosted: docker-compose pull + restart. ALEA-hosted: Kubernetes rolling update. Rollback via Alembic downgrade.
- **D-05:** Build for both adapter pattern with bidirectional sync queue AND webhook-driven sync -- since CMS systems may support only one method. CMSAdapter ABC with push/pull/sync methods. Each CMS (Clio, MyCase, Legal Server) implements the adapter.
- **D-06:** Sync scope is org-configurable. Orgs decide what data flows to their CMS. Recommended: intake metadata + contacts + output documents. Analysis internals optional. ALEA does NOT store customer data -- organizations deploy the code and manage their own data.
- **D-07:** Org-level setting with automatic lifecycle management. Three modes: (1) Ephemeral -- data auto-deleted after session or configurable TTL. (2) Persistent -- full case tracking, retained until right-to-delete. (3) CMS-integrated -- synced to CMS on completion, local retention per org policy.
- **D-08:** Ephemeral deletion scope: delete all PII + analysis (messages, facts, claims, mappings, documents, audio, memos, consumer PII). Keep anonymized audit trail + screening trigger counts (protocol effectiveness metrics). Uses Phase 1 right-to-delete cascade.
- **D-09:** Full APM via OpenTelemetry. Distributed tracing across all services. Structured JSON logging (structlog) with correlation IDs per intake. Prometheus-compatible /metrics endpoint: request latency, active intakes, analysis stage durations, LLM call counts/costs, screening trigger rates. Extended /health endpoint: DB, FOLIO OWL, folio-mcp, LLM provider, queue depths. Operators use their own dashboarding (Grafana, Datadog, etc.).
- **D-10:** Both self-service signup + admin approval AND fully self-service (no approval) -- ALEA toggles between. On approval/signup: DB schema created, default protocols seeded, admin credentials emailed. First login triggers setup wizard (Phase 8 D-34).
- **D-11:** Full production security suite. Rate limiting (per-IP + per-org), strict CORS (production origin only), CSP headers (script-src self), HSTS, secrets via env vars, API key rotation support, session fixation protection, input sanitization middleware, request size limits. All config via env vars for per-deployment tuning.
- **D-12:** MIT License. Organizations can use, modify, deploy without restriction. ALEA retains copyright. Most adoption-friendly for legal organizations.
- **D-13:** Core skills bundled (DV screening, general intake templates), community marketplace for extras. Skills are Markdown definitions, not code. Organizations can create private skills. Community skills registry (like npm for legal intake).

### Claude's Discretion
- CMS API field mapping details (Clio API schema, MyCase API schema, Legal Server API schema)
- Helm chart structure and values.yaml defaults
- OpenTelemetry instrumentation scope (which spans to trace)
- Alembic migration directory structure
- Rate limiting algorithm (token bucket, sliding window)
- Skills registry implementation (Git-based, HTTP API, or bundled JSON index)

### Deferred Ideas (OUT OF SCOPE)
None -- this is the final phase. Everything needed for v1.0 is in scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INTEGRATE-01 | CMS sync connector for Clio | CMSAdapter ABC + Clio v4 REST API adapter with OAuth2 auth, contacts/matters/documents sync |
| INTEGRATE-02 | CMS sync connector for MyCase | CMSAdapter ABC + MyCase REST API adapter with OAuth2/API key auth |
| INTEGRATE-03 | CMS sync connector for Legal Server | CMSAdapter ABC + LegalServer REST API adapter with Premium API access |
| DEPLOY-02 | Multi-tenant cloud deployment with org-scoped data isolation | DEPLOYMENT_MODE=multi_tenant with PostgreSQL schema isolation (already built in Phase 1) |
| DEPLOY-03 | Single-tenant self-hosted deployment option | DEPLOYMENT_MODE=single_tenant with SQLite/Postgres, docker-compose.yml, install.sh |
| DEPLOY-05 | Configurable persistence: ephemeral, persistent, CMS-integrated | Org-level persistence_mode setting with TTL scheduler and DeletionService integration |
| DEPLOY-06 | Health check and monitoring endpoints | OpenTelemetry + structlog + Prometheus /metrics + extended /health |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| opentelemetry-api | 1.40.0 | Tracing/metrics API | CNCF standard for observability; vendor-neutral |
| opentelemetry-sdk | 1.40.0 | OTel SDK implementation | Required runtime for OTel API |
| opentelemetry-exporter-otlp-proto-http | 1.40.0 | OTLP exporter (HTTP) | HTTP transport preferred for simplicity; no gRPC dep |
| structlog | 25.5.0 | Structured JSON logging | Best Python structured logging lib; processor chain architecture |
| slowapi | 0.1.9 | Rate limiting | Standard FastAPI/Starlette rate limiter; supports Redis backend |
| prometheus-client | 0.24.1 | Prometheus metrics | Standard Python Prometheus client for /metrics endpoint |
| prometheus-fastapi-instrumentator | 7.1.0 | Auto-instrument FastAPI | Automatic request duration/count metrics |
| alembic | 1.18.4 | Database migrations | Already installed; multi-schema support via env.py (already configured) |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| opentelemetry-instrumentation-fastapi | 0.59b0 | Auto-instrument FastAPI routes | Distributed tracing for all HTTP endpoints |
| httpx | 0.28.0+ | HTTP client for CMS APIs | Already installed; async CMS API calls |
| authlib | 1.6.0+ | OAuth2 client for CMS auth | Already installed; Clio/MyCase OAuth2 flows |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| slowapi | Custom middleware | slowapi is battle-tested, supports Redis for multi-worker; custom adds maintenance |
| structlog | stdlib logging + JSON formatter | structlog processor chain is cleaner for correlation IDs and OTel integration |
| prometheus-fastapi-instrumentator | Manual OTel metrics | Instrumentator gives standard RED metrics for free; manual is more flexible but more work |
| opentelemetry-exporter-otlp-proto-http | otlp-proto-grpc | HTTP simpler to deploy (no gRPC deps); grpc slightly higher throughput |

**Installation:**
```bash
cd backend && uv add opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp-proto-http opentelemetry-instrumentation-fastapi structlog slowapi prometheus-client prometheus-fastapi-instrumentator
```

## Architecture Patterns

### Recommended Project Structure
```
backend/app/
  integrations/
    cms/
      __init__.py
      base.py              # CMSAdapter ABC + CMSSyncRecord model
      clio.py              # ClioAdapter
      mycase.py            # MyCaseAdapter
      legalserver.py       # LegalServerAdapter
      sync_queue.py        # Background sync queue (asyncio.Queue)
      field_mapping.py     # Canonical ALEA -> CMS field mapping
  middleware/
    security.py            # SecurityHeadersMiddleware (CSP, HSTS, X-Frame)
    rate_limit.py          # Rate limiting setup (slowapi)
  observability/
    __init__.py
    telemetry.py           # OTel setup (TracerProvider, MeterProvider, LoggerProvider)
    metrics.py             # Custom application metrics (intake counts, LLM costs)
    health.py              # Extended /health endpoint logic
    logging.py             # structlog configuration + OTel correlation
  deployment/
    __init__.py
    mode.py                # DeploymentMode enum + mode-specific behavior
    persistence.py         # PersistenceMode enum + lifecycle manager
    provisioning.py        # Tenant provisioning (enhanced TenantService)
    migration_runner.py    # Auto-migration on startup
  skills/
    __init__.py
    registry.py            # Skills registry (bundled + community)
    marketplace.py         # Skills marketplace index
docker/
  docker-compose.yml       # Single-tenant quick start (enhanced from existing)
  docker-compose.multi.yml # Multi-tenant with separate Postgres
  Dockerfile               # Enhanced from existing
helm/
  alea-intake/
    Chart.yaml
    values.yaml
    templates/
      deployment.yaml
      service.yaml
      ingress.yaml
      configmap.yaml
      secret.yaml
      _helpers.tpl
scripts/
  install.sh               # One-liner self-hosted setup
```

### Pattern 1: CMS Adapter ABC
**What:** Abstract base class for CMS connectors with push/pull/sync methods
**When to use:** Every CMS integration implements this interface
**Example:**
```python
# Source: project convention (mirrors Phase 6 research adapter pattern)
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

class SyncDirection(str, Enum):
    PUSH = "push"      # ALEA -> CMS
    PULL = "pull"      # CMS -> ALEA
    BIDIRECTIONAL = "bidirectional"

@dataclass
class CMSSyncConfig:
    """Org-level CMS sync configuration."""
    cms_type: str                    # "clio", "mycase", "legalserver"
    credentials_encrypted: bytes     # OAuth tokens or API key
    sync_scope: list[str]            # ["contacts", "matters", "documents"]
    direction: SyncDirection
    webhook_url: str | None = None   # For webhook-driven sync

class CMSAdapter(ABC):
    """Abstract CMS connector. Each CMS implements this."""

    @abstractmethod
    async def push_contact(self, contact_data: dict) -> str:
        """Push a contact to the CMS. Returns CMS-side ID."""

    @abstractmethod
    async def push_matter(self, matter_data: dict) -> str:
        """Push a matter/case to the CMS. Returns CMS-side ID."""

    @abstractmethod
    async def push_document(self, doc_data: dict, file_bytes: bytes) -> str:
        """Upload a document to the CMS. Returns CMS-side ID."""

    @abstractmethod
    async def pull_updates(self, since: datetime) -> list[dict]:
        """Pull changes from CMS since timestamp."""

    @abstractmethod
    async def handle_webhook(self, payload: dict) -> None:
        """Process an inbound webhook from the CMS."""

    @abstractmethod
    async def test_connection(self) -> bool:
        """Verify CMS credentials and connectivity."""
```

### Pattern 2: Deployment Mode Branching
**What:** Single codebase, env-var-driven topology switching
**When to use:** Startup configuration, tenant provisioning, migration execution
**Example:**
```python
from enum import Enum
from app.config import get_settings

class DeploymentMode(str, Enum):
    MULTI_TENANT = "multi_tenant"
    SINGLE_TENANT = "single_tenant"

def get_deployment_mode() -> DeploymentMode:
    settings = get_settings()
    return DeploymentMode(getattr(settings, 'deployment_mode', 'single_tenant'))

# Usage in lifespan:
# if mode == DeploymentMode.MULTI_TENANT:
#     run_migrations_all_schemas()
# else:
#     run_migrations_default_schema()
```

### Pattern 3: Persistence Mode Lifecycle
**What:** Org-level persistence mode with automatic data lifecycle management
**When to use:** After intake completion or session end
**Example:**
```python
class PersistenceMode(str, Enum):
    EPHEMERAL = "ephemeral"        # Auto-delete after TTL
    PERSISTENT = "persistent"      # Retain until right-to-delete
    CMS_INTEGRATED = "cms_integrated"  # Sync then retain per policy

class PersistenceManager:
    async def handle_session_complete(self, intake_id: int, org: Organization):
        mode = org.settings.get("persistence_mode", "persistent")
        if mode == "ephemeral":
            ttl = org.settings.get("ephemeral_ttl_hours", 24)
            await self._schedule_deletion(intake_id, ttl)
        elif mode == "cms_integrated":
            await self._sync_to_cms(intake_id, org)
            # Local retention per org policy
```

### Pattern 4: OpenTelemetry Setup
**What:** Centralized OTel initialization with TracerProvider + MeterProvider + LoggerProvider
**When to use:** Application lifespan startup
**Example:**
```python
# Source: OpenTelemetry Python docs
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

def setup_telemetry(app):
    # Traces
    provider = TracerProvider()
    if settings.otel_endpoint:
        exporter = OTLPSpanExporter(endpoint=settings.otel_endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    # Auto-instrument FastAPI
    FastAPIInstrumentor.instrument_app(app)

    # Metrics via prometheus-fastapi-instrumentator
    from prometheus_fastapi_instrumentator import Instrumentator
    Instrumentator().instrument(app).expose(app, endpoint="/metrics")
```

### Anti-Patterns to Avoid
- **Coupling CMS logic to core models:** CMS adapters must consume OutputDocument/Intake via read-only queries, never modify core models. CMS sync state lives in its own CMSSyncRecord table.
- **Blocking sync in request handlers:** CMS sync must be async background tasks, never blocking the intake flow. Use asyncio.Queue or similar.
- **Hardcoding deployment assumptions:** Never assume multi-tenant or single-tenant. Always check DeploymentMode at runtime.
- **Conditional imports for deployment mode:** Use the same code paths with mode-aware branching, not separate codebases.
- **Starting OTel collector as a required dependency:** OTel must be opt-in via env vars. If no collector endpoint is configured, telemetry is a no-op.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Rate limiting | Custom token bucket middleware | slowapi (with Redis for multi-worker) | Edge cases: burst handling, distributed state, IP extraction behind proxies |
| Prometheus metrics | Custom /metrics text format renderer | prometheus-client + prometheus-fastapi-instrumentator | Prometheus text format has precise spec; instrumentator gives RED metrics for free |
| Distributed tracing | Custom request ID propagation | opentelemetry-instrumentation-fastapi | W3C trace context propagation, span hierarchy, async context management |
| Structured logging | Custom JSON log formatter | structlog with OTel processor | Processor chain, contextvars integration, async-safe, OTel trace/span ID injection |
| Security headers | Custom header middleware | Starlette middleware (simple enough to write; no library needed) | CSP/HSTS/X-Frame are simple string headers; a library adds overhead for simple strings |
| Helm charts | Custom Kubernetes manifests | Helm chart with values.yaml | Templating, upgrades, rollbacks, community convention |
| OAuth2 CMS auth | Custom OAuth2 flow | authlib (already installed) | Token refresh, PKCE, state management |

**Key insight:** The monitoring/observability stack is the most dangerous to hand-roll. OpenTelemetry's context propagation across async boundaries, Prometheus text format compliance, and structlog's contextvars integration each have subtle correctness requirements that custom implementations routinely get wrong.

## Common Pitfalls

### Pitfall 1: Alembic Multi-Schema Migration Ordering
**What goes wrong:** Running migrations against all tenant schemas without proper ordering causes deadlocks or inconsistent state if one schema fails mid-migration.
**Why it happens:** Alembic's default is single-schema. Multi-tenant requires explicit iteration over schemas.
**How to avoid:** Run migrations against shared schema first, then iterate tenant schemas sequentially. Use a try/except per schema with logging so one failed tenant doesn't block others. Track per-schema alembic_version.
**Warning signs:** "relation already exists" errors, migrations running twice on same schema.

### Pitfall 2: OTel Instrumentation in Async Context
**What goes wrong:** Trace context (span IDs, trace IDs) don't propagate into background tasks or asyncio.gather branches.
**Why it happens:** OTel uses contextvars. asyncio.create_task copies context, but asyncio.gather with return_exceptions=True may swallow context propagation errors silently.
**How to avoid:** Always use `trace.get_current_span()` inside each async branch. For background tasks, explicitly copy context with `context.attach(context.get_current())`.
**Warning signs:** Orphaned spans in traces, missing correlation IDs in logs from background tasks.

### Pitfall 3: Rate Limiting Behind Reverse Proxy
**What goes wrong:** All requests appear to come from the same IP (the proxy), so rate limiting blocks all users at once.
**Why it happens:** slowapi defaults to `request.client.host`, which is the proxy IP.
**How to avoid:** Configure slowapi with a custom key function that reads `X-Forwarded-For` or `X-Real-IP` header. Make this configurable via env var (ALEA_RATE_LIMIT_KEY_HEADER).
**Warning signs:** Rate limit errors for all users simultaneously.

### Pitfall 4: CMS OAuth Token Expiration During Sync
**What goes wrong:** Long-running sync jobs fail mid-way because the CMS OAuth access token expires.
**Why it happens:** Clio access tokens expire after ~10 minutes. A large sync batch can exceed this.
**How to avoid:** Implement automatic token refresh in the CMS adapter base class. Check token expiry before each API call. Store refresh tokens encrypted in CMSSyncConfig.
**Warning signs:** 401 errors partway through sync batches.

### Pitfall 5: Ephemeral Deletion Race Condition
**What goes wrong:** User is still in active session when TTL-based deletion fires, deleting their in-progress work.
**Why it happens:** TTL is calculated from session start, not session end.
**How to avoid:** Ephemeral TTL starts from session completion (status changed to "completed" or "abandoned"), not creation. Check session status before deletion. Only delete if status is terminal.
**Warning signs:** Users reporting lost data during active sessions.

### Pitfall 6: Helm Chart Secrets in values.yaml
**What goes wrong:** Sensitive values (DB password, secret key) end up in values.yaml committed to git.
**Why it happens:** Default Helm pattern puts everything in values.yaml.
**How to avoid:** Use Kubernetes Secrets (created externally or via sealed-secrets) referenced in deployment.yaml via secretKeyRef. values.yaml contains only non-sensitive defaults. Document this in the Helm chart README.
**Warning signs:** Credentials visible in `helm get values`.

### Pitfall 7: Single-Tenant Mode with PostgreSQL Schema Isolation
**What goes wrong:** Single-tenant PostgreSQL deployment still tries to create "shared" and "tenant_X" schemas, confusing operators.
**Why it happens:** Existing code always uses schema_translate_map.
**How to avoid:** In single-tenant mode, set schema_translate_map to {"tenant": None, "shared": None} (no schema prefixes). All tables go to the default public schema. This mirrors the existing SQLite test behavior.
**Warning signs:** Unexpected schema creation in single-tenant Postgres installs.

## CMS API Research

### Clio (INTEGRATE-01)
**API:** Clio Manage API v4 (REST, JSON)
**Base URL:** `https://app.clio.com/api/v4` (US), region-specific for AU/CA/EU
**Auth:** OAuth 2.0 Authorization Code grant (mandatory). Access tokens are short-lived; refresh tokens required.
**Key endpoints:**
- `POST /api/v4/contacts.json` -- Create contact
- `POST /api/v4/matters.json` -- Create matter
- `POST /api/v4/documents.json` -- Upload document (multipart)
- `GET /api/v4/contacts.json` -- List/search contacts
- `GET /api/v4/matters.json` -- List/search matters
- Webhook support via Clio's webhook subscriptions
**Field mapping:** Contacts have name, email, phone, type (Company/Person). Matters have description, status, practice_area, client (contact reference). Documents belong to a contact's folder.
**Rate limits:** Documented per-app limits; respect 429 responses.
**Confidence:** MEDIUM (based on official docs site structure and help center; actual field schemas need verification during implementation)

### MyCase (INTEGRATE-02)
**API:** MyCase REST API (hosted on Stoplight docs)
**Base URL:** `https://api.mycase.com/v1` (inferred from docs)
**Auth:** OAuth2 or API key (Advanced tier only, $89/month subscription required)
**Key endpoints:**
- Cases, Clients, Documents endpoints
- `GET /clients/{id}/cases` -- Get cases for a client
**Limitations:** API access requires Advanced tier subscription. Documentation hosted at mycaseapi.stoplight.io.
**Field mapping:** Cases map to matters, Clients map to contacts.
**Confidence:** MEDIUM (Stoplight docs available but could not scrape full endpoint details)

### Legal Server (INTEGRATE-03)
**API:** LegalServer REST API (Stoplight docs at apidocs.legalserver.org)
**Auth:** API key-based (Premium APIs require $200/month additional charge)
**Key endpoints:**
- GET/POST/PATCH/PUT/DELETE for Matter, Event, Timeslip, Clinic records
- Guided Navigation API for intake flows
**Limitations:** Premium API access must be enabled by LegalServer staff. Standard API is read-only for some operations.
**Field mapping:** Matters map directly; contacts/clients are Matter participants.
**Confidence:** MEDIUM (official help docs confirm API structure; field-level details need verification during implementation)

### CMS Adapter Recommendation
Use the same adapter ABC pattern established in Phase 6 for research tools. Each CMS adapter:
1. Implements CMSAdapter ABC
2. Handles its own auth (OAuth2 via authlib for Clio/MyCase, API key for LegalServer)
3. Maps ALEA's canonical OutputDocument/Intake/IntakeParty fields to CMS-specific fields via field_mapping.py
4. Stores sync state in a CMSSyncRecord model (maps ALEA entity IDs to CMS entity IDs)

## Code Examples

### Extended Settings Configuration
```python
# Source: existing app/config.py pattern
class DeploymentMode(str, Enum):
    MULTI_TENANT = "multi_tenant"
    SINGLE_TENANT = "single_tenant"

class PersistenceMode(str, Enum):
    EPHEMERAL = "ephemeral"
    PERSISTENT = "persistent"
    CMS_INTEGRATED = "cms_integrated"

class Settings(BaseSettings):
    # ... existing fields ...

    # Deployment
    deployment_mode: DeploymentMode = DeploymentMode.SINGLE_TENANT
    tenant_signup_mode: str = "admin_approval"  # or "self_service"

    # Observability
    otel_endpoint: str = ""  # Empty = disabled
    otel_service_name: str = "alea-intake"
    log_level: str = "INFO"
    log_format: str = "json"  # "json" or "console"

    # Rate limiting
    rate_limit_default: str = "100/minute"
    rate_limit_key_header: str = ""  # Empty = use client IP
    rate_limit_storage: str = "memory"  # "memory" or "redis://..."

    # Security
    csp_script_src: str = "'self'"
    hsts_max_age: int = 31536000  # 1 year
    max_request_size_mb: int = 50

    # CMS
    cms_enabled: bool = False
    cms_sync_interval_seconds: int = 300  # 5 minutes
```

### Structlog + OTel Correlation
```python
# Source: structlog docs + OTel Python docs
import structlog
from opentelemetry import trace

def add_otel_context(logger, method_name, event_dict):
    """Structlog processor that injects OTel trace/span IDs."""
    span = trace.get_current_span()
    ctx = span.get_span_context()
    if ctx.is_valid:
        event_dict["trace_id"] = format(ctx.trace_id, "032x")
        event_dict["span_id"] = format(ctx.span_id, "016x")
    return event_dict

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        add_otel_context,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
)
```

### Extended Health Endpoint
```python
# Source: existing /health pattern in main.py
@app.get("/health")
async def health():
    """Extended health check with component status."""
    from app.services.folio.owl_cache import get_owl_status

    checks = {
        "status": "healthy",
        "version": "1.0.0",
        "folio_owl": get_owl_status(),
    }

    # DB connectivity
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = {"status": "up"}
    except Exception as e:
        checks["database"] = {"status": "down", "error": str(e)}
        checks["status"] = "degraded"

    # folio-mcp
    folio_mcp = getattr(app.state, "folio_mcp_client", None)
    if folio_mcp and folio_mcp.connected:
        checks["folio_mcp"] = {"status": "up"}
    else:
        checks["folio_mcp"] = {"status": "down"}

    # LLM provider (lightweight check)
    checks["llm_provider"] = {"status": "configured" if settings.cms_enabled else "not_configured"}

    return checks
```

### Auto-Migration on Startup
```python
# Source: Alembic cookbook + existing env.py
import subprocess
from app.config import get_settings

async def run_startup_migrations():
    """Auto-detect and run pending Alembic migrations on startup."""
    settings = get_settings()
    if settings.deployment_mode == DeploymentMode.MULTI_TENANT:
        # Run shared schema first
        subprocess.run(
            ["alembic", "upgrade", "head"],
            cwd="backend", check=True
        )
        # Then each tenant schema
        for org in await list_all_orgs():
            subprocess.run(
                ["alembic", "-x", f"tenant=tenant_{org.slug}", "upgrade", "head"],
                cwd="backend", check=True
            )
    else:
        # Single tenant: just run against default schema
        subprocess.run(
            ["alembic", "upgrade", "head"],
            cwd="backend", check=True
        )
```

### Security Headers Middleware
```python
# Source: Starlette middleware pattern
from starlette.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        settings = get_settings()
        response.headers["Content-Security-Policy"] = f"script-src {settings.csp_script_src}"
        response.headers["Strict-Transport-Security"] = f"max-age={settings.hsts_max_age}; includeSubDomains"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "0"  # Deprecated but some scanners check
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Custom tracing (request IDs) | OpenTelemetry (W3C trace context) | 2023+ | Industry standard; vendor-neutral; auto-instrumentation |
| Separate logging/tracing/metrics | OTel unified (signals) | 2024+ | Single SDK for all three pillars |
| Gunicorn + Flask for production | Uvicorn + FastAPI | Established | Already using; no change needed |
| Manual Kubernetes YAML | Helm 4 charts | Nov 2025 | Server-side apply, slog logging, kstatus watching |
| Docker Compose v1 | Docker Compose v2 (integrated) | 2023+ | `docker compose` not `docker-compose`; already using |
| flask-limiter | slowapi (port to Starlette) | Established | Direct port; same API patterns |

**Deprecated/outdated:**
- `opentelemetry-instrumentation-fastapi` is still in beta (0.59b0) but stable and widely used in production. The beta version number is a Python OTel convention for instrumentation packages, not an indication of instability.
- Helm 3 -> Helm 4 transition (Nov 2025): Helm 4 uses server-side apply by default. Charts written for Helm 3 work with Helm 4 but should use apiVersion: v2.

## Open Questions

1. **CMS API Rate Limits**
   - What we know: Clio has per-app rate limits; MyCase and LegalServer likely similar
   - What's unclear: Exact rate limit numbers for each CMS
   - Recommendation: Implement exponential backoff with 429 response handling in CMSAdapter base class. Document per-CMS limits when discovered during implementation.

2. **Skills Registry Storage Backend**
   - What we know: Skills are Markdown files. Community registry needed.
   - What's unclear: Whether to use Git repo (like npm registry concept), HTTP API, or bundled JSON index for v1.0
   - Recommendation: For v1.0, use a Git-based registry (GitHub repo with Markdown files + JSON index). Simple, auditable, familiar to open-source community. HTTP API can be added in v2.

3. **Multi-Worker Rate Limiting**
   - What we know: slowapi supports Redis backend for distributed rate limiting
   - What's unclear: Whether ALEA-hosted will run multiple workers behind a load balancer for v1.0
   - Recommendation: Default to in-memory rate limiting. Support Redis via env var (ALEA_RATE_LIMIT_STORAGE=redis://host:6379). Document that multi-worker deployments MUST use Redis.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker | Container builds, deployment artifacts | Yes | 29.3.1 | -- |
| Python | Backend runtime | Yes | 3.12+ | -- |
| Node.js | Frontend build | Yes | 25.2.1 | -- |
| pnpm | Frontend package manager | Yes | 10.28.2 | -- |
| Alembic | Database migrations | Yes | 1.18.4 | -- |
| PostgreSQL | Multi-tenant DB | No (not running locally) | -- | SQLite for dev/test |
| Redis | Distributed rate limiting | No | -- | In-memory rate limiting (single-worker) |
| Helm | Kubernetes deployment | No | -- | Chart authored without local Helm; CI validates |
| kubectl | Kubernetes management | No | -- | Not needed for chart authoring |

**Missing dependencies with no fallback:**
- None blocking. All development/testing can proceed with SQLite and in-memory alternatives.

**Missing dependencies with fallback:**
- PostgreSQL: Tests use SQLite; integration testing with PostgreSQL can use docker-compose.dev.yml
- Redis: In-memory rate limiting works for single-worker dev; Redis only needed for production multi-worker
- Helm/kubectl: Chart files are YAML templates; validation can happen in CI

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.0+ with pytest-asyncio 0.24+ |
| Config file | backend/pyproject.toml [tool.pytest.ini_options] |
| Quick run command | `cd backend && uv run pytest tests/ -x -q --timeout=30` |
| Full suite command | `cd backend && uv run pytest tests/ -q --timeout=30` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INTEGRATE-01 | Clio adapter push/pull/sync | unit | `cd backend && uv run pytest tests/test_cms_clio.py -x` | No -- Wave 0 |
| INTEGRATE-02 | MyCase adapter push/pull/sync | unit | `cd backend && uv run pytest tests/test_cms_mycase.py -x` | No -- Wave 0 |
| INTEGRATE-03 | LegalServer adapter push/pull/sync | unit | `cd backend && uv run pytest tests/test_cms_legalserver.py -x` | No -- Wave 0 |
| DEPLOY-02 | Multi-tenant mode startup + schema creation | unit | `cd backend && uv run pytest tests/test_deployment_mode.py -x` | No -- Wave 0 |
| DEPLOY-03 | Single-tenant mode startup + SQLite | unit | `cd backend && uv run pytest tests/test_deployment_mode.py -x` | No -- Wave 0 |
| DEPLOY-05 | Persistence mode lifecycle (ephemeral/persistent/CMS) | unit | `cd backend && uv run pytest tests/test_persistence_mode.py -x` | No -- Wave 0 |
| DEPLOY-06 | /health extended checks + /metrics endpoint | unit | `cd backend && uv run pytest tests/test_monitoring.py -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `cd backend && uv run pytest tests/ -x -q --timeout=30`
- **Per wave merge:** `cd backend && uv run pytest tests/ -q --timeout=30`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_cms_clio.py` -- covers INTEGRATE-01
- [ ] `tests/test_cms_mycase.py` -- covers INTEGRATE-02
- [ ] `tests/test_cms_legalserver.py` -- covers INTEGRATE-03
- [ ] `tests/test_deployment_mode.py` -- covers DEPLOY-02, DEPLOY-03
- [ ] `tests/test_persistence_mode.py` -- covers DEPLOY-05
- [ ] `tests/test_monitoring.py` -- covers DEPLOY-06 (/health, /metrics)
- [ ] `tests/test_security_headers.py` -- covers D-11 security hardening
- [ ] `tests/test_rate_limiting.py` -- covers D-11 rate limiting
- [ ] `tests/test_tenant_provisioning.py` -- covers D-10 provisioning flows

## Sources

### Primary (HIGH confidence)
- Existing codebase: `backend/app/config.py`, `backend/app/main.py`, `backend/app/middleware/tenant.py`, `backend/app/services/deletion_service.py`, `backend/app/db/engine.py`, `backend/app/db/tenant.py`, `backend/app/services/tenant_service.py`, `backend/alembic/env.py`
- PyPI package index: verified versions for opentelemetry-api (1.40.0), opentelemetry-sdk (1.40.0), structlog (25.5.0), slowapi (0.1.9), prometheus-client (0.24.1), prometheus-fastapi-instrumentator (7.1.0)
- [Alembic Cookbook - Multi-Tenant](https://alembic.sqlalchemy.org/en/latest/cookbook.html) -- Schema-per-tenant migration pattern
- [OpenTelemetry Python Contrib - FastAPI](https://opentelemetry-python-contrib.readthedocs.io/en/latest/instrumentation/fastapi/fastapi.html) -- Auto-instrumentation

### Secondary (MEDIUM confidence)
- [Clio Developer Documentation](https://docs.developers.clio.com/) -- API v4, OAuth2, region-specific base URLs
- [MyCase API Documentation](https://mycaseapi.stoplight.io/) -- REST API, Advanced tier requirement
- [LegalServer API Documentation](https://www.apidocs.legalserver.org) -- REST API, Premium API pricing
- [Helm Charts Best Practices 2026](https://tech-insider.org/kubernetes-helm-chart-tutorial-deploy-applications-2026/) -- Helm 4 features
- [structlog JSON + OTel integration](https://johal.in/structlog-json-logs-middleware-opentelemetry-python-2026/) -- Processor chain pattern
- [slowapi GitHub](https://github.com/laurentS/slowapi) -- Redis backend, custom key functions

### Tertiary (LOW confidence)
- CMS field-level mapping details (Clio contacts/matters field names, MyCase case schema, LegalServer matter schema) -- official API docs could not be scraped; field mappings must be verified during implementation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all packages verified on PyPI with current versions; all are established production libraries
- Architecture: HIGH -- extends existing patterns in the codebase (adapter ABC, middleware, env-var config)
- CMS APIs: MEDIUM -- official documentation exists but field-level details could not be scraped; adapter implementations will need to reference live API docs
- Pitfalls: HIGH -- based on established patterns in multi-tenant systems, OTel, and CMS integration
- Deployment/Helm: MEDIUM -- Helm 4 is new (Nov 2025) but charts follow stable conventions; no local Helm to validate

**Research date:** 2026-04-03
**Valid until:** 2026-05-03 (30 days; stable domain, no fast-moving dependencies)
