---
phase: 11-integration-production-deployment
plan: 03
subsystem: deployment
tags: [multi-tenant, single-tenant, schema-isolation, persistence, ephemeral, migration, provisioning, alembic]

requires:
  - phase: 11-01
    provides: "Config enums (DeploymentMode, PersistenceMode), settings fields, CMS adapter base"
provides:
  - "DeploymentMode branching: get_deployment_mode, is_multi_tenant, get_schema_translate_map"
  - "PersistenceManager: ephemeral/persistent/cms_integrated lifecycle"
  - "Auto-migration runner: shared-first then tenant schemas with failure isolation"
  - "TenantProvisioner: schema creation, protocol seeding, admin user"
  - "Mode-aware TenantMiddleware: single-tenant bypass"
affects: [intake-completion-hooks, admin-provisioning-api, deployment-config]

tech-stack:
  added: []
  patterns: [schema-translate-map-branching, ephemeral-ttl-scheduling, per-tenant-migration-isolation, signup-mode-gating]

key-files:
  created:
    - backend/app/deployment/__init__.py
    - backend/app/deployment/mode.py
    - backend/app/deployment/persistence.py
    - backend/app/deployment/provisioning.py
    - backend/app/deployment/migration_runner.py
    - backend/tests/test_deployment_mode.py
    - backend/tests/test_persistence_mode.py
    - backend/tests/test_tenant_provisioning.py
  modified:
    - backend/app/middleware/tenant.py
    - backend/app/main.py

key-decisions:
  - "get_schema_translate_map is the SINGLE source of schema naming -- all code calls it"
  - "Single-tenant maps both tenant and shared to None (public schema, no prefixes)"
  - "Ephemeral TTL starts from session completion, not creation (Pitfall 5 mitigation)"
  - "Ephemeral deletion anonymizes audit trail (actor_id=None) rather than deleting"
  - "Migration runner uses subprocess for alembic (compatibility with sync alembic env)"
  - "TenantProvisioner creates admin with random 20-char password"

patterns-established:
  - "Schema naming: always via get_schema_translate_map, never hardcoded"
  - "Deployment mode branching: is_multi_tenant() guard for mode-specific code paths"
  - "Ephemeral lifecycle: schedule deletion via asyncio.Task with TTL, cancel on resume"
  - "Per-tenant migration isolation: try/except per schema, log and continue"

requirements-completed: [DEPLOY-02, DEPLOY-03, DEPLOY-05]

duration: 5min
completed: 2026-04-06
---

# Phase 11 Plan 03: Deployment Mode & Persistence Summary

**Multi/single-tenant mode branching, org-configurable persistence lifecycle (ephemeral/persistent/CMS), auto-migration runner with per-tenant failure isolation, and tenant provisioning with schema creation + admin user**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-06T21:33:13Z
- **Completed:** 2026-04-06T21:38:29Z
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments
- Deployment mode branching with single source of truth for schema naming (get_schema_translate_map)
- TenantMiddleware single-tenant bypass: skips resolution, uses public schema
- PersistenceManager with three modes: ephemeral (auto-delete after TTL), persistent (retain), CMS-integrated (sync)
- Ephemeral deletion preserves anonymized audit trail and respects terminal-only session guard (Pitfall 5)
- Auto-migration runner: shared schema first, then per-tenant with failure isolation
- TenantProvisioner: creates schema, runs migration, seeds protocols, creates admin user with credentials

## Task Commits

Each task was committed atomically:

1. **Task 1: Deployment mode branching and auto-migration runner** - `809e8e7` (feat)
2. **Task 2: Persistence modes and tenant provisioning** - `8a0756d` (feat)

_TDD: Tests written first (RED), implementation second (GREEN), verified passing._

## Files Created/Modified
- `backend/app/deployment/__init__.py` - Empty package init
- `backend/app/deployment/mode.py` - DeploymentMode helpers: get_deployment_mode, is_multi_tenant, get_schema_translate_map
- `backend/app/deployment/migration_runner.py` - Auto-migration on startup with per-tenant isolation
- `backend/app/deployment/persistence.py` - PersistenceManager: ephemeral TTL scheduling, audit preservation
- `backend/app/deployment/provisioning.py` - TenantProvisioner: schema + migration + protocols + admin user
- `backend/app/middleware/tenant.py` - Added single-tenant mode bypass
- `backend/app/main.py` - Wired migration runner and PersistenceManager into lifespan
- `backend/tests/test_deployment_mode.py` - 12 tests for mode branching + migration runner
- `backend/tests/test_persistence_mode.py` - 11 tests for persistence modes
- `backend/tests/test_tenant_provisioning.py` - 6 tests for tenant provisioning

## Decisions Made
- **get_schema_translate_map as single source**: All schema naming goes through one function -- prevents inconsistent naming
- **Single-tenant maps to None**: Pitfall 7 -- both "tenant" and "shared" map to None so all tables live in public schema
- **Ephemeral TTL from completion**: Pitfall 5 -- TTL timer starts when session reaches terminal state, not when intake is created
- **Audit anonymization**: D-08 -- ephemeral deletion sets actor_id=None on audit log entries instead of deleting them
- **subprocess for alembic**: Alembic env.py uses synchronous engine; subprocess avoids event loop conflicts
- **Random 20-char admin password**: Provisioner generates and returns password for initial admin delivery

## Deviations from Plan

None -- plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None -- no external service configuration required.

## Next Phase Readiness
- Deployment mode infrastructure ready for Plan 04 (production hardening)
- PersistenceManager available on app.state for intake completion hooks
- TenantProvisioner ready for admin API endpoints

---
*Phase: 11-integration-production-deployment*
*Completed: 2026-04-06*
