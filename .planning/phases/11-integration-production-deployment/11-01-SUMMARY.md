---
phase: 11-integration-production-deployment
plan: 01
subsystem: infra
tags: [opentelemetry, prometheus, structlog, security-headers, rate-limiting, slowapi, observability]

# Dependency graph
requires:
  - phase: 01-foundation-security
    provides: FastAPI app, Settings, middleware stack, DB engine
provides:
  - Extended Settings with deployment, persistence, OTel, security, rate-limit, CMS fields
  - OpenTelemetry tracing (opt-in via ALEA_OTEL_ENDPOINT)
  - Prometheus /metrics endpoint with custom domain metrics
  - Extended /health with component-level checks (DB, FOLIO OWL, folio-mcp, LLM)
  - structlog JSON logging with OTel trace correlation
  - SecurityHeadersMiddleware (CSP, HSTS, X-Content-Type-Options, X-Frame-Options, Referrer-Policy)
  - Rate limiting via slowapi with proxy header support
affects: [11-02, 11-03, 11-04]

# Tech tracking
tech-stack:
  added: [opentelemetry-api, opentelemetry-sdk, opentelemetry-exporter-otlp-proto-http, opentelemetry-instrumentation-fastapi, structlog, slowapi, prometheus-client, prometheus-fastapi-instrumentator]
  patterns: [opt-in OTel via empty endpoint guard, split Prometheus setup at app-creation vs OTel at lifespan, component-level health aggregation with degraded status]

key-files:
  created:
    - backend/app/observability/__init__.py
    - backend/app/observability/telemetry.py
    - backend/app/observability/metrics.py
    - backend/app/observability/health.py
    - backend/app/observability/logging.py
    - backend/app/middleware/security.py
    - backend/app/middleware/rate_limit.py
    - backend/tests/test_monitoring.py
    - backend/tests/test_security_headers.py
    - backend/tests/test_rate_limiting.py
  modified:
    - backend/app/config.py
    - backend/app/main.py
    - backend/app/middleware/tenant.py
    - backend/pyproject.toml

key-decisions:
  - "Prometheus instrumentation at app creation time (not lifespan) so /metrics route is registered before route resolution"
  - "OTel tracing stays in lifespan since it only configures providers, not routes"
  - "Health check returns 'degraded' not 'unhealthy' when components fail -- partial functionality still available"
  - "Rate limit key_func reads header value directly (not parsed first-IP) for maximum flexibility"
  - "SecurityHeadersMiddleware added between CORS and Session in middleware stack"

patterns-established:
  - "Opt-in OTel: empty ALEA_OTEL_ENDPOINT means complete no-op, no crash"
  - "Component health aggregation: each subsystem returns {status, ...details}, aggregator sets overall to degraded if any down"
  - "Prometheus route at module level, OTel at lifespan: separation prevents route registration timing issues"

requirements-completed: [DEPLOY-06]

# Metrics
duration: 7min
completed: 2026-04-06
---

# Phase 11 Plan 01: Observability, Security Headers, and Rate Limiting Summary

**OTel tracing (opt-in), Prometheus /metrics, structlog with trace correlation, CSP/HSTS security headers, and slowapi rate limiting with proxy support**

## Performance

- **Duration:** 7 min
- **Started:** 2026-04-06T21:13:16Z
- **Completed:** 2026-04-06T21:20:29Z
- **Tasks:** 2
- **Files modified:** 14

## Accomplishments
- Extended Settings with 17 new fields (deployment, persistence, OTel, logging, rate-limit, security, CMS) for all Phase 11 plans
- Built complete observability stack: OTel tracing (opt-in), Prometheus metrics with 4 custom domain counters/histograms, structlog JSON logging with OTel trace_id/span_id correlation
- Extended /health endpoint with component-level checks (database, FOLIO OWL, folio-mcp, LLM provider) returning degraded status on failures
- Added SecurityHeadersMiddleware with configurable CSP and HSTS, plus X-Content-Type-Options, X-Frame-Options, Referrer-Policy
- Added rate limiting via slowapi with X-Forwarded-For support for reverse proxy deployments and exempt paths

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend Settings and build observability stack** - `b57055b` (feat)
2. **Task 2: Security headers middleware and rate limiting** - `4e7bfeb` (feat)

## Files Created/Modified
- `backend/app/config.py` - Added DeploymentMode, PersistenceMode enums and 17 Settings fields
- `backend/app/observability/telemetry.py` - OTel TracerProvider setup + Prometheus instrumentator
- `backend/app/observability/metrics.py` - Custom Prometheus counters/histograms for intake domain
- `backend/app/observability/health.py` - Component-level health checks with degraded aggregation
- `backend/app/observability/logging.py` - structlog JSON/console config with OTel correlation processor
- `backend/app/middleware/security.py` - SecurityHeadersMiddleware (CSP, HSTS, X-Frame-Options, etc.)
- `backend/app/middleware/rate_limit.py` - slowapi rate limiting with proxy header key function
- `backend/app/main.py` - Wired observability, security, rate limiting; updated version to 1.0.0
- `backend/app/middleware/tenant.py` - Added /metrics to PUBLIC_ROUTES
- `backend/tests/test_monitoring.py` - 21 tests for Settings, OTel, health, metrics, logging
- `backend/tests/test_security_headers.py` - 5 tests for security header presence
- `backend/tests/test_rate_limiting.py` - 5 tests for rate limiting behavior

## Decisions Made
- Prometheus instrumentation separated to app creation time (not lifespan) to ensure /metrics route is registered before route resolution -- OTel tracing remains in lifespan
- Health check returns "degraded" (not "unhealthy") when components fail, since partial functionality is still available
- Rate limit key_func reads X-Forwarded-For header value directly for maximum flexibility behind reverse proxies
- SecurityHeadersMiddleware placed between CORS and Session in middleware execution order

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Split setup_telemetry into setup_telemetry + setup_prometheus**
- **Found during:** Task 1 (wiring /metrics endpoint)
- **Issue:** Prometheus /metrics route registered during lifespan was not visible to route resolution; 404 on /metrics
- **Fix:** Separated Prometheus instrumentator into setup_prometheus() called at app creation time (module level), kept OTel tracing in setup_telemetry() during lifespan
- **Files modified:** backend/app/observability/telemetry.py, backend/app/main.py
- **Verification:** /metrics endpoint returns 200 with Prometheus text format
- **Committed in:** b57055b (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Route registration timing fix was necessary for /metrics to work. No scope creep.

## Issues Encountered
None beyond the deviation above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All Phase 11 Settings fields are available for Plans 02-04
- Observability stack is operational -- downstream plans can emit custom metrics and use structured logging
- Security headers and rate limiting are active on all endpoints

## Self-Check: PASSED

All 10 created files verified present on disk. Both commit hashes (b57055b, 4e7bfeb) verified in git log.

---
*Phase: 11-integration-production-deployment*
*Completed: 2026-04-06*
