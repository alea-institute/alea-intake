---
phase: 11-integration-production-deployment
plan: 02
subsystem: integrations
tags: [cms, clio, mycase, legalserver, sync, oauth2, api-key, httpx, adapter-pattern]

# Dependency graph
requires:
  - phase: 11-01
    provides: "Observability/health infra, cms_enabled and cms_sync_interval_seconds settings"
provides:
  - "CMSAdapter ABC with uniform push/pull/webhook interface"
  - "ClioAdapter for Clio Manage v4 API (OAuth2)"
  - "MyCaseAdapter for MyCase v1 API (OAuth2/API key)"
  - "LegalServerAdapter for LegalServer Premium API (API key)"
  - "CMSSyncQueue async background job processor"
  - "Canonical field mapping functions (intake->contact, intake->matter, output->document)"
  - "CMSSyncRecord and CMSConnectorConfig DB models"
  - "CMS admin API at /api/v1/admin/cms"
affects: [11-03, 11-04, production-deployment]

# Tech tracking
tech-stack:
  added: [httpx (already present, new usage for CMS)]
  patterns: [CMS adapter ABC mirroring ResearchAdapter, two-layer field mapping (canonical then CMS-specific), async sync queue with retry/backoff]

key-files:
  created:
    - backend/app/integrations/__init__.py
    - backend/app/integrations/cms/__init__.py
    - backend/app/integrations/cms/base.py
    - backend/app/integrations/cms/sync_queue.py
    - backend/app/integrations/cms/field_mapping.py
    - backend/app/integrations/cms/clio.py
    - backend/app/integrations/cms/mycase.py
    - backend/app/integrations/cms/legalserver.py
    - backend/app/models/cms.py
    - backend/app/routers/cms_admin.py
    - backend/tests/test_cms_base.py
    - backend/tests/test_cms_clio.py
    - backend/tests/test_cms_mycase.py
    - backend/tests/test_cms_legalserver.py
    - backend/tests/test_cms_admin.py
  modified:
    - backend/app/models/__init__.py
    - backend/app/main.py

key-decisions:
  - "CMSAdapter ABC mirrors ResearchAdapter pattern from Phase 6 for consistency"
  - "Two-layer field mapping: canonical dicts first, then CMS-specific translation in each adapter"
  - "LegalServer uses API key auth (not OAuth) -- contacts are matter participants"
  - "In-memory connector store for MVP admin API; production uses CMSConnectorConfig DB model"
  - "Sync queue uses asyncio.Queue with MAX_RETRIES=3 and exponential backoff"

patterns-established:
  - "CMS adapter ABC: CMSAdapter with push_contact/push_matter/push_document/pull_updates/handle_webhook/test_connection"
  - "Token refresh guard: _refresh_token_if_needed() called before every API request (Pitfall 4)"
  - "Canonical field mapping: CMS-neutral dicts as intermediate representation between ALEA and CMS-specific formats"

requirements-completed: [INTEGRATE-01, INTEGRATE-02, INTEGRATE-03]

# Metrics
duration: 7min
completed: 2026-04-06
---

# Phase 11 Plan 02: CMS Sync Connectors Summary

**Bidirectional CMS sync adapters for Clio/MyCase/LegalServer with async queue, canonical field mapping, and admin CRUD API**

## Performance

- **Duration:** 7 min
- **Started:** 2026-04-06T21:22:37Z
- **Completed:** 2026-04-06T21:30:13Z
- **Tasks:** 2
- **Files modified:** 17

## Accomplishments
- CMSAdapter ABC defining uniform interface for all CMS connectors with push/pull/webhook/test_connection
- Three production-ready CMS adapters: Clio (OAuth2, v4 API), MyCase (OAuth2/API key, v1 API), LegalServer (API key, Premium API)
- Background async sync queue with retry (3 attempts) and exponential backoff
- Two-layer field mapping isolating CMS-specific quirks from shared sync logic
- Admin API with full CRUD for connector configs plus test/sync/status endpoints
- 33 tests covering all adapters, queue, mapping, and admin schemas

## Task Commits

Each task was committed atomically:

1. **Task 1: CMS adapter ABC, models, sync queue, and field mapping** - `686cf1f` (feat)
2. **Task 2: Clio, MyCase, and LegalServer adapters with admin API** - `a85cc9b` (feat)

## Files Created/Modified
- `backend/app/integrations/cms/base.py` - CMSAdapter ABC, SyncDirection enum, CMSSyncConfig dataclass
- `backend/app/integrations/cms/sync_queue.py` - Async sync queue with retry/backoff
- `backend/app/integrations/cms/field_mapping.py` - Canonical ALEA-to-CMS field mapping
- `backend/app/integrations/cms/clio.py` - Clio Manage v4 API adapter (OAuth2)
- `backend/app/integrations/cms/mycase.py` - MyCase v1 API adapter (OAuth2/API key)
- `backend/app/integrations/cms/legalserver.py` - LegalServer Premium API adapter (API key)
- `backend/app/models/cms.py` - CMSSyncRecord and CMSConnectorConfig DB models
- `backend/app/routers/cms_admin.py` - CMS admin API endpoints
- `backend/app/main.py` - Wired cms_admin_router and sync queue worker in lifespan
- `backend/app/models/__init__.py` - Registered CMS models for Alembic
- `backend/tests/test_cms_base.py` - 12 tests for base ABC, queue, mapping, models
- `backend/tests/test_cms_clio.py` - 7 tests for Clio adapter
- `backend/tests/test_cms_mycase.py` - 4 tests for MyCase adapter
- `backend/tests/test_cms_legalserver.py` - 5 tests for LegalServer adapter
- `backend/tests/test_cms_admin.py` - 5 tests for admin API schemas/router

## Decisions Made
- **CMSAdapter mirrors ResearchAdapter pattern:** Consistent adapter ABC approach across the codebase
- **Two-layer field mapping:** Canonical dicts as intermediate representation prevents tight coupling between ALEA entities and CMS-specific field names
- **LegalServer uses API key auth:** LegalServer Premium APIs use API keys, not OAuth2; contacts are matter participants (no standalone contacts endpoint)
- **In-memory connector store for MVP:** Admin API uses dict-backed store; production wires through CMSConnectorConfig SQLAlchemy model
- **MAX_RETRIES=3 with exponential backoff:** Balances reliability with resource consumption for failed sync jobs

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. CMS connectors are configured at runtime via the admin API when organizations provide their CMS credentials.

## Known Stubs

- `backend/app/routers/cms_admin.py` - Connector storage uses in-memory dict instead of CMSConnectorConfig DB model (admin API functional but not persisted across restarts; production wires DB via existing TenantBase pattern)

## Next Phase Readiness
- CMS adapter infrastructure complete; ready for end-to-end integration testing in Plan 03
- Admin API provides CRUD + test + sync trigger endpoints for all three CMS providers
- Background sync queue worker starts automatically when cms_enabled=True

## Self-Check: PASSED

All 15 created files verified present. Both task commits (686cf1f, a85cc9b) verified in git log.

---
*Phase: 11-integration-production-deployment*
*Completed: 2026-04-06*
