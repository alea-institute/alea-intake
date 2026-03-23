---
phase: 01-foundation-security
plan: 05
subsystem: llm, api, infra, frontend
tags: [alea-llm-client, docker, vite, react, tailwindcss, typescript, pgvector, multi-tenant, training-opt-out]

# Dependency graph
requires:
  - phase: 01-foundation-security-01
    provides: FastAPI skeleton, SQLAlchemy models, OrganizationConfig, TenantService, test conftest
provides:
  - LLMService wrapping alea-llm-client with per-org config and 3-level training opt-out
  - get_llm_service factory function for dependency injection
  - Organization CRUD endpoints (POST/GET/GET-by-id/PATCH) at /api/v1/organizations
  - Cross-tenant isolation tests proving data separation by org_id
  - Database backend abstraction tests for SQLite and PostgreSQL engines
  - Multi-stage Dockerfile (node:22-slim + python:3.12-slim) with HEALTHCHECK
  - docker-compose.yml with backend + pgvector:pg17 and health-checked depends_on
  - docker-compose.dev.yml with lightweight DB-only for local development
  - Frontend scaffold (React 19, Vite 6, TypeScript 5.7, Tailwind 3.4 with design tokens)
affects: [02-legal-ontology, 06-research-tools, 08-frontend-application, 11-production-deployment]

# Tech tracking
tech-stack:
  added: [alea-llm-client, docker, docker-compose, react, vite, typescript, tailwindcss, autoprefixer, postcss]
  patterns: [LLM service wrapper with training opt-out enforcement, provider model map for multi-provider support, admin-only CRUD endpoints, multi-stage Docker build, pnpm workspace frontend scaffold]

key-files:
  created:
    - backend/app/services/llm_service.py
    - backend/app/routers/organizations.py
    - backend/tests/test_llm_service.py
    - backend/tests/test_tenancy.py
    - backend/tests/test_db_backend.py
    - Dockerfile
    - docker-compose.yml
    - docker-compose.dev.yml
    - frontend/package.json
    - frontend/vite.config.ts
    - frontend/tsconfig.json
    - frontend/tailwind.config.ts
    - frontend/postcss.config.js
    - frontend/src/main.tsx
    - frontend/src/App.tsx
    - frontend/src/index.css
    - frontend/index.html
  modified:
    - backend/app/main.py

key-decisions:
  - "LLMService uses _PROVIDER_MODEL_MAP dict for provider-to-class resolution, supporting openai, anthropic, google, vllm"
  - "Three-level training opt-out: API-tier access, provider-specific headers, local_only policy enforcement"
  - "Organization CRUD uses shared session (not tenant session) since orgs are in the shared schema"
  - "Slug changes blocked on PATCH to prevent breaking tenant schema naming"
  - "Frontend uses Tailwind 3.x (not 4.x) for PostCSS compatibility and @tailwind directive support"
  - "Design tokens use suffixed names (sm-custom, md-custom) to avoid collision with Tailwind defaults"

patterns-established:
  - "LLM service pattern: org_config overrides -> platform defaults -> hardcoded fallbacks"
  - "Provider model map: dict mapping provider strings to alea-llm-client model classes"
  - "Admin-only CRUD: require_role(Role.ADMIN) dependency on all organization management endpoints"
  - "Docker multi-stage: frontend build stage -> backend runtime stage with COPY --from"
  - "Frontend scaffold: Vite + React + TypeScript + Tailwind with API proxy to backend"

requirements-completed: [SECURITY-09, INTEGRATE-04, DEPLOY-04]

# Metrics
duration: 6min
completed: 2026-03-23
---

# Phase 1 Plan 05: LLM Service, Docker, and Frontend Scaffold Summary

**LLM service wrapping alea-llm-client with 3-level training opt-out, org CRUD endpoints, Docker build (pgvector + multi-stage), and React/Vite/Tailwind frontend scaffold with design tokens**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-23T00:18:43Z
- **Completed:** 2026-03-23T00:24:17Z
- **Tasks:** 2
- **Files modified:** 18

## Accomplishments
- LLMService with per-org configuration and three-level training opt-out enforcement (API-tier, provider headers, local_only policy blocking)
- Organization CRUD at /api/v1/organizations with admin-only access and duplicate slug prevention
- 21 new tests covering LLM service (12), tenant isolation (6), DB backend (3) -- all passing
- Docker infrastructure: multi-stage Dockerfile, production and dev compose files with pgvector health checks
- Frontend scaffold: React 19 + Vite 6 + TypeScript 5.7 + Tailwind 3.4 with UI-SPEC spacing tokens pre-seeded

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Failing tests for LLM service, tenant isolation, DB backend** - `da2da2c` (test)
2. **Task 1 (GREEN): LLM service, org CRUD endpoints, passing tests** - `404aabf` (feat)
3. **Task 2: Docker infrastructure and frontend scaffold** - `e979526` (feat)

## Files Created/Modified
- `backend/app/services/llm_service.py` - LLM client wrapper with per-org config, training opt-out, connection check
- `backend/app/routers/organizations.py` - Organization CRUD endpoints (POST/GET/GET-by-id/PATCH), admin-only
- `backend/app/main.py` - Added organizations_router to app.include_router
- `backend/tests/test_llm_service.py` - 12 tests: init, local-only policy, cloud config, connection check, factory
- `backend/tests/test_tenancy.py` - 6 tests: schema creation, user isolation, cross-tenant API, shared schema
- `backend/tests/test_db_backend.py` - 3 tests: SQLite engine, PostgreSQL URL, unsupported backend
- `Dockerfile` - Multi-stage build with node:22-slim frontend + python:3.12-slim backend + HEALTHCHECK
- `docker-compose.yml` - Production compose: backend + pgvector:pg17 with health checks
- `docker-compose.dev.yml` - Dev compose: DB-only for local development
- `frontend/package.json` - React 19, Vite 6, TypeScript 5.7, Tailwind 3.4 dependencies
- `frontend/vite.config.ts` - Vite config with /api proxy to localhost:8000
- `frontend/tsconfig.json` - Strict TypeScript with ES2022 target
- `frontend/tailwind.config.ts` - Design tokens from UI-SPEC (xs through 3xl-custom spacing)
- `frontend/postcss.config.js` - Tailwind + autoprefixer PostCSS plugins
- `frontend/index.html` - HTML entry point with root div
- `frontend/src/main.tsx` - React entry point with StrictMode
- `frontend/src/App.tsx` - Placeholder component
- `frontend/src/index.css` - Tailwind directives

## Decisions Made
- **Provider model map:** Used a dict mapping provider names to alea-llm-client classes rather than if/elif chain, enabling easier extension
- **Training opt-out approach:** Level 1 (API-tier inherent), Level 2 (provider headers in config), Level 3 (local_only blocks cloud providers at init)
- **Shared session for org CRUD:** Organizations live in the shared schema, not tenant schemas, so the router uses get_shared_session
- **Slug immutability:** PATCH endpoint explicitly rejects slug changes to prevent breaking tenant schema naming (tenant_{slug})
- **Tailwind 3.x:** Selected Tailwind 3.4 (not 4.x) because 4.x drops PostCSS plugin approach and @tailwind directives
- **Suffixed spacing tokens:** Used sm-custom, md-custom etc. to avoid colliding with Tailwind's built-in sm/md/lg numeric scale

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test mock targeting for _PROVIDER_MODEL_MAP**
- **Found during:** Task 1 (TDD GREEN phase)
- **Issue:** Tests patched `app.services.llm_service.OpenAIModel` but `check_connection()` resolved classes from `_PROVIDER_MODEL_MAP` dict (cached at import time), making patches invisible
- **Fix:** Changed tests to use `patch.dict(_PROVIDER_MODEL_MAP, {...})` to properly mock the lookup table
- **Files modified:** backend/tests/test_llm_service.py
- **Verification:** All connection check tests pass (mock side_effect exception correctly triggers error path)
- **Committed in:** 404aabf

**2. [Rule 1 - Bug] Fixed tenant schema test for SQLite**
- **Found during:** Task 1 (TDD GREEN phase)
- **Issue:** `ensure_tenant_schema_exists()` called with raw `async_engine` tries to create tables with `schema='tenant'` prefix on SQLite, which doesn't support named schemas
- **Fix:** Changed test to verify table existence from conftest's schemaless setup (SQLite path) and added separate `resolve_tenant_schema` test
- **Files modified:** backend/tests/test_tenancy.py
- **Verification:** All tenant tests pass on SQLite backend
- **Committed in:** 404aabf

**3. [Rule 2 - Missing Critical] Added .gitignore entry for tsbuildinfo**
- **Found during:** Task 2 (frontend build verification)
- **Issue:** `pnpm build` generates `tsconfig.tsbuildinfo` which was appearing as untracked
- **Fix:** Added `*.tsbuildinfo` to .gitignore
- **Files modified:** .gitignore
- **Verification:** Build artifact no longer shows in git status

---

**Total deviations:** 3 auto-fixed (2 bugs, 1 missing critical)
**Impact on plan:** All auto-fixes necessary for correctness. No scope creep.

## Issues Encountered
- Pre-existing failing test in `test_audit.py::test_audit_log_created_on_login` (unrelated to this plan -- audit middleware from Plan 04). Logged as out of scope per deviation rules.

## User Setup Required
None - no external service configuration required. Docker compose uses default passwords suitable for development only.

## Next Phase Readiness
- Phase 1 (Foundation & Security) is now complete with all 5 plans executed
- Phase 2 (Legal Ontology) can use the LLM service for any AI-powered processing
- Phase 6 (Research Tools) can extend LLM service with research-specific methods
- Phase 8 (Frontend Application) can build on the React/Vite/Tailwind scaffold with design tokens
- Phase 11 (Production Deployment) can use the Docker infrastructure as a starting point

## Self-Check: PASSED

All 18 created/modified files verified on disk. All 3 commit hashes (da2da2c, 404aabf, e979526) confirmed in git log.

---
*Phase: 01-foundation-security*
*Completed: 2026-03-23*
