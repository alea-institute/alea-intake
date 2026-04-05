---
phase: 08
plan: 02
subsystem: frontend-application
tags: [themes, i18n, auth, routing, a11y]
requires: [08-01]
provides:
  - three-theme-css-variable-system
  - react-i18next-with-7-lsc-languages
  - auth-store-ram-only-bearer-token
  - apiFetch-wrapper-with-refresh-retry
  - react-router-with-6-lazy-routes
  - skip-to-content-a11y-link
  - use-reduced-motion-hook
affects: [frontend]
tech-stack:
  added: []
  patterns:
    - "data-theme-attribute + CSS custom properties"
    - "lazy namespace loading via HttpBackend"
    - "in-memory bearer token + httpOnly refresh cookie"
    - "React Router lazy route modules for code splitting"
key-files:
  created:
    - frontend/src/shared/components/ThemeProvider.tsx
    - frontend/src/shared/components/ThemeProvider.test.tsx
    - frontend/src/shared/components/SkipToContent.tsx
    - frontend/src/shared/hooks/useReducedMotion.ts
    - frontend/src/shared/i18n/config.ts
    - frontend/src/shared/i18n/config.test.ts
    - frontend/src/shared/i18n/themes.ts
    - frontend/src/features/auth/store.ts
    - frontend/src/features/auth/store.test.ts
    - frontend/src/features/auth/api.ts
    - frontend/src/features/auth/api.test.ts
    - frontend/src/features/auth/LoginPage.tsx
    - frontend/src/features/auth/OAuthFinishPage.tsx
    - frontend/src/features/chat/ChatPage.tsx
    - frontend/src/features/dashboard/DashboardPage.tsx
    - frontend/src/features/admin/AdminRouter.tsx
    - frontend/src/features/output/OutputPage.tsx
    - frontend/src/app/App.tsx
    - frontend/src/app/router.tsx
    - frontend/src/app/providers.tsx
    - frontend/src/vite-env.d.ts
    - frontend/public/locales/en/common.json
    - frontend/public/locales/en/chat.json
    - frontend/public/locales/en/admin.json
    - frontend/public/locales/en/safety.json
    - frontend/public/locales/en/output.json
    - frontend/public/locales/en/auth.json
    - frontend/public/locales/es/common.json
    - frontend/public/locales/zh/common.json
    - frontend/public/locales/vi/common.json
    - frontend/public/locales/ko/common.json
    - frontend/public/locales/tl/common.json
    - frontend/public/locales/ru/common.json
  modified:
    - frontend/src/styles/globals.css
    - frontend/tailwind.config.ts
    - frontend/src/main.tsx
  deleted:
    - frontend/src/App.tsx
decisions:
  - "ThemeProvider syncs on defaultTheme prop change (useEffect) so async org-data loading can update theme after mount"
  - "Refresh coalescing uses module-scoped refreshPromise to prevent thundering-herd on concurrent 401s"
  - "apiFetch uses window.location.href = '/login' for hard redirect on refresh failure (no router dependency)"
  - "jsdom origin http://localhost:3000 — MSW handlers use absolute URLs matching this origin"
  - "vite-env.d.ts declares *.css module + vite/client for import.meta.env typing"
metrics:
  duration: 8min
  completed: 2026-04-05
---

# Phase 8 Plan 2: Application Shell Summary

Built the Phase 8 application shell: three-theme CSS variable system with `data-theme` switching, react-i18next with 7 LSC languages and lazy namespace loading, in-memory access token auth store with `apiFetch` 401-refresh wrapper, React Router 7 with lazy-loaded feature routes for code splitting, and WCAG 2.4.1 skip-to-content link.

## One-Liner

Three-theme runtime switching via `data-theme` + CSS vars, react-i18next lazy namespaces across 7 LSC languages, RAM-only JWT auth with auto-refresh retry, React Router 7 lazy routes producing 6 separate bundle chunks.

## What Was Built

### Task 1: Three-theme CSS variable system

**`globals.css`** now declares four cascading theme blocks:

| Selector | Primary (HSL) | Display Font | Body Font |
|----------|---------------|--------------|-----------|
| `:root` (fallback) | `240 5.9% 10%` (zinc) | system-ui | system-ui |
| `[data-theme="legal-professional"]` | `213 52% 25%` (#1E3A5F navy) | Source Serif 4 | Inter |
| `[data-theme="modern-conversational"]` | `217 91% 60%` (#2563EB blue) | Inter | Inter |
| `[data-theme="courthouse-classic"]` | `217 19% 27%` (#1F2937 slate) | Libre Caslon Text | Libre Franklin |

Each theme also defines `--background`, `--foreground`, `--card`, `--popover`, `--secondary`, `--muted`, `--accent`, `--destructive`, `--border`, `--input`, `--ring` — all at WCAG 2.2 AA contrast (4.5:1) per UI-SPEC.

Dark-mode overlays on `[data-theme="X"].dark` lighten the primary accent to maintain contrast on dark surfaces.

**`tailwind.config.ts`** reads CSS vars via `hsl(var(--primary))` pattern + adds `fontFamily.display` / `fontFamily.body` tokens mapped to `var(--font-display)` / `var(--font-body)`.

**`ThemeProvider.tsx`** sets `data-theme` on `<html>` via `useEffect`, syncs on `defaultTheme` prop change (supports async org-data loading), and applies `orgAccent` hex overrides as inline CSS custom properties on the wrapper div (D-26). Includes `hexToHsl` helper converting `#RRGGBB` → `"H S% L%"` matching globals.css format.

### Task 2: react-i18next with 7 LSC languages + lazy namespaces

**`config.ts`** initializes i18n with:

- **7 languages (D-27):** en, es, zh, vi, ko, tl, ru
- **6 namespaces:** common, chat, admin, safety, output, auth
- **Startup load:** only `common` namespace — features trigger lazy loads via `useTranslation('chat')` etc.
- **HttpBackend:** fetches `/locales/{{lng}}/{{ns}}.json` from public/ static assets
- **LanguageDetector:** localStorage → navigator → htmlTag
- **useSuspense: true** for lazy loading (Pitfall 7: must have stub files per language to prevent 404→Suspense hang)

**`themes.ts`** lazy-loads @fontsource packages per theme — keeps fonts out of main bundle (Pitfall 6). Each theme only pulls the weights it needs.

**English source strings** exported from UI-SPEC Copywriting Contract across 6 files:
- `common.json`: 6 shared CTAs, 5 nav items, 11 error messages, 3 a11y labels
- `chat.json`: per-theme welcome + empty-dashboard copy, modality labels, streaming, progress, connection-lost banners
- `admin.json`: org settings, user management, protocols, KB, confirmations
- `safety.json`: critical-tier banner + drawer, elevated-tier badge, professional actions
- `output.json`: export generating, empty state, format labels
- `auth.json`: sign-in labels, SSO buttons, auth errors

**Spanish** has actual translations for `common.json` (primary non-English LSC language). **5 stub files** (zh/vi/ko/tl/ru) copy English content so Suspense resolves during load — translations to be supplied by downstream localization work.

### Task 3: Auth + router + providers

**`store.ts`** — Zustand auth store holds `accessToken` in RAM only (no persist middleware per D-22). Prevents XSS bearer-token exfiltration.

**`api.ts`** — `apiFetch` wrapper:

```
apiFetch(url) →
  attach Authorization: Bearer <accessToken>
  fetch with credentials: 'include'
  if 401 →
    refreshToken() via POST /api/v1/auth/refresh (cookie-bearing)
    if refresh ok → store new token, retry request
    if refresh fails → clear store, window.location.href = '/login', throw
```

Refresh coalescing via module-scoped `refreshPromise` prevents thundering-herd when multiple concurrent requests hit 401.

**`router.tsx`** — 7 routes, each feature route uses `lazy: async` pattern:

| Route | Component | Chunk (gzipped) |
|-------|-----------|-----------------|
| `/` | Navigate to `/dashboard` | (no chunk) |
| `/login` | LoginPage | 0.25 KB |
| `/oauth/finish` | OAuthFinishPage | 0.23 KB |
| `/chat/:sessionId` | ChatPage | 0.24 KB |
| `/dashboard` | DashboardPage | 0.25 KB |
| `/admin/*` | AdminRouter | 0.25 KB |
| `/intake/:id/output` | OutputPage | 0.25 KB |

Placeholder pages (simple Tailwind divs) to be replaced by plans 08-03 through 08-06.

**`App.tsx` (AppShell)** wraps `<Outlet/>` in `ThemeProvider` (defaults to `modern-conversational`) + `SkipToContent` + `<main id="main-content">`.

**`providers.tsx` (AppProviders)** wraps children in `QueryClientProvider` + `I18nextProvider` + top-level `Suspense` fallback.

**`main.tsx`** wires `AppProviders → RouterProvider(router)`.

**`SkipToContent.tsx`** — first focusable element on every page, visually hidden until keyboard focus, jumps to `<main id="main-content">` (D-20 item 6, WCAG 2.4.1).

**`useReducedMotion.ts`** hook — subscribes to `prefers-reduced-motion` media query changes, used by streaming/animations downstream (D-20 item 3).

## Auth Flow

```
User → Login form → POST /api/v1/auth/login { email, password }
                  ← 200 { access_token, user } + Set-Cookie: refresh=... (httpOnly)
                  → useAuth.setAuth(access_token, user)
                  → apiFetch('/api/v1/intakes') [token in RAM, attached as Bearer]
                  ← 401 (token expired)
                  → refreshToken() via POST /api/v1/auth/refresh [cookie-bearing]
                  ← 200 { access_token, user }
                  → useAuth.setAuth(new_access_token, user)
                  → retry original request with new token
                  ← 200 { ... }
```

## Bundle Check After Shell Build

- **Main chunk (index):** 180.91 KB raw, **57.34 KB gzipped** (budget 200 KB)
- **react-vendor:** 34.12 KB gzipped
- **i18n-vendor:** 21.97 KB gzipped
- **query-vendor:** 8.97 KB gzipped
- **6 lazy feature chunks:** 0.23-0.25 KB gzipped each

Bundle is well within budget with ~70% headroom remaining for feature code.

## Testing

- **21 tests passing** across 5 test files
- **ThemeProvider** (4 tests): data-theme attribute, all 3 themes, orgAccent override, error on use outside provider
- **i18n config** (5 tests): 7 languages, 6 namespaces, fallbackLng, startup namespaces, HttpBackend path
- **useAuth store** (4 tests): null initial state, setAuth, clear, never writes to localStorage
- **apiFetch** (4 tests): Authorization header attached, 401 refresh retry, refresh failure clears auth, login stores token

## Decisions Made

1. **ThemeProvider prop-sync via useEffect** — Downstream plans will fetch `user.theme` from `/api/v1/auth/me` async. ThemeProvider must re-apply when `defaultTheme` prop changes (not just initial mount).

2. **Refresh coalescing** — Single module-scoped `refreshPromise` prevents N parallel refresh requests when multiple API calls fire simultaneously and all hit 401.

3. **Hard redirect on refresh failure** — `window.location.href = '/login'` (not React Router navigate) because `apiFetch` lives outside the router tree and we want to clear all in-memory state.

4. **jsdom origin `http://localhost:3000`** — MSW handlers use absolute URLs matching this origin. Test code calls `apiFetch('/api/v1/ping')` (relative) and MSW intercepts correctly.

5. **Stub translations for 5 languages** — Copying English prevents 404→Suspense hang (Pitfall 7). Spanish has real translations as the primary non-English LSC language.

6. **vite-env.d.ts** — Required for `import.meta.env.DEV` typing + `.css` module imports in `themes.ts`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocker] Created `vite-env.d.ts` for TypeScript build**
- **Found during:** Task 3 build verification
- **Issue:** `import.meta.env.DEV` in i18n config.ts + `.css` imports in themes.ts failed TS2339/TS2307 in production build (`tsc -b`)
- **Fix:** Added `frontend/src/vite-env.d.ts` with `/// <reference types="vite/client" />` + `.css` module declaration
- **Files modified:** `frontend/src/vite-env.d.ts` (new)
- **Commit:** 9251ca9

**2. [Rule 3 - Blocker] Removed unused `@ts-expect-error` directives**
- **Found during:** Task 3 build verification
- **Issue:** `noUnusedLocals`/TS2578 flagged two `@ts-expect-error` directives before assignments that aren't actually type errors in jsdom test context
- **Fix:** Removed the unused directives
- **Files modified:** `frontend/src/features/auth/api.test.ts`
- **Commit:** 9251ca9

**3. [Rule 1 - Bug] Fixed ThemeProvider rerender test expectation**
- **Found during:** Task 1 GREEN test run
- **Issue:** Original implementation used `useState(defaultTheme)` — prop changes after mount didn't re-trigger `data-theme` attribute update. Test using `rerender()` with different `defaultTheme` failed.
- **Fix:** Added `useEffect(() => setTheme(defaultTheme), [defaultTheme])` so the provider syncs when async org data flows in. This is also the correct production behavior.
- **Files modified:** `frontend/src/shared/components/ThemeProvider.tsx`
- **Commit:** de0e813

**4. [Rule 3 - Blocker] Reworked window.location test override**
- **Found during:** Task 3 RED→GREEN
- **Issue:** jsdom's `window.location.href` is non-configurable; `Object.defineProperty` on `href` throws TypeError. Also `window.location.assign` is non-configurable (can't spyOn).
- **Fix:** Delete `window.location`, replace with a Proxy that intercepts `href` assignments. Restore original in `finally`.
- **Files modified:** `frontend/src/features/auth/api.test.ts`
- **Commit:** 9251ca9

## Self-Check: PASSED

All artifacts verified on disk:
- FOUND: frontend/src/shared/components/ThemeProvider.tsx
- FOUND: frontend/src/shared/components/ThemeProvider.test.tsx
- FOUND: frontend/src/shared/i18n/config.ts
- FOUND: frontend/src/shared/i18n/themes.ts
- FOUND: frontend/src/features/auth/store.ts
- FOUND: frontend/src/features/auth/api.ts
- FOUND: frontend/src/app/App.tsx
- FOUND: frontend/src/app/router.tsx
- FOUND: frontend/src/app/providers.tsx
- FOUND: frontend/src/shared/components/SkipToContent.tsx
- FOUND: frontend/src/shared/hooks/useReducedMotion.ts
- FOUND: frontend/public/locales/{en,es,zh,vi,ko,tl,ru}/common.json
- FOUND: frontend/public/locales/en/{chat,admin,safety,output,auth}.json

Commits verified:
- 3be02c3: test(08-02) RED for ThemeProvider
- de0e813: feat(08-02) three-theme CSS system
- 3617c8e: test(08-02) RED for i18n
- d4b55a4: feat(08-02) react-i18next config
- 1ead98a: test(08-02) RED for auth
- 9251ca9: feat(08-02) auth + router + providers

Tests: 21/21 passing. Build: succeeds with 6 lazy route chunks. Bundle: 57.34 KB gzipped (well under 200 KB budget).
