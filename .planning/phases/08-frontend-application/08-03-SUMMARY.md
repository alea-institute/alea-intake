---
phase: 08-frontend-application
plan: 03
subsystem: auth
tags: [oauth, sso, authlib, google, microsoft, oidc, jwt, react, i18n]

# Dependency graph
requires:
  - phase: 08-01
    provides: shadcn component system, Vite build, Tailwind config
  - phase: 08-02
    provides: ThemeProvider, auth store (useAuth/Zustand), apiFetch, i18n config, router with /login and /oauth/finish routes
  - phase: 01-foundation-security
    provides: User model, AuthService, JWT token creation (create_access_token, create_refresh_token), RefreshToken model
provides:
  - Authlib OAuth client registry (Google + Microsoft OIDC)
  - SSOService with user upsert/link and one-time nonce exchange
  - OAuth router with /login/{provider}, /callback/{provider}, /exchange endpoints
  - LoginPage with email/password form + SSO buttons (D-21)
  - OAuthFinishPage with nonce-to-token exchange
  - SSOButtons component
affects: [08-04, 08-05, 08-06]

# Tech tracking
tech-stack:
  added: [authlib 1.6.9, itsdangerous 2.2.0, starlette SessionMiddleware]
  patterns: [one-time nonce exchange pattern (Pitfall 4), SSO user upsert by provider+subject then email]

key-files:
  created:
    - backend/app/core/oauth.py
    - backend/app/services/sso_service.py
    - backend/app/routers/oauth.py
    - backend/tests/unit/test_sso_service.py
    - backend/tests/integration/test_oauth.py
    - frontend/src/features/auth/LoginPage.test.tsx
    - frontend/src/features/auth/components/SSOButtons.tsx
    - backend/alembic/versions/001_add_sso_fields.py
  modified:
    - backend/pyproject.toml
    - backend/app/config.py
    - backend/app/models/user.py
    - backend/app/main.py
    - backend/app/middleware/tenant.py
    - frontend/src/features/auth/LoginPage.tsx
    - frontend/src/features/auth/OAuthFinishPage.tsx
    - frontend/public/locales/en/auth.json
    - frontend/src/test/msw/handlers.ts

key-decisions:
  - "Inline token minting in OAuth callback using create_access_token/create_refresh_token directly (AuthService lacks mint_tokens_for_user method)"
  - "In-memory nonce store for MVP; production should use Redis for multi-worker safety"
  - "OAuth routes exempted from TenantMiddleware via path prefix match (not PUBLIC_ROUTES set)"
  - "Alembic migration gitignored per project convention; SSO columns on User model auto-created in test metadata"

patterns-established:
  - "Pitfall 4 safe OAuth: nonce in URL, token exchanged via POST JSON, never in browser history"
  - "SSO user lookup order: (provider, subject) -> email -> create new"
  - "SessionMiddleware for OAuth state CSRF in Authlib Starlette integration"

requirements-completed: [FRONTEND-01]

# Metrics
duration: 8min
completed: 2026-04-06
---

# Phase 8 Plan 03: OAuth SSO + Login Page Summary

**Google + Microsoft OAuth via Authlib with one-time nonce exchange pattern (Pitfall 4 safe), LoginPage with email/password + SSO buttons per D-21**

## Performance

- **Duration:** 8 min
- **Started:** 2026-04-06T02:48:37Z
- **Completed:** 2026-04-06T02:56:45Z
- **Tasks:** 2
- **Files modified:** 17

## Accomplishments
- Authlib OAuth client registry with Google + Microsoft OIDC providers via server_metadata_url auto-discovery
- SSOService with 3-tier user upsert (provider+subject match, email link, create new) and 60s TTL one-time nonce exchange
- Full OAuth router: /login/{provider} redirect, /callback/{provider} token exchange + user upsert + nonce redirect, /exchange JSON token delivery
- LoginPage with email/password form, "Continue with Google" and "Continue with Microsoft" SSO buttons, i18n copy per UI-SPEC
- OAuthFinishPage that exchanges nonce for access_token + user via POST, hydrates Zustand auth store, navigates to /dashboard
- 14 backend tests pass (8 unit + 6 integration), 3 frontend tests pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Install Authlib + configure OAuth providers + SSO service** - `542de9f` (feat)
2. **Task 2: OAuth router endpoints + integration tests + frontend LoginPage + OAuthFinishPage** - `eced44e` (feat)

## Files Created/Modified
- `backend/app/core/oauth.py` - Authlib OAuth client registry (Google + Microsoft)
- `backend/app/services/sso_service.py` - User upsert/link logic + nonce exchange
- `backend/app/routers/oauth.py` - OAuth endpoints: login redirect, callback, exchange
- `backend/app/config.py` - 7 new OAuth settings fields
- `backend/app/models/user.py` - sso_provider + sso_subject columns
- `backend/app/main.py` - SessionMiddleware + OAuth router registration
- `backend/app/middleware/tenant.py` - OAuth route exemption
- `backend/tests/unit/test_sso_service.py` - 8 unit tests for nonce + upsert
- `backend/tests/integration/test_oauth.py` - 6 integration tests for OAuth flow
- `frontend/src/features/auth/LoginPage.tsx` - Full login form with SSO
- `frontend/src/features/auth/OAuthFinishPage.tsx` - Nonce exchange + auth hydration
- `frontend/src/features/auth/components/SSOButtons.tsx` - Google + Microsoft buttons
- `frontend/src/features/auth/LoginPage.test.tsx` - 3 tests for LoginPage
- `frontend/public/locales/en/auth.json` - Added finishing, ssoFailed, ssoMissingCode keys
- `frontend/src/test/msw/handlers.ts` - Added login + exchange mock handlers

## Decisions Made
- **Inline token minting:** AuthService lacks a `mint_tokens_for_user` method; used `create_access_token` and `create_refresh_token` directly in the OAuth callback (same approach as AuthService.login internally)
- **In-memory nonce store:** Sufficient for single-worker MVP; production should swap to Redis for multi-process safety
- **OAuth route exemption via path prefix:** Added `/api/v1/auth/oauth/` prefix check in TenantMiddleware dispatch (broader than individual routes in PUBLIC_ROUTES set) since all OAuth routes are public
- **Alembic migration file:** Created but gitignored per project convention; SSO columns on User model are created automatically from SQLAlchemy metadata in tests

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] AuthService.mint_tokens_for_user does not exist**
- **Found during:** Task 2 (OAuth router implementation)
- **Issue:** Plan references `AuthService.mint_tokens_for_user(user)` and `auth_service.get_user_by_id(user_id)` which are not methods on the existing AuthService
- **Fix:** Used `create_access_token` and `create_refresh_token` directly (same primitives AuthService uses internally); used direct SQLAlchemy query for user lookup
- **Files modified:** backend/app/routers/oauth.py
- **Verification:** All integration tests pass with correct token generation
- **Committed in:** eced44e

**2. [Rule 3 - Blocking] OAuth routes blocked by TenantMiddleware**
- **Found during:** Task 2 (integration test execution)
- **Issue:** OAuth routes require no tenant context (pre-authentication), but TenantMiddleware returns 400 for non-public routes
- **Fix:** Added `/api/v1/auth/oauth/` prefix exemption in TenantMiddleware dispatch
- **Files modified:** backend/app/middleware/tenant.py
- **Verification:** All OAuth integration tests pass without X-Tenant-Slug header
- **Committed in:** eced44e

**3. [Rule 3 - Blocking] python-docx/pymupdf/pytesseract removed during uv sync**
- **Found during:** Task 2 (integration test execution)
- **Issue:** `uv sync` removed packages not listed in pyproject.toml (were installed manually), causing ImportError in docx_adapter
- **Fix:** Reinstalled via `uv pip install` (not added to pyproject.toml -- these are separate from this plan's scope)
- **Files modified:** none (runtime fix)
- **Verification:** Integration tests run without import errors
- **Committed in:** not committed (runtime environment fix)

---

**Total deviations:** 3 auto-fixed (3 blocking)
**Impact on plan:** All auto-fixes necessary for correct execution. No scope creep.

## Issues Encountered
None beyond the deviations noted above.

## User Setup Required

**External services require manual configuration.** Google and Microsoft OAuth require app registrations:

**Google OAuth:**
1. Google Cloud Console -> APIs & Services -> Credentials -> Create OAuth 2.0 Client ID (Web application)
2. Add authorized redirect URI: `http://localhost:8000/api/v1/auth/oauth/callback/google`
3. Set `ALEA_GOOGLE_CLIENT_ID` and `ALEA_GOOGLE_CLIENT_SECRET` in `.env`

**Microsoft OAuth:**
1. Azure Portal -> App registrations -> New registration
2. Add redirect URI: `http://localhost:8000/api/v1/auth/oauth/callback/microsoft` (type: Web)
3. Add API permissions: Microsoft Graph -> User.Read, openid, email, profile
4. Create client secret under Certificates & secrets
5. Set `ALEA_MICROSOFT_CLIENT_ID` and `ALEA_MICROSOFT_CLIENT_SECRET` in `.env`

**Also set:** `ALEA_SESSION_SECRET_KEY` to a random string for production (dev uses fallback).

## Known Stubs
None -- all components are fully wired to backend endpoints and auth store.

## Next Phase Readiness
- OAuth SSO foundation complete; Google + Microsoft flows ready for end-to-end testing when credentials are configured
- LoginPage and OAuthFinishPage ready for Plan 08-04 (chat interface) to build on authenticated session
- Auth store hydration works identically for email/password and SSO flows

## Self-Check: PASSED

All 10 key files verified present. Both task commits (542de9f, eced44e) found in git log.

---
*Phase: 08-frontend-application*
*Completed: 2026-04-06*
