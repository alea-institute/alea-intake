---
phase: 01-foundation-security
plan: 02
subsystem: auth, api
tags: [jwt, pyjwt, argon2, pwdlib, rbac, refresh-token-rotation, fastapi-dependencies]

# Dependency graph
requires:
  - phase: 01-foundation-security/01
    provides: User model with Role enum, Settings with secret_key/token expiry, TenantBase, test conftest
provides:
  - JWT access/refresh token creation and validation (PyJWT HS256)
  - Argon2 password hashing via pwdlib
  - ROLE_PERMISSIONS mapping for admin, professional, consumer
  - FastAPI auth dependencies (get_current_user, get_current_active_user, require_role, require_permission)
  - RefreshToken model with token family tracking and reuse detection
  - AuthService with register, login, refresh_tokens, logout
  - Auth API router (POST register, login, refresh, logout)
  - Users API router (GET /me, GET / admin-only, GET /{id})
affects: [01-03, 01-04, 01-05, all-subsequent-phases]

# Tech tracking
tech-stack:
  added: []
  patterns: [refresh-token-rotation-with-family-reuse-detection, fastapi-dependency-injection-rbac, sha256-token-storage, schema_translate_map-sqlite-fix]

key-files:
  created:
    - backend/app/core/security.py
    - backend/app/core/permissions.py
    - backend/app/models/refresh_token.py
    - backend/app/services/auth_service.py
    - backend/app/routers/auth.py
    - backend/app/routers/users.py
    - backend/tests/test_security.py
    - backend/tests/test_auth.py
  modified:
    - backend/app/models/__init__.py
    - backend/app/main.py
    - backend/app/core/security.py
    - backend/app/db/session.py
    - backend/app/middleware/tenant.py
    - backend/tests/conftest.py
    - backend/tests/test_rbac.py

key-decisions:
  - "Added jti (JWT ID) claim to refresh tokens for uniqueness across same-second rotations"
  - "Fixed SQLite schema_translate_map: schemaless table copies for create_all, connection-level execution_options instead of session-level"
  - "require_role checks DB user.role (authoritative) not JWT role claim (informational)"
  - "Refresh token stored as SHA-256 hash, never raw, for defense-in-depth"
  - "Token reuse detection revokes entire family, not just the replayed token"

patterns-established:
  - "Auth dependency chain: get_current_user -> get_current_active_user -> require_role/require_permission"
  - "Token family pattern: each login creates a new family; refresh rotates within family; reuse revokes family"
  - "Integration test pattern: register user via API, update role via direct DB update, create role-specific JWT"
  - "SQLite test pattern: to_metadata(schema=None) for table creation, schema_translate_map for queries"

requirements-completed: [SECURITY-01, SECURITY-02]

# Metrics
duration: 11min
completed: 2026-03-22
---

# Phase 1 Plan 02: JWT Auth & RBAC Summary

**JWT auth with rotating refresh tokens (PyJWT + Argon2), three-role RBAC via FastAPI dependency injection, and full auth API endpoints**

## Performance

- **Duration:** 11 min
- **Started:** 2026-03-23T00:03:46Z
- **Completed:** 2026-03-23T00:15:04Z
- **Tasks:** 2
- **Files modified:** 15

## Accomplishments
- JWT access tokens (30 min) and refresh tokens (7 days) with PyJWT HS256 and Argon2 password hashing
- Refresh token rotation with family-based reuse detection (replayed tokens revoke the entire family)
- Three-role RBAC (admin, professional, consumer) with granular permission sets enforced via FastAPI dependencies
- Full auth API: register (201), login, refresh, logout endpoints with exact UI-SPEC error messages
- Users API: /me (any user), / (admin-only), /{id} (role-based access)
- Fixed SQLite schema_translate_map compatibility for test infrastructure

## Task Commits

Each task was committed atomically:

1. **Task 1: JWT security, password hashing, RBAC permissions (TDD)**
   - `d3d4d38` (test: failing tests for security + RBAC)
   - `d47590f` (feat: implementation -- security.py, permissions.py, RefreshToken model)

2. **Task 2: Auth service, API endpoints, integration tests (TDD)**
   - `1423293` (test: failing integration tests for auth endpoints + RBAC)
   - `8b71849` (feat: AuthService, routers, conftest fixes, all tests passing)

## Files Created/Modified
- `backend/app/core/security.py` - JWT creation/validation, Argon2 password hashing
- `backend/app/core/permissions.py` - ROLE_PERMISSIONS dict, get_current_user, require_role, require_permission
- `backend/app/models/refresh_token.py` - RefreshToken model with token_family and token_hash
- `backend/app/models/__init__.py` - Added RefreshToken to exports
- `backend/app/services/auth_service.py` - AuthService with register, login, refresh_tokens, logout
- `backend/app/routers/auth.py` - Auth API endpoints (register, login, refresh, logout)
- `backend/app/routers/users.py` - User API endpoints (me, list, get)
- `backend/app/main.py` - Added auth and users router includes
- `backend/app/db/session.py` - Fixed schema_translate_map to use connection-level execution_options with SQLite detection
- `backend/app/middleware/tenant.py` - Added /api/v1/auth/refresh to PUBLIC_ROUTES
- `backend/tests/test_security.py` - 11 unit tests for JWT and password hashing
- `backend/tests/test_auth.py` - 9 integration tests for auth endpoints
- `backend/tests/test_rbac.py` - 12 tests (8 unit + 4 integration) for RBAC
- `backend/tests/conftest.py` - Fixed table creation for SQLite with schemaless metadata copies

## Decisions Made
- **jti claim for refresh tokens:** Added UUID-based jti to prevent identical JWTs when tokens are rotated within the same second
- **DB role is authoritative:** `require_role` checks the User's database role, not the JWT claim, ensuring role changes take immediate effect
- **SQLite schema fix:** Used `to_metadata(schema=None)` copies for DDL and connection-level `schema_translate_map` for DML, since SQLAlchemy's DDL compiler doesn't honor `schema_translate_map`
- **SHA-256 token storage:** Refresh tokens stored as SHA-256 hashes for defense-in-depth (even if DB is compromised, tokens can't be replayed)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed SQLite schema_translate_map incompatibility**
- **Found during:** Task 2 (integration tests failing with "no such table: main.users")
- **Issue:** SQLAlchemy's `async_sessionmaker.__call__` doesn't accept `execution_options` kwarg; DDL compiler ignores `schema_translate_map` for `create_all` on SQLite
- **Fix:** Changed session creation to use connection-level `execution_options`, added SQLite detection to use `schema_translate_map={"tenant": None, "shared": None}`, used `to_metadata(schema=None)` for test table creation
- **Files modified:** backend/app/db/session.py, backend/tests/conftest.py
- **Verification:** All 45 tests pass
- **Committed in:** 8b71849

**2. [Rule 1 - Bug] Added jti claim to prevent duplicate refresh tokens**
- **Found during:** Task 2 (test_refresh_token_success failing -- new and old tokens identical)
- **Issue:** Refresh tokens generated in same second with same payload produce identical JWTs
- **Fix:** Added `"jti": uuid.uuid4().hex` to refresh token payload for guaranteed uniqueness
- **Files modified:** backend/app/core/security.py
- **Verification:** test_refresh_token_success passes, new token differs from old
- **Committed in:** 8b71849

**3. [Rule 2 - Missing Critical] Added /api/v1/auth/refresh to PUBLIC_ROUTES**
- **Found during:** Task 2 (refresh endpoint requires tenant header but shouldn't need tenant resolution)
- **Issue:** Token refresh endpoint was blocked by TenantMiddleware requiring X-Tenant-Slug
- **Fix:** Added the refresh path to the PUBLIC_ROUTES set in tenant middleware
- **Files modified:** backend/app/middleware/tenant.py
- **Verification:** Refresh endpoint accessible without tenant header
- **Committed in:** 8b71849

---

**Total deviations:** 3 auto-fixed (2 bugs, 1 missing critical)
**Impact on plan:** All fixes necessary for correctness. No scope creep.

## Issues Encountered
None beyond the auto-fixed deviations.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Auth system complete: all protected endpoints can now use `get_current_active_user`, `require_role`, `require_permission`
- Plan 03 (encryption) can add field-level encryption to User.full_name using the established model patterns
- Plan 04 (audit/consent) can add audit logging middleware and consent checking using the auth dependencies
- Plan 05 (LLM/Docker) can protect LLM endpoints with the RBAC system

## Self-Check: PASSED

All 9 created files verified on disk. All 4 commit hashes (d3d4d38, d47590f, 1423293, 8b71849) confirmed in git log.

---
*Phase: 01-foundation-security*
*Completed: 2026-03-22*
