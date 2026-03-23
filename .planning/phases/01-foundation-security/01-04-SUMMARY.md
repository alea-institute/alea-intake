---
phase: 01-foundation-security
plan: 04
subsystem: security, audit, consent
tags: [audit-logging, middleware, consent-management, right-to-delete, cascade-deletion, rbac]

# Dependency graph
requires:
  - phase: 01-foundation-security/01
    provides: AuditLog and ConsentRecord models, Organization with deletion_policy/consent_mode, test conftest
  - phase: 01-foundation-security/02
    provides: JWT auth, RBAC permissions (require_role, get_current_active_user), RefreshToken model
provides:
  - AuditService for creating and querying immutable audit log entries
  - AuditMiddleware generating UUID request_id and logging all API requests
  - Admin-only audit log query endpoints with action/actor/date filters
  - ConsentService for grant, revoke, check, status, and template retrieval
  - ConsentMiddleware blocking AI-processing endpoints without active consent
  - Consent API endpoints (grant, revoke, status, template)
  - DeletionService with preview hash confirmation and three deletion policies
  - Admin-only deletion preview and confirm endpoints
affects: [01-05, 02-intake-forms, 03-ai-analysis, 08-frontend, all-phases-with-ai-endpoints]

# Tech tracking
tech-stack:
  added: []
  patterns: [separate-session-audit-logging, consent-middleware-enforcement, preview-hash-confirmation, org-configurable-deletion-policy]

key-files:
  created:
    - backend/app/services/audit_service.py
    - backend/app/middleware/audit.py
    - backend/app/routers/audit.py
    - backend/app/services/consent_service.py
    - backend/app/middleware/consent.py
    - backend/app/routers/consent.py
    - backend/app/services/deletion_service.py
    - backend/app/routers/admin.py
    - backend/tests/test_audit.py
    - backend/tests/test_consent.py
    - backend/tests/test_deletion.py
  modified:
    - backend/app/main.py
    - backend/tests/conftest.py

key-decisions:
  - "Audit middleware uses separate DB session (engine.begin()) for isolation from request transaction -- audit persists even on request rollback"
  - "Temp-file SQLite for async_client fixture instead of in-memory -- required for multi-connection audit middleware to access same database"
  - "ConsentMiddleware checks AI_PROCESSING_PREFIXES (/analysis, /intake, /research) and decodes JWT independently for user_id"
  - "Deletion preview uses SHA-256 hash of preview data for stale-detection confirmation"
  - "Seeded test Organization in async_client fixture for admin endpoint testing"

patterns-established:
  - "Separate-session audit: middleware creates its own engine.begin() context for audit writes, isolated from request transaction"
  - "Consent enforcement: ConsentMiddleware blocks AI endpoints, returns 403 with consent-specific error messages"
  - "Preview-confirm pattern: deletion preview returns hash, confirm verifies hash to prevent stale/accidental deletions"
  - "Org-configurable deletion: DeletionService reads org.deletion_policy to choose full_delete, anonymize, or time_based behavior"

requirements-completed: [SECURITY-05, SECURITY-07, SECURITY-08]

# Metrics
duration: 12min
completed: 2026-03-23
---

# Phase 1 Plan 04: Audit, Consent & Deletion Summary

**Immutable audit logging middleware with request correlation, consent enforcement blocking AI endpoints, and right-to-delete cascade with org-configurable audit trail handling (full delete, anonymize, time-based)**

## Performance

- **Duration:** 12 min
- **Started:** 2026-03-23T00:18:26Z
- **Completed:** 2026-03-23T00:31:12Z
- **Tasks:** 2 (both TDD)
- **Files modified:** 13

## Accomplishments
- Audit middleware logs every API request with UUID correlation ID, actor, action, IP, and response status
- Admin-only audit log query endpoints with filtering by action, actor, and date range
- Consent service with full lifecycle: grant (revokes previous), revoke (immediate), check, status
- Consent middleware blocks AI-processing endpoints (/analysis, /intake, /research) without active consent
- Right-to-delete cascade with preview showing record counts, SHA-256 hash confirmation, and three org-configurable deletion policies
- 27 new tests (10 audit + 9 consent + 8 deletion), 93 total passing

## Task Commits

Each task was committed atomically:

1. **Task 1: Audit logging service, middleware, and query endpoint (TDD)**
   - `67df108` (test) -- RED: 10 failing tests for audit service, middleware, and endpoints
   - `9e59281` (feat) -- GREEN: AuditService, AuditMiddleware, audit router, all 10 tests passing

2. **Task 2: Consent management, enforcement middleware, and right-to-delete cascade (TDD)**
   - `21c0195` (test) -- RED: 17 failing tests for consent and deletion
   - `8a88e05` (feat) -- GREEN: ConsentService, ConsentMiddleware, DeletionService, admin router, all 17 tests passing

## Files Created/Modified
- `backend/app/services/audit_service.py` - AuditService with log_action and query_logs
- `backend/app/middleware/audit.py` - AuditMiddleware with UUID request_id, X-Request-ID header, separate-session logging
- `backend/app/routers/audit.py` - Admin-only GET /api/v1/audit/ with filters and GET /api/v1/audit/{id}
- `backend/app/services/consent_service.py` - ConsentService with grant, revoke, check, status, template retrieval
- `backend/app/middleware/consent.py` - ConsentMiddleware enforcing consent on AI-processing prefixes
- `backend/app/routers/consent.py` - POST /grant (201), POST /revoke, GET /status, GET /template
- `backend/app/services/deletion_service.py` - DeletionService with preview (SHA-256 hash), confirm cascade, three policies
- `backend/app/routers/admin.py` - GET /deletion/preview/{id} and POST /deletion/confirm (admin-only)
- `backend/app/main.py` - Added AuditMiddleware, ConsentMiddleware, audit/consent/admin routers
- `backend/tests/conftest.py` - Temp-file SQLite for async_client, seeded Organization, schema_translate_map for async_session
- `backend/tests/test_audit.py` - 10 tests for audit logging
- `backend/tests/test_consent.py` - 9 tests for consent management
- `backend/tests/test_deletion.py` - 8 tests for right-to-delete cascade

## Decisions Made
- **Separate-session audit logging:** Audit middleware uses its own `engine.begin()` context, not the request's session. This ensures audit entries persist even if the request transaction rolls back. Required switching async_client fixture from in-memory SQLite to temp-file SQLite since in-memory databases with StaticPool don't properly support multiple concurrent connection contexts.
- **Temp-file SQLite for integration tests:** In-memory SQLite with StaticPool has only one raw connection; when the audit middleware creates a separate session, the single-connection constraint causes data visibility issues. Temp-file SQLite allows true multi-connection access.
- **Organization seeding in async_client:** Admin endpoints need to query the Organization model for deletion_policy. Added Organization seed data to the async_client fixture to support this.
- **JWT decoding in consent middleware:** ConsentMiddleware independently decodes the JWT to extract user_id rather than relying on request.state (which is set by the auth dependency, not available at middleware level).
- **Preview hash for deletion safety:** DeletionService generates a deterministic SHA-256 hash from preview data (user_id, categories, total, deletion_policy) to detect stale previews when confirming deletion.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed in-memory SQLite multi-connection issue for audit middleware**
- **Found during:** Task 1 (audit middleware tests failing -- entries written but not visible)
- **Issue:** In-memory SQLite with StaticPool uses a single raw connection. The audit middleware's separate session context wrote data that wasn't visible to subsequent queries because of connection-level transaction isolation with the single connection.
- **Fix:** Changed async_client fixture to use temp-file SQLite instead of in-memory, allowing the audit middleware's separate connection to access the same database.
- **Files modified:** backend/tests/conftest.py
- **Verification:** All 10 audit tests pass
- **Committed in:** 9e59281

**2. [Rule 1 - Bug] Fixed async_session fixture missing schema_translate_map**
- **Found during:** Task 1 (unit tests failing with "no such table: tenant.audit_log")
- **Issue:** The async_session fixture created sessions without schema_translate_map, causing SQLite to look for schema-prefixed table names that don't exist.
- **Fix:** Changed async_session to use connection-level execution_options with schema_translate_map={"tenant": None, "shared": None}
- **Files modified:** backend/tests/conftest.py
- **Verification:** All unit tests pass
- **Committed in:** 9e59281

**3. [Rule 2 - Missing Critical] Seeded Organization in async_client fixture**
- **Found during:** Task 2 (deletion preview returning 500 "Organization not found")
- **Issue:** Admin deletion endpoints query the Organization model, but no Organization record existed in the async_client test database.
- **Fix:** Added Organization seed data creation after table setup in the async_client fixture.
- **Files modified:** backend/tests/conftest.py
- **Verification:** All deletion tests pass
- **Committed in:** 8a88e05

---

**Total deviations:** 3 auto-fixed (2 bugs, 1 missing critical)
**Impact on plan:** All fixes necessary for correctness. No scope creep.

## Issues Encountered
None beyond the auto-fixed deviations.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Audit logging captures all API requests -- future phases get audit trail automatically
- Consent enforcement blocks AI endpoints -- Phase 3 (AI Analysis) will be protected by default
- Right-to-delete cascade is extensible -- when case/narrative/document models are added in Phase 2, DeletionService just needs new delete statements
- All error messages match UI-SPEC copywriting contract for Phase 8 frontend integration

## Self-Check: PASSED

All 11 created files verified on disk. All 4 commit hashes (67df108, 9e59281, 21c0195, 8a88e05) confirmed in git log.

---
*Phase: 01-foundation-security*
*Completed: 2026-03-23*
