---
phase: 01-foundation-security
plan: 01
subsystem: database, api, infra
tags: [fastapi, sqlalchemy, pydantic, asyncpg, aiosqlite, alembic, multi-tenant, schema-per-tenant]

# Dependency graph
requires:
  - phase: none
    provides: greenfield project
provides:
  - FastAPI app skeleton with /health endpoint and lifespan management
  - Pydantic Settings with ALEA_ env prefix and DatabaseBackend/LLMDataPolicy enums
  - Async engine factory supporting PostgreSQL (asyncpg) and SQLite (aiosqlite)
  - TenantBase and SharedBase declarative bases with naming conventions
  - All SQLAlchemy models -- Organization, User, AuditLog, ConsentRecord, ConsentTemplate, OrganizationConfig
  - Pydantic schemas for auth, user, organization, audit, consent
  - Schema-per-tenant session management with schema_translate_map
  - TenantMiddleware for per-request tenant resolution from X-Tenant-Slug header
  - TenantService for org CRUD and schema provisioning
  - Alembic configured for multi-schema migrations
  - Test conftest with async fixtures and SQLite in-memory backend
  - Custom exception classes (TenantNotFoundError, EncryptionError, ConsentRequiredError, InsufficientPermissionsError)
affects: [01-02, 01-03, 01-04, 01-05, all-subsequent-phases]

# Tech tracking
tech-stack:
  added: [fastapi, uvicorn, sqlalchemy, alembic, pydantic, pydantic-settings, pyjwt, pwdlib, cryptography, python-multipart, python-dotenv, alea-llm-client, httpx, asyncpg, psycopg, aiosqlite, pgvector, pytest, pytest-asyncio, factory-boy, ruff, pytest-timeout, email-validator]
  patterns: [schema-per-tenant isolation, async engine factory, lifespan context manager, exception handler registration, pydantic settings with env prefix]

key-files:
  created:
    - backend/app/main.py
    - backend/app/config.py
    - backend/app/db/engine.py
    - backend/app/db/base.py
    - backend/app/db/session.py
    - backend/app/db/tenant.py
    - backend/app/models/shared.py
    - backend/app/models/user.py
    - backend/app/models/audit.py
    - backend/app/models/consent.py
    - backend/app/models/organization.py
    - backend/app/middleware/tenant.py
    - backend/app/services/tenant_service.py
    - backend/app/schemas/auth.py
    - backend/app/schemas/user.py
    - backend/app/schemas/organization.py
    - backend/app/schemas/audit.py
    - backend/app/schemas/consent.py
    - backend/app/core/exceptions.py
    - backend/tests/conftest.py
    - backend/alembic/env.py
    - backend/pyproject.toml
    - .env.example
    - .gitignore
    - package.json
    - pnpm-workspace.yaml
  modified: []

key-decisions:
  - "Used pydantic[email] extra for EmailStr validation (email-validator dependency)"
  - "TenantMiddleware skips public routes (/health, /docs, auth endpoints) -- no tenant required"
  - "Test fixtures use aiosqlite in-memory for speed; schema isolation is a no-op on SQLite"
  - "LargeBinary columns for PII fields (full_name, llm_api_key_encrypted) ready for encryption layer in Plan 03"

patterns-established:
  - "Schema-per-tenant: TenantBase metadata has schema='tenant', session uses schema_translate_map to route"
  - "Settings pattern: get_settings() with lru_cache for testability (clear cache in tests)"
  - "Engine singleton: module-level _engine with get_engine()/dispose_engine() lifecycle"
  - "Exception handlers: registered on FastAPI app with appropriate HTTP status codes"
  - "Alembic multi-schema: -x tenant=schema_name flag for per-tenant migrations"

requirements-completed: [DEPLOY-01, SECURITY-10]

# Metrics
duration: 5min
completed: 2026-03-22
---

# Phase 1 Plan 01: Project Scaffolding Summary

**FastAPI skeleton with async PostgreSQL/SQLite engine, schema-per-tenant isolation, 6 SQLAlchemy models, Pydantic schemas, and test harness**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-22T23:55:12Z
- **Completed:** 2026-03-22T23:59:47Z
- **Tasks:** 2
- **Files modified:** 40

## Accomplishments
- Complete backend project structure matching RESEARCH.md architecture
- All 6 SQLAlchemy models with correct column types (LargeBinary for encrypted PII, JSON for flexible config)
- Schema-per-tenant isolation via SQLAlchemy schema_translate_map with TenantMiddleware
- Async engine factory supporting both PostgreSQL (asyncpg) and SQLite (aiosqlite) backends
- Test infrastructure with async fixtures, in-memory SQLite, and pre-built org/user fixtures

## Task Commits

Each task was committed atomically:

1. **Task 1: Project scaffolding, config, and database engine** - `a63b59f` (feat)
2. **Task 2: Data models, schemas, tenant isolation, and test harness** - `7755502` (feat)

## Files Created/Modified
- `backend/pyproject.toml` - Project dependencies and tool configuration
- `backend/app/main.py` - FastAPI app with lifespan, CORS, exception handlers, TenantMiddleware, /health
- `backend/app/config.py` - Pydantic Settings with DatabaseBackend and LLMDataPolicy enums
- `backend/app/db/engine.py` - Async engine factory for PostgreSQL and SQLite
- `backend/app/db/base.py` - TenantBase and SharedBase declarative bases with naming conventions
- `backend/app/db/session.py` - Tenant-scoped and shared session factories with schema_translate_map
- `backend/app/db/tenant.py` - Tenant schema resolution and creation
- `backend/app/models/shared.py` - Organization model (shared schema, tenant registry)
- `backend/app/models/user.py` - User model with Role enum, LargeBinary full_name for encryption
- `backend/app/models/audit.py` - AuditLog model with timestamp+action index
- `backend/app/models/consent.py` - ConsentRecord and ConsentTemplate models
- `backend/app/models/organization.py` - OrganizationConfig model with encrypted LLM key field
- `backend/app/middleware/tenant.py` - TenantMiddleware resolving org from X-Tenant-Slug header
- `backend/app/services/tenant_service.py` - TenantService for org CRUD and schema provisioning
- `backend/app/schemas/auth.py` - LoginRequest, TokenResponse, RegisterRequest, RefreshRequest
- `backend/app/schemas/user.py` - UserResponse, UserCreate
- `backend/app/schemas/organization.py` - OrganizationResponse, OrganizationCreate
- `backend/app/schemas/audit.py` - AuditLogResponse, AuditLogQuery
- `backend/app/schemas/consent.py` - ConsentGrantRequest, ConsentResponse, ConsentTemplateResponse
- `backend/app/core/exceptions.py` - TenantNotFoundError, EncryptionError, ConsentRequiredError, InsufficientPermissionsError
- `backend/tests/conftest.py` - Async test fixtures with SQLite in-memory backend
- `backend/alembic/env.py` - Multi-schema Alembic environment
- `backend/alembic/alembic.ini` - Alembic configuration
- `backend/alembic/script.py.mako` - Migration template
- `.env.example` - All ALEA_ environment variables with placeholders
- `.gitignore` - Python, Node, IDE, env, data exclusions
- `package.json` - Workspace root
- `pnpm-workspace.yaml` - Frontend workspace

## Decisions Made
- **pydantic[email] extra:** Added email-validator dependency for EmailStr validation in auth/user schemas
- **TenantMiddleware public routes:** /health, /docs, /openapi.json, /redoc, and auth endpoints skip tenant resolution
- **Test database:** aiosqlite in-memory for fast isolated tests; schema isolation is no-op on SQLite
- **PII field types:** LargeBinary for full_name and llm_api_key_encrypted, ready for encryption in Plan 03

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added pydantic[email] extra for EmailStr support**
- **Found during:** Task 2 (verifying schema imports)
- **Issue:** EmailStr in auth.py and user.py schemas requires email-validator package, which is not installed by default with pydantic
- **Fix:** Changed `pydantic>=2.12.0` to `pydantic[email]>=2.12.0` in pyproject.toml
- **Files modified:** backend/pyproject.toml
- **Verification:** All schema imports succeed
- **Committed in:** 7755502 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Essential fix for EmailStr validation. No scope creep.

## Issues Encountered
None beyond the auto-fixed email-validator dependency.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Foundation complete: all models, schemas, and infrastructure ready
- Plan 02 (JWT auth) can build on User model, Settings config, and test fixtures
- Plan 03 (encryption) can implement field-level crypto on LargeBinary columns
- Plan 04 (audit/consent) can use AuditLog and ConsentRecord models
- Plan 05 (LLM/Docker) can use OrganizationConfig and engine factory

## Self-Check: PASSED

All 26 created files verified on disk. Both commit hashes (a63b59f, 7755502) confirmed in git log.

---
*Phase: 01-foundation-security*
*Completed: 2026-03-22*
