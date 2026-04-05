# Phase 08: Frontend Application - Research

**Researched:** 2026-04-03
**Domain:** React 19 SPA (Vite) + FastAPI SSO backend — chat, dashboards, admin, voice, i18n, WCAG 2.2 AA
**Confidence:** HIGH (library choices + versions verified against npm/pypi registries on research date)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions (36 total)

**Chat Interface Design:**
- **D-01:** Aesthetic tied to deployment profile. Three themes mapping to Phase 7 OutputProfile: law_firm → Legal-professional; legal_aid → Modern conversational; court_self_help → Courthouse classic. Org admin selects theme based on deployment type.
- **D-02:** Asymmetric message layout: consumer left with avatar/initial, system right with subtle badge. Modality icon per message. Timestamp on hover. Document-like subtle backgrounds, not traditional bubbles.
- **D-03:** Inline input bar with modality toggle. Single input bar with three modality buttons: text (default), mic (voice), paperclip (document). Active modality highlighted. Voice shows waveform. Document shows file preview + extraction status. Consistent across all three aesthetics.
- **D-04:** Character-by-character LLM streaming with cursor indicator. Message grows dynamically. Stop button during streaming.

**State Management & Data Flow:**
- **D-05:** Zustand + React Query. Zustand for local UI state; React Query for server state.
- **D-06:** WebSocket lifecycle via Zustand store with auto-reconnect (exponential backoff) + React Query cache invalidation. Inbound messages invalidate relevant caches. Connection state exposed as subscribable state. useWebSocket hook for scoped access.
- **D-07:** Optimistic UI for sent messages — show immediately with pending indicator, confirm on WebSocket ack. Failed sends show error state with retry.
- **D-08:** Persistent analysis progress panel (collapsible on mobile) showing current stage, iteration number, completeness score, next stage preview. Real-time from orchestrator broadcasts. Matches Phase 4 D-15.

**Dashboard & Navigation:**
- **D-09:** Hybrid table ↔ card view (user toggles). Dense table default for professionals. Sidebar filters. Quick-search by name/ID.
- **D-10:** Left sidebar + top bar, responsive collapse. Persistent sidebar. Top bar with org switcher, user menu, notifications. Sidebar collapses to icons on tablet, hamburger on mobile.

**Admin Interface Design:**
- **D-11:** Both setup wizard AND tabbed sections — org admin chooses at first-run.
- **D-12:** Both card view AND table view for protocol management.

**Voice Recording UX:**
- **D-13:** Tap-to-record with live waveform + transcript review.
- **D-14:** Inline edit with audio playback. Low-confidence words highlighted. Approve sends to pipeline; Re-record discards.

**Output Display & Export UX:**
- **D-15:** Profile-switcher tabs with markdown preview. TOC sidebar for long memos.
- **D-16:** One-click export with format menu (PDF/DOCX/JSON). Recently-exported formats cached.

**Mobile Responsiveness:**
- **D-17:** Bottom nav bar + full-screen views + collapsible progress panel. Touch targets min 44px. Voice recording full-screen modal.
- **D-18:** Tailwind default breakpoints: sm (640), md (768), lg (1024), xl (1280). Mobile-first CSS.

**Accessibility:**
- **D-19:** Target WCAG 2.2 AA across all flows.
- **D-20:** Full a11y suite: keyboard-reachable everything, screen reader announcements, prefers-reduced-motion, prefers-color-scheme dark mode, focus trap in modals, skip-to-content link, live regions.

**Authentication & Login Flow:**
- **D-21:** Email/password + SSO (user choice). Frontend offers both. SSO buttons for Google, Microsoft. **Backend SSO work included in this phase.**
- **D-22:** Access token in-memory only (XSS-safe). Refresh token in httpOnly secure cookie. Auto-refresh on 401. Draft messages preserved in localStorage.

**Error & Empty States:**
- **D-23:** Contextual errors with recovery actions.
- **D-24:** Illustrated empty states with primary actions.

**Theme System & Org Branding:**
- **D-25:** CSS custom properties with theme data attributes. `data-theme="professional|conversational|courthouse"` on root. Tailwind extends with CSS variables.
- **D-26:** Org branding overrides via inline CSS custom properties at runtime.

**i18n & Localization:**
- **D-27:** Full i18n via react-i18next. 7 LSC languages: English, Spanish, Chinese, Vietnamese, Korean, Tagalog/Filipino, Russian.
- **D-28:** LLM thinks in English, frontend translates. Parallel outputs for professional review.

**Critical Safety Alert UX:**
- **D-29:** Critical-tier alerts = persistent non-dismissible banner + safety resources drawer.
- **D-30:** Elevated-tier alerts = notification badge on chat header.

**Professional Oversight:**
- **D-31:** Both live observation mode AND after-the-fact review — org chooses.
- **D-32:** Multi-party intakes via party switcher + per-party threads.

**Onboarding:**
- **D-33:** All three consumer onboarding modes built — admin org chooses.
- **D-34:** Both admin onboarding modes built.

**Performance:**
- **D-35:** Mobile-first targets: LCP < 2.5s on 3G, initial JS bundle < 200KB gzipped, total page weight < 1MB, Lighthouse Performance > 90.
- **D-36:** Skeletons (not spinners). Route-based code splitting: chat, dashboard, admin, output. Message history paginated (50/page). Intake list with virtual scrolling for 100+ intakes.

### Claude's Discretion
- Specific React component structure and file organization
- Exact color palette values per theme (within aesthetic direction)
- Specific icon library choice (UI-SPEC specifies lucide-react — shadcn default)
- Specific illustration style for empty states (UI-SPEC already constrains to monochrome line SVGs in accent color)
- Exact Zustand store structure
- React Query cache key conventions
- Specific SSO provider implementations (Google OIDC, Microsoft Azure AD flows)

### Deferred Ideas (OUT OF SCOPE)
None — phase 9 handles fact-mapping visualizations (graph, matrix, narrative-anchored).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FRONTEND-01 | React frontend with conversational chat interface for intake | shadcn + custom ChatMessage, ChatInput, StreamingMessage components; WebSocket client with React Query cache integration |
| FRONTEND-02 | Real-time analysis progress via WebSocket/SSE streaming | useWebSocket hook + Zustand store + React Query setQueryData pattern; exponential backoff reconnect |
| FRONTEND-06 | Intake dashboard listing all intakes with status and progress | shadcn `dashboard-01` block + table/card toggle; @tanstack/react-virtual for 100+ rows |
| FRONTEND-07 | Output display with export capabilities | react-markdown + remark-gfm + rehype-raw (opt-in) for memo rendering; format menu wraps export endpoint from Phase 7 |
| FRONTEND-08 | Admin configuration interface for org settings, research tools, KB management, screening protocols | shadcn `tabs` + `form` + react-hook-form + zod resolver; wizard via `stepper` pattern |
| FRONTEND-09 | Mobile-responsive design | Tailwind mobile-first breakpoints; shadcn `sheet` for mobile nav; `sidebar-07` block collapse behavior |
| FRONTEND-10 | Voice recording UI component for voice input | @wavesurfer/react v1 + wavesurfer.js v7 Record plugin; MediaRecorder API via Record plugin abstraction |
</phase_requirements>

## Summary

Phase 08 is the first major frontend phase and also includes backend SSO work per D-21. The stack is already heavily constrained by CONTEXT.md (36 locked decisions) and the approved UI-SPEC (shadcn new-york + zinc, three themes via `data-theme`, @fontsource for self-hosted fonts, tailwindcss-animate, lucide-react icons, sonner toasts).

The research confirms that the ecosystem standard for every library the user asked about is stable and directly compatible with React 19 + Vite 6 + Tailwind 3.4 (the existing scaffold from Phase 01). **Critical version gotcha:** the default `npx shadcn@latest init` assumes Tailwind v4. Because this project uses Tailwind 3.4 (locked by Phase 01 for PostCSS compatibility), plans MUST use `npx shadcn@2.3.0 init` instead. This is a documented compatibility requirement.

For SSO, the recommended backend approach is **Authlib's FastAPI/Starlette OAuth client with server_metadata_url** for both Google (OpenID Connect discovery) and Microsoft Azure AD (per-tenant or `common` discovery endpoint). This unifies the two providers under a single abstraction and avoids building custom token-exchange code. MSAL-React is rejected for the frontend — it introduces a parallel token store that conflicts with the existing JWT infrastructure and D-22's in-memory + httpOnly-cookie pattern.

For voice, **wavesurfer.js v7.12+ with the Record plugin (via the @wavesurfer/react wrapper)** is the clear choice — it ships live microphone rendering out of the box and returns a standard Blob for upload. For virtualization, **@tanstack/react-virtual v3.13** is recommended over react-window — it's React 19-aware, more actively maintained, and handles variable-size rows which the intake dashboard needs. For markdown, **react-markdown v10 + remark-gfm + rehype-sanitize** is safe by default (no `dangerouslySetInnerHTML`) and critical for LLM-generated output.

For testing, the stack is **Vitest + @testing-library/react + jsdom for unit/component, Playwright for E2E, @axe-core/playwright for WCAG 2.2 AA automation, and MSW for API mocking**. This is the 2026 React/Vite standard.

**Primary recommendation:** Treat this phase as 4 parallel tracks — (1) foundation & shell (routing, shadcn init, theme system, i18n, auth state), (2) chat & WebSocket, (3) dashboards & admin, (4) backend SSO. Wave 0 MUST install shadcn at version 2.3.0 (Tailwind v3 compatibility) and scaffold the theme CSS variables before any feature work begins.

## Standard Stack

### Core (verified 2026-04-03)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| react | 19.2.4 | UI framework | Already installed (Phase 01) |
| react-dom | 19.2.4 | DOM renderer | Already installed |
| vite | 6.0.x | Build/dev server | Already installed; supports Tailwind 3 PostCSS pipeline |
| typescript | ~5.7 | Type safety | Already installed |
| tailwindcss | 3.4.18 | Styling | **Locked at v3 by Phase 01 (PostCSS compatibility)** — do NOT upgrade to v4 |
| autoprefixer | 10.4.x | PostCSS | Already installed |
| postcss | 8.5.x | CSS pipeline | Already installed |

### shadcn/ui + Design System

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| shadcn (CLI) | **2.3.0** | Component installer | **MUST pin to 2.3.0 for Tailwind v3** — later versions assume Tailwind v4 |
| class-variance-authority | 0.7.1 | Variant API | shadcn dependency |
| clsx | 2.1.1 | Class composition | shadcn `cn()` helper |
| tailwind-merge | 3.3.1 | Tailwind conflict resolution | shadcn `cn()` helper |
| tailwindcss-animate | 1.0.7 | Animation plugin | shadcn dependency (v3-era); later shadcn uses `tw-animate-css` instead |
| lucide-react | 0.545.x (latest) | Icon library | shadcn default (`icon: "lucide"` in components.json) |
| sonner | 2.0.7 | Toast notifications | shadcn `toast` replacement (Radix-based) |
| @radix-ui/* | per-component | Headless primitives | Installed transitively by shadcn components |

### State & Data

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| zustand | 5.0.12 | Local UI state | D-05 decision; tiny footprint (~1.2KB gzip); React 19 compatible |
| @tanstack/react-query | 5.96.2 | Server state | D-05 decision; stale-while-revalidate, optimistic updates, cache invalidation on WebSocket events |
| @tanstack/react-query-devtools | 5.96.x | Dev-only debugging | Conditional import — strip in prod build |

### Routing & Forms

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| react-router-dom | 7.14.0 | Client-side routing | v7 is the declared stable line in 2026; supports `lazy: () => import(...)` per-route code splitting natively |
| react-hook-form | 7.72.1 | Form state | shadcn `form` primitive integrates via `@hookform/resolvers` |
| @hookform/resolvers | 5.2.2 | Validation adapters | Bridges zod → react-hook-form |
| zod | 4.3.6 | Schema validation | 2026 standard; mature v4 line; shares schemas with backend if desired |

### WebSocket & Real-time

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| (native WebSocket) | — | Chat transport | Backend uses native WebSocket at `/api/ws/intake/{session_id}`; no library needed |
| — | — | Reconnect strategy | Custom hook + Zustand — keep control of backoff + auth (JWT in query param) |

**Note:** `react-use-websocket` is viable but adds dependency overhead for functionality that's ~40 lines of custom code. Recommend custom hook for tighter control over D-06's required connection-state enum (`connecting | connected | disconnected | reconnecting | error`) and exponential-backoff schedule (1s, 2s, 4s, 8s, 16s, 30s cap).

### Virtualization

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| @tanstack/react-virtual | 3.13.23 | Virtual scrolling | **Recommended over react-window** — React 19 aware, variable-size row support, most active maintenance in 2026 |

**Alternatives considered:**
- `react-window` 2.2.7 — simpler, smaller, but weaker variable-size handling. Choose only if the intake dashboard always uses fixed-height rows.
- `react-virtualized` — legacy, not recommended for greenfield.

### Markdown Rendering

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| react-markdown | 10.1.0 | Markdown → React elements | **Safe by default** — no `dangerouslySetInnerHTML`; converts to virtual DOM |
| remark-gfm | 4.0.1 | GitHub Flavored Markdown | Tables, task lists, strikethrough, autolinks — needed for Phase 7 memos |
| rehype-sanitize | 6.0.0 | HTML sanitization | Defense-in-depth if any `rehype-raw` usage creeps in |
| rehype-slug | 6.0.0 | Heading ID injection | Required for D-15 TOC sidebar |
| remark-breaks | 4.0.0 | Line-break preservation | Optional — match LLM output formatting |

**Rejected:** `marked` requires manual DOMPurify pass. Not worth the ergonomic regression when react-markdown handles LLM streams safely by construction.

### Voice Recording

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| wavesurfer.js | 7.12.5 | Waveform rendering engine | v7 Record plugin handles MediaRecorder + live microphone waveform natively |
| @wavesurfer/react | 1.0.19+ | React wrapper | Official React bindings; ref-based API |

**Alternatives considered:**
- `react-media-recorder` 1.7.x — simpler recorder but no live waveform; would need separate visualizer library. Adds integration surface.
- `react-voice-visualizer` — visualizer only, no recorder — still need MediaRecorder glue.
- Pure MediaRecorder API + custom AnalyserNode waveform — viable but re-invents wheel; UI-SPEC D-13 requires live waveform which is non-trivial to build well.

### i18n

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| i18next | 26.0.3 | Core i18n engine | Framework-agnostic; current major |
| react-i18next | 17.0.2 | React bindings + `useTranslation` hook | D-27 decision |
| i18next-http-backend | 3.0.4 | Lazy-load namespace JSON from server | Namespaces loaded only when route needs them — keeps initial bundle small |
| i18next-browser-languagedetector | 8.2.1 | Browser locale detection | Reads `navigator.language` / localStorage / cookie |
| i18next-resources-to-backend | 1.2.1 | Alternative: bundle-then-lazy-chunk | Use if you prefer webpack/Vite dynamic-import chunks over HTTP fetching |

**Recommendation:** Use `i18next-http-backend` with `loadPath: '/locales/{{lng}}/{{ns}}.json'` served as static assets. This keeps translations out of the initial bundle (the single biggest risk to D-35's <200KB target when shipping 7 languages).

### Testing

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| vitest | 3.3.3 | Unit/component test runner | 2-4x faster than Jest; native ESM; Vite-integrated |
| @vitest/browser | 4.1.2 | Browser-mode runner (optional) | For component tests that need real DOM |
| @testing-library/react | 16.3.2 | React component testing | Standard 2026 pairing with Vitest |
| @testing-library/jest-dom | (latest) | DOM matchers | Extends expect() for DOM assertions |
| @testing-library/user-event | (latest) | Realistic user interaction simulation | More accurate than fireEvent |
| jsdom | 29.0.1 | DOM simulation | vitest environment |
| @playwright/test | 1.59.1 | E2E testing | 2026 leader for E2E; parallel browsers; trace viewer |
| @axe-core/playwright | 4.11.1 | WCAG automation | **Required for D-19 WCAG 2.2 AA gate** |
| msw | 2.12.14 | API mocking (unit + E2E) | Service-worker-based mocking; shares handlers between Vitest + Playwright |

### Authentication (Frontend + Backend SSO)

**Frontend token handling:**

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| (none) | — | In-memory access token + fetch wrapper | Custom ~80-line auth slice (Zustand) matching D-22 |
| axios (optional) | 1.7.x | HTTP with interceptors | Use if automatic 401→refresh retry is cleaner than a fetch wrapper |

**Recommendation:** stick with `fetch` + a custom `apiClient` wrapper that reads the in-memory access token from the Zustand auth store and handles 401 refresh automatically. This matches D-22 precisely and avoids taking on an HTTP client dependency.

**Backend SSO (Python):**

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| authlib | 1.6.9 | OAuth 2.0 / OIDC client (Google, Microsoft) | Unified API for both providers via `server_metadata_url`; async Starlette integration works natively with FastAPI |
| itsdangerous | 2.2.x | Session cookie signing | Required by Starlette SessionMiddleware for OAuth state |

**Alternatives considered:**
- `python-social-auth` — Django-oriented, not actively maintained (last release 2017). **Reject.**
- `fastapi-users` 15.x — full auth framework including OAuth; rejected because project already has custom AuthService with refresh-token rotation (Phase 01). Migrating would be a rewrite, not an addition.
- `httpx-oauth` 0.16.x — lightweight OAuth client; viable alternative to Authlib but Authlib's `server_metadata_url` auto-discovery is a clean abstraction for the Google + Microsoft pair.
- Custom OAuth (as seen in some Medium tutorials) — rejected. Rolling your own token validation (JWKS fetch, signature verify, audience check) is exactly the kind of "don't hand-roll" security code this phase should avoid.
- `fastapi-azure-auth` — Microsoft-only; would require separate Google library. Authlib unifies.
- `msal` (Python) — Microsoft-only; same objection.

**Installation (frontend):**
```bash
# Core UI + Tailwind v3 shadcn
npx shadcn@2.3.0 init --style new-york --base-color zinc
npm install class-variance-authority clsx tailwind-merge lucide-react tailwindcss-animate sonner

# State & data
npm install zustand @tanstack/react-query
npm install -D @tanstack/react-query-devtools

# Routing & forms
npm install react-router-dom react-hook-form @hookform/resolvers zod

# Virtualization, markdown, voice
npm install @tanstack/react-virtual
npm install react-markdown remark-gfm rehype-sanitize rehype-slug
npm install wavesurfer.js @wavesurfer/react

# i18n
npm install i18next react-i18next i18next-http-backend i18next-browser-languagedetector

# Fonts (per UI-SPEC)
npm install @fontsource/inter @fontsource/source-serif-4 @fontsource/libre-caslon-text @fontsource/libre-franklin

# Testing
npm install -D vitest @testing-library/react @testing-library/jest-dom @testing-library/user-event jsdom
npm install -D @playwright/test @axe-core/playwright msw
npm install -D rollup-plugin-visualizer
```

**Installation (backend SSO additions):**
```bash
pip install "authlib>=1.6.9" "itsdangerous>=2.2.0"
```

### Version Verification
All versions above verified via `npm view <package> version` and `pip index versions <package>` on 2026-04-03. React ecosystem versions may tick up between research and plan-execution — planner should re-verify with `npm view` at plan-execute time and bump to latest compatible patch.

## Architecture Patterns

### Recommended Project Structure

```
frontend/src/
├── app/                          # App entry, providers, router
│   ├── router.tsx                # createBrowserRouter with lazy routes
│   ├── providers.tsx             # QueryClient, i18n, Theme, Auth providers
│   └── App.tsx
├── features/                     # Feature-first organization
│   ├── auth/
│   │   ├── components/           # LoginForm, SSOButtons
│   │   ├── hooks/                # useAuth, useAuthRefresh
│   │   ├── store.ts              # Zustand auth slice (in-memory access token)
│   │   └── api.ts                # fetch wrapper with 401 refresh
│   ├── chat/
│   │   ├── components/           # ChatMessage, ChatInput, StreamingMessage, VoiceRecorder, TranscriptReview
│   │   ├── hooks/                # useWebSocket, useIntakeSession
│   │   ├── store.ts              # WebSocket connection state
│   │   └── types.ts              # Message types
│   ├── dashboard/
│   │   ├── components/           # IntakeTable, IntakeCardGrid, FilterSidebar
│   │   ├── hooks/                # useIntakes
│   │   └── api.ts
│   ├── admin/
│   │   ├── components/           # SetupWizard, OrgProfile, ProtocolCards
│   │   ├── hooks/
│   │   └── api.ts
│   ├── output/
│   │   ├── components/           # ProfileTabs, MarkdownMemo, TOCSidebar, ExportMenu
│   │   └── api.ts
│   └── safety/
│       ├── components/           # SafetyBanner, SafetyDrawer, ResourceList
│       └── store.ts
├── shared/
│   ├── components/               # Custom primitives: EmptyState, MobileBottomNav, ThemeProvider, PartySwitcher
│   ├── hooks/                    # useMediaQuery, useLocalStorage, useReducedMotion
│   ├── api/                      # Shared fetch client, error types
│   └── i18n/                     # i18next config, types
├── components/ui/                # shadcn primitives (generated)
├── lib/
│   └── utils.ts                  # cn() helper
├── locales/                      # Static JSON per language (served via http-backend)
│   ├── en/{common,chat,admin,safety}.json
│   ├── es/...
│   └── (vi, ko, zh, tl, ru)/...
├── styles/
│   └── globals.css               # CSS vars for 3 themes + dark mode
├── assets/
│   └── illustrations/            # Empty-state SVGs per theme
├── main.tsx
└── vite-env.d.ts
```

### Pattern 1: Theme System (D-25, D-26) — CSS Custom Properties with `data-theme`

**What:** Three themes declared as CSS variable blocks selected by `data-theme` on `<html>`; org accent override via inline style.

**When to use:** All themed surfaces.

**Example:**
```css
/* src/styles/globals.css */
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    /* shadcn zinc defaults (used when no data-theme set - fallback) */
    --background: 0 0% 100%;
    --foreground: 240 10% 3.9%;
    /* ... other shadcn defaults ... */
    --radius: 0.5rem;
  }

  [data-theme="legal-professional"] {
    --background: 40 33% 97%;       /* #FAF8F3 */
    --foreground: 222 47% 11%;
    --card: 0 0% 100%;
    --card-foreground: 222 47% 11%;
    --primary: 213 52% 25%;          /* #1E3A5F navy */
    --primary-foreground: 0 0% 100%;
    --destructive: 0 71% 42%;        /* #B91C1C */
    --destructive-foreground: 0 0% 100%;
    --ring: 213 52% 25%;
    --font-display: "Source Serif 4", Georgia, serif;
    --font-body: "Inter", system-ui, sans-serif;
  }

  [data-theme="modern-conversational"] {
    --background: 210 20% 98%;      /* #F9FAFB */
    --foreground: 222 47% 11%;
    --primary: 217 91% 60%;          /* #2563EB */
    --primary-foreground: 0 0% 100%;
    --destructive: 0 72% 51%;        /* #DC2626 */
    --ring: 217 91% 60%;
    --font-display: "Inter", system-ui, sans-serif;
    --font-body: "Inter", system-ui, sans-serif;
  }

  [data-theme="courthouse-classic"] {
    --background: 60 20% 98%;       /* #FBFBF8 */
    --foreground: 222 47% 11%;
    --primary: 217 19% 27%;          /* #1F2937 slate */
    --primary-foreground: 0 0% 100%;
    --destructive: 0 70% 35%;        /* #991B1B */
    --ring: 217 19% 27%;
    --font-display: "Libre Caslon Text", Georgia, serif;
    --font-body: "Libre Franklin", system-ui, sans-serif;
  }

  /* Dark-mode overlays per theme (prefers-color-scheme: dark) */
  [data-theme="legal-professional"].dark { /* inverted vars */ }
  /* ... */
}
```

```tsx
// src/shared/components/ThemeProvider.tsx
export function ThemeProvider({ theme, orgAccent, logoUrl, children }: Props) {
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  const orgOverride = orgAccent
    ? { '--primary': orgAccent } as React.CSSProperties
    : undefined;

  return (
    <div style={orgOverride}>
      {children}
    </div>
  );
}
```

```ts
// tailwind.config.ts — extend colors to read CSS variables
export default {
  darkMode: ["class"],
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))',
        },
        /* ... all shadcn token pairs ... */
      },
      fontFamily: {
        display: 'var(--font-display)',
        body: 'var(--font-body)',
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
    },
  },
  plugins: [require('tailwindcss-animate')],
};
```

### Pattern 2: WebSocket Hook + React Query Cache Sync (D-05, D-06, D-07)

**What:** Single WebSocket per intake session, connection state in Zustand, inbound messages mutate React Query cache.

**When to use:** Chat transport + any real-time server event.

**Example:**
```ts
// features/chat/store.ts
interface WSState {
  status: 'connecting' | 'connected' | 'disconnected' | 'reconnecting' | 'error';
  ws: WebSocket | null;
  reconnectAttempt: number;
}
export const useWSStore = create<WSState>(...);
```

```ts
// features/chat/hooks/useWebSocket.ts
const BACKOFF_MS = [1000, 2000, 4000, 8000, 16000, 30000];

export function useWebSocket(sessionId: string, token: string) {
  const queryClient = useQueryClient();
  const { setStatus, setWs } = useWSStore();

  useEffect(() => {
    let ws: WebSocket | null = null;
    let reconnectTimer: number | null = null;
    let attempt = 0;
    let disposed = false;

    const connect = () => {
      if (disposed) return;
      setStatus(attempt === 0 ? 'connecting' : 'reconnecting');
      ws = new WebSocket(`/api/ws/intake/${sessionId}?token=${token}`);

      ws.onopen = () => {
        attempt = 0;
        setStatus('connected');
        setWs(ws);
      };

      ws.onmessage = (e) => {
        const msg = JSON.parse(e.data);
        switch (msg.type) {
          case 'message_ack':
            queryClient.setQueryData(
              ['intake', sessionId, 'messages'],
              (old: Message[] = []) => old.map(m =>
                m.clientId === msg.client_id ? { ...m, status: 'sent', id: msg.id } : m
              )
            );
            break;
          case 'llm_stream':
            queryClient.setQueryData(
              ['intake', sessionId, 'messages'],
              (old: Message[] = []) => appendToken(old, msg.message_id, msg.token)
            );
            break;
          case 'analysis_progress':
            queryClient.setQueryData(['intake', sessionId, 'progress'], msg.data);
            break;
          case 'safety_alert':
            queryClient.invalidateQueries({ queryKey: ['intake', sessionId, 'safety'] });
            break;
        }
      };

      ws.onclose = (e) => {
        setStatus('disconnected');
        setWs(null);
        if (e.code === 4001 || e.code === 4003) {
          // Auth failure — don't reconnect, trigger refresh
          return;
        }
        const delay = BACKOFF_MS[Math.min(attempt, BACKOFF_MS.length - 1)];
        reconnectTimer = window.setTimeout(connect, delay + Math.random() * 300);
        attempt += 1;
      };

      ws.onerror = () => setStatus('error');
    };

    connect();
    return () => {
      disposed = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      ws?.close();
    };
  }, [sessionId, token, queryClient, setStatus, setWs]);
}
```

### Pattern 3: Auth — In-Memory Access Token + httpOnly Refresh Cookie (D-22)

**What:** Access token in Zustand (RAM only), refresh via cookie-bearing POST.

**Example:**
```ts
// features/auth/store.ts
interface AuthState {
  accessToken: string | null;
  user: User | null;
  setAuth: (tok: string, user: User) => void;
  clear: () => void;
}
export const useAuth = create<AuthState>(set => ({
  accessToken: null,
  user: null,
  setAuth: (accessToken, user) => set({ accessToken, user }),
  clear: () => set({ accessToken: null, user: null }),
}));

// features/auth/api.ts - fetch wrapper
export async function apiFetch(input: RequestInfo, init: RequestInit = {}) {
  const token = useAuth.getState().accessToken;
  const headers = new Headers(init.headers);
  if (token) headers.set('Authorization', `Bearer ${token}`);

  let res = await fetch(input, { ...init, headers, credentials: 'include' });

  if (res.status === 401) {
    const refreshRes = await fetch('/api/v1/auth/refresh', {
      method: 'POST',
      credentials: 'include',  // httpOnly cookie sent automatically
    });
    if (!refreshRes.ok) {
      useAuth.getState().clear();
      window.location.href = '/login';
      throw new Error('Session expired');
    }
    const { access_token, user } = await refreshRes.json();
    useAuth.getState().setAuth(access_token, user);
    headers.set('Authorization', `Bearer ${access_token}`);
    res = await fetch(input, { ...init, headers, credentials: 'include' });
  }
  return res;
}
```

**Backend (Phase 08 SSO additions):**
```python
# backend/app/core/oauth.py
from authlib.integrations.starlette_client import OAuth
from app.config import get_settings

settings = get_settings()
oauth = OAuth()

oauth.register(
    name='google',
    client_id=settings.google_client_id,
    client_secret=settings.google_client_secret,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'},
)

oauth.register(
    name='microsoft',
    client_id=settings.microsoft_client_id,
    client_secret=settings.microsoft_client_secret,
    server_metadata_url='https://login.microsoftonline.com/common/v2.0/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile User.Read'},
)

# backend/app/routers/oauth.py
@router.get("/login/{provider}")
async def oauth_login(provider: str, request: Request):
    client = oauth.create_client(provider)
    redirect_uri = request.url_for('oauth_callback', provider=provider)
    return await client.authorize_redirect(request, str(redirect_uri))

@router.get("/callback/{provider}", name='oauth_callback')
async def oauth_callback(provider: str, request: Request, session: AsyncSession = Depends(...)):
    client = oauth.create_client(provider)
    token = await client.authorize_access_token(request)
    userinfo = token.get('userinfo') or await client.parse_id_token(request, token)

    # Link or create user by email; mint access + refresh JWT using existing AuthService
    user = await auth_service.upsert_sso_user(
        email=userinfo['email'],
        provider=provider,
        provider_id=userinfo['sub'],
        full_name=userinfo.get('name'),
        org_id=request.state.org_id,
    )
    access, refresh = await auth_service.mint_tokens_for_user(user)

    response = RedirectResponse(url=f'/login/callback#access_token={access}')
    response.set_cookie('refresh_token', refresh, httponly=True, secure=True,
                        samesite='lax', max_age=604800, path='/api/v1/auth/refresh')
    return response
```

### Pattern 4: Route-Based Code Splitting (D-35, D-36)

```ts
// app/router.tsx
import { createBrowserRouter } from 'react-router-dom';

export const router = createBrowserRouter([
  {
    path: '/',
    Component: AppShell,
    children: [
      { path: 'login', lazy: () => import('@/features/auth/LoginPage').then(m => ({ Component: m.LoginPage })) },
      { path: 'chat/:sessionId', lazy: () => import('@/features/chat/ChatPage').then(m => ({ Component: m.ChatPage })) },
      { path: 'dashboard', lazy: () => import('@/features/dashboard/DashboardPage').then(m => ({ Component: m.DashboardPage })) },
      { path: 'admin/*', lazy: () => import('@/features/admin/AdminRouter').then(m => ({ Component: m.AdminRouter })) },
      { path: 'intake/:id/output', lazy: () => import('@/features/output/OutputPage').then(m => ({ Component: m.OutputPage })) },
    ],
  },
]);
```

```ts
// vite.config.ts additions
import { visualizer } from 'rollup-plugin-visualizer';

export default defineConfig({
  plugins: [
    react(),
    visualizer({ filename: 'dist/stats.html', gzipSize: true }),
  ],
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
          'query-vendor': ['@tanstack/react-query', 'zustand'],
          'ui-vendor': ['@radix-ui/react-dialog', '@radix-ui/react-dropdown-menu' /* ...heavy Radix modules */],
          'markdown-vendor': ['react-markdown', 'remark-gfm', 'rehype-sanitize'],
          'wavesurfer-vendor': ['wavesurfer.js', '@wavesurfer/react'],
          'i18n-vendor': ['i18next', 'react-i18next', 'i18next-http-backend'],
        },
      },
    },
    chunkSizeWarningLimit: 200,
  },
});
```

### Pattern 5: i18n Lazy Namespace Loading

```ts
// shared/i18n/config.ts
import i18n from 'i18next';
import HttpBackend from 'i18next-http-backend';
import LanguageDetector from 'i18next-browser-languagedetector';
import { initReactI18next } from 'react-i18next';

i18n
  .use(HttpBackend)
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    fallbackLng: 'en',
    supportedLngs: ['en', 'es', 'zh', 'vi', 'ko', 'tl', 'ru'],
    ns: ['common'],  // load only 'common' on startup
    defaultNS: 'common',
    backend: {
      loadPath: '/locales/{{lng}}/{{ns}}.json',
    },
    react: { useSuspense: true },
    interpolation: { escapeValue: false },
  });

// In feature components:
const { t } = useTranslation(['chat', 'common']);  // lazy-loads 'chat' namespace on mount
```

### Anti-Patterns to Avoid

- **Storing the access token in `localStorage` or a non-httpOnly cookie** — violates D-22 and exposes token to any XSS payload. Access token MUST be Zustand state only.
- **Rendering LLM output with `dangerouslySetInnerHTML` (e.g., via marked + innerHTML)** — even "sanitized" HTML paths introduce XSS surface. Use react-markdown (virtual-DOM path) exclusively.
- **Global i18n namespace** — bundling all 7 languages' all-namespaces JSON into the initial chunk will blow D-35's 200KB budget. Lazy-load via backend.
- **`useEffect` to imperatively set the token then run queries** — creates auth race conditions. Read the token synchronously inside the fetch wrapper.
- **WebSocket reconnect without jitter** — synchronized retries after an outage create thundering-herd on the backend. Always add 0-300ms random jitter.
- **Using MSAL-React for Microsoft SSO** — conflicts with existing JWT + refresh-cookie scheme. Use backend Authlib flow that mints the same JWTs as email/password login.
- **Frontend rolling its own OAuth PKCE flow** — given backend custody of refresh tokens and tenant isolation, backend-driven OAuth is cleaner and keeps provider secrets off the client.
- **Loading all shadcn components eagerly** — shadcn generates components into your source tree; only `import` what each route needs. Trust the router's lazy boundaries.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Markdown → HTML | Custom parser or string-replace | `react-markdown` + `remark-gfm` | GFM tables, task lists, HTML escaping, heading IDs — hundreds of edge cases |
| Live microphone waveform | Canvas + AnalyserNode + RAF loop | `wavesurfer.js` Record plugin | Timing, scroll mode, device enumeration, browser codec quirks |
| WebSocket reconnect | `setTimeout` with fixed delay | Exponential backoff with jitter (pattern 2) | Thundering herd, network-outage recovery |
| Virtual list (100+ intakes) | `overflow:auto` + render-all | `@tanstack/react-virtual` | Variable row heights, scroll restoration, keyboard navigation |
| OAuth flow (Google + Microsoft) | Custom `authorize` URL builders + JWKS fetch + signature verify | `authlib` with `server_metadata_url` | State/nonce management, JWKS rotation, provider quirks (Azure tid claim, etc.) |
| Focus trap in modals | Custom keyboard handlers | shadcn `Dialog` / `AlertDialog` / `Sheet` (Radix primitives) | Screen reader announcements, ESC handling, restoring focus on close |
| Form validation | ad-hoc setState for every field | `react-hook-form` + `zod` | Schema reuse, async validation, error locale messages |
| Accessible color contrast | eyeballing palette | Verify with contrast tool + `@axe-core/playwright` | WCAG 2.2 AA requires 4.5:1 (normal text) measured at runtime |
| i18n plural/gender | template literals + if/else | react-i18next ICU format | Slavic plurals (Russian has 4 forms), Tagalog plurality rules |

**Key insight:** The frontend ecosystem in 2026 has solved the problems above with battle-tested libraries. Every hand-rolled replacement becomes a forever-bug backlog. The phase's complexity should come from *the user-facing features* (chat UX, multi-party threads, safety alerts), not from re-implementing infrastructure.

## Runtime State Inventory

Not applicable — Phase 08 is greenfield frontend + additive backend SSO endpoints. No renames, no data migrations, no existing frontend production code to preserve state from.

## Common Pitfalls

### Pitfall 1: shadcn CLI Version Mismatch with Tailwind v3
**What goes wrong:** Running `npx shadcn@latest init` in this project generates Tailwind v4 `@theme inline` syntax in globals.css, which Tailwind 3.4's PostCSS pipeline doesn't parse. Components install but pages render unstyled.
**Why it happens:** shadcn 3.x / 4.x defaults to Tailwind v4. Project is pinned to Tailwind 3.x per Phase 01 (PostCSS compatibility).
**How to avoid:** Pin the CLI: `npx shadcn@2.3.0 init --style new-york --base-color zinc`. All `add` commands also use `shadcn@2.3.0 add <component>`.
**Warning signs:** `@theme inline { ... }` appears in generated CSS; components render without color; `hsl(var(--background))` resolves to nothing.

### Pitfall 2: React Query Rendering Stale Data After WebSocket Event
**What goes wrong:** Server pushes a new message via WebSocket; UI doesn't update even though cache was updated with `setQueryData`.
**Why it happens:** `setQueryData` mutation must return a *new* reference. Mutating `old.push(newMessage)` and returning `old` keeps the same reference and React Query doesn't re-notify subscribers.
**How to avoid:** Always return a new array/object: `setQueryData(key, (old) => [...(old ?? []), newMessage])`.
**Warning signs:** Messages arrive in network tab but don't appear in UI until something else triggers a re-render.

### Pitfall 3: MediaRecorder MIME Type Browser Inconsistency
**What goes wrong:** Recording produces an unplayable file on one browser (e.g., `audio/webm;codecs=opus` on Chrome vs. `audio/mp4` on Safari).
**Why it happens:** Browsers support different default MIME types; backend ASR may reject unexpected formats.
**How to avoid:** Check `MediaRecorder.isTypeSupported()` and prefer `audio/webm;codecs=opus` (broadly supported). Always send the actual MIME type from the Blob in the upload Content-Type. Phase 3's ASR layer already handles multiple formats per its backend design, but verify with legal_aid/court_self_help browsers (iOS Safari is most divergent).
**Warning signs:** Server-side ASR 415 Unsupported Media Type errors; playback works in one browser but not another.

### Pitfall 4: JWT Access Token Exposure via URL Fragment After OAuth Redirect
**What goes wrong:** Backend returns OAuth callback by redirecting to `/login/callback#access_token=...`, leaving the token in browser history and referer headers.
**Why it happens:** Quick way to hand the token back to the SPA after OAuth flow.
**How to avoid:** Redirect to a dedicated `/oauth/finish` page; on mount it calls a backend endpoint that returns the access token in JSON (reading a short-lived one-time code from the fragment or a server session). Alternatively, set both refresh and a short-lived access cookie, then have the SPA call `/api/v1/auth/me` to hydrate state. **Preferred:** return access token in JSON via a fetch POST to backend `/oauth/exchange` using a single-use server-side state.
**Warning signs:** Access token visible in browser history; token in window.location.hash persists after app mounts.

### Pitfall 5: React 19 + TanStack Virtual `useFlushSync` Warnings
**What goes wrong:** Console warnings during rapid scroll: "flushSync was called from inside a lifecycle method".
**Why it happens:** React 19's batching is more aggressive; TanStack Virtual's default sync updates conflict.
**How to avoid:** Pass `useFlushSync: false` to the `useVirtualizer` options for React 19 projects. This allows React to batch updates naturally.
**Warning signs:** Console warnings during scroll; lag perceptible on low-end devices.

### Pitfall 6: Bundle Size Blow-Up from Eager @fontsource Imports
**What goes wrong:** All 6 font-weight files from 4 @fontsource packages get bundled into the initial chunk, adding 100-300KB and breaking D-35's 200KB budget.
**Why it happens:** Importing `@fontsource/inter` without a style file pulls all weights; importing all themes at once loads fonts for themes the user's org doesn't use.
**How to avoid:** (1) Import only the specific weights used (`@fontsource/inter/400.css`, `@fontsource/inter/600.css`). (2) Lazy-import theme-specific fonts after org is known — each theme's fonts load only when that theme is active. (3) Use `font-display: swap` in the @fontsource CSS to avoid render blocking.
**Warning signs:** Initial JS > 200KB gzipped; Lighthouse flags "render-blocking resources: woff2".

### Pitfall 7: react-i18next Suspense + Error Boundary Interaction
**What goes wrong:** Missing translation key causes the whole app to stay suspended forever; user sees blank screen.
**Why it happens:** `useSuspense: true` waits for namespaces; if an HTTP 404 happens on a namespace fetch, Suspense never resolves.
**How to avoid:** Set `backend.requestOptions = { cache: 'no-store' }` in dev; wrap each feature route in an `ErrorBoundary` with a "Translation failed" fallback. Ensure all 7 language directories exist under `public/locales/` even if some are English-only stubs initially.
**Warning signs:** Blank app screen; console shows failed fetch for `/locales/ru/chat.json`.

### Pitfall 8: WCAG Focus Ring Invisible on Dark Mode
**What goes wrong:** `--ring` variable set to a mid-luminance color works on light mode but disappears on dark surfaces.
**Why it happens:** UI-SPEC verified contrast only on white text. Dark mode inverts surfaces.
**How to avoid:** Define separate `--ring` values in each `[data-theme].dark` block; verify with `@axe-core/playwright withTags(['wcag2aa', 'wcag22aa'])`.
**Warning signs:** axe-core reports "focusable-element: focus indicator not visible" on dark-mode screenshots.

## Code Examples

### WebSocket Hook — See Pattern 2 above (full example)

### Authlib OAuth Registration (backend)
```python
# backend/app/core/oauth.py — verified from Authlib official demo
from authlib.integrations.starlette_client import OAuth
oauth = OAuth()
oauth.register(
    name='google',
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile', 'prompt': 'select_account'},
)
# Source: https://github.com/authlib/demo-oauth-client/blob/master/starlette-google-login/app.py
```

### shadcn cn() Helper (Tailwind v3)
```ts
// src/lib/utils.ts
import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
```

### Wavesurfer React Record Plugin
```tsx
// features/chat/components/VoiceRecorder.tsx
import { useWavesurfer } from '@wavesurfer/react';
import RecordPlugin from 'wavesurfer.js/dist/plugins/record.esm.js';
import { useRef, useState, useEffect } from 'react';

export function VoiceRecorder({ onRecorded }: { onRecorded: (blob: Blob, mime: string) => void }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [recording, setRecording] = useState(false);
  const [elapsedMs, setElapsedMs] = useState(0);

  const { wavesurfer } = useWavesurfer({
    container: containerRef,
    waveColor: 'hsl(var(--primary))',
    progressColor: 'hsl(var(--primary) / 0.5)',
    height: 64,
  });

  useEffect(() => {
    if (!wavesurfer) return;
    const record = wavesurfer.registerPlugin(RecordPlugin.create({
      scrollingWaveform: true,
      renderRecordedAudio: true,
    }));
    record.on('record-progress', (time) => setElapsedMs(time));
    record.on('record-end', (blob) => {
      setRecording(false);
      onRecorded(blob, blob.type);
    });
    return () => record.destroy();
  }, [wavesurfer, onRecorded]);

  const toggleRecord = async () => {
    const record = wavesurfer?.getActivePlugins()[0] as any;
    if (recording) {
      record.stopRecording();
    } else {
      const mime = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus' : 'audio/webm';
      await record.startRecording({ mimeType: mime });
      setRecording(true);
    }
  };

  return (
    <div>
      <div ref={containerRef} aria-label="Voice recording waveform" />
      <button onClick={toggleRecord} aria-label={recording ? 'Stop recording' : 'Start recording'}>
        {recording ? '■' : '●'} {formatTime(elapsedMs)}
      </button>
    </div>
  );
}
```

### Markdown Rendering for LLM Output
```tsx
// features/output/components/MarkdownMemo.tsx
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeSanitize from 'rehype-sanitize';
import rehypeSlug from 'rehype-slug';

export function MarkdownMemo({ content }: { content: string }) {
  return (
    <article className="prose prose-zinc dark:prose-invert max-w-none">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeSanitize, rehypeSlug]}
        components={{
          h1: ({ children, id }) => <h1 id={id} className="font-display text-[28px]">{children}</h1>,
          h2: ({ children, id }) => <h2 id={id} className="font-display text-[20px]">{children}</h2>,
          a: ({ href, children }) => (
            <a href={href} className="text-primary underline" target="_blank" rel="noreferrer">
              {children}
            </a>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </article>
  );
}
```

### TanStack Virtual for Intake List
```tsx
// features/dashboard/components/IntakeVirtualList.tsx
import { useVirtualizer } from '@tanstack/react-virtual';
import { useRef } from 'react';

export function IntakeVirtualList({ intakes }: { intakes: Intake[] }) {
  const parentRef = useRef<HTMLDivElement>(null);
  const rowVirtualizer = useVirtualizer({
    count: intakes.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 72,
    overscan: 8,
    useFlushSync: false,  // React 19
  });

  return (
    <div ref={parentRef} className="h-[600px] overflow-auto" role="list" aria-label="Intakes">
      <div style={{ height: rowVirtualizer.getTotalSize(), position: 'relative' }}>
        {rowVirtualizer.getVirtualItems().map(v => (
          <div
            key={v.key}
            role="listitem"
            style={{ position: 'absolute', top: 0, left: 0, transform: `translateY(${v.start}px)`, width: '100%' }}
          >
            <IntakeRow intake={intakes[v.index]} />
          </div>
        ))}
      </div>
    </div>
  );
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| CRA (Create React App) | Vite | ~2023 | 10x dev-server speed; CRA deprecated 2023 |
| Redux Toolkit for everything | Zustand (UI) + React Query (server) | ~2022 | Smaller bundles, less boilerplate, clearer separation |
| Jest | Vitest | ~2023 | Native ESM, 2-4x faster, better Vite integration |
| Cypress for E2E | Playwright | ~2024 | Parallel browsers, better tracing, faster |
| styled-components/emotion | Tailwind + CSS vars | ~2022 | Runtime-zero styling, theme via CSS vars |
| Enzyme | Testing Library | ~2020 | User-centric queries, a11y tree as source of truth |
| HSL for shadcn themes (pre-2026) | OKLch | shadcn 2.4+ (2026) | Better perceptual uniformity for dark mode |
| react-query v4 | @tanstack/react-query v5 | 2023 | Renamed exports, simpler signatures |
| react-router v6 data API | react-router v7 | 2025 | Unified with Remix, native `lazy` route property |

**Deprecated / outdated:**
- **`i18next-xhr-backend`** — replaced by `i18next-http-backend`. Do not install.
- **`react-virtualized`** — superseded by `@tanstack/react-virtual`.
- **`react-i18next` `withTranslation` HOC** — use `useTranslation` hook.
- **`react-markdown` `escapeHtml`** — replaced by `rehype-sanitize`.
- **shadcn CLI 1.x** — v2.3.0 is minimum for stability on Tailwind v3 projects; 3.x+ defaults to Tailwind v4.

## Open Questions

1. **OAuth callback mechanism for access-token hand-off**
   - What we know: D-22 requires access token in memory, refresh in httpOnly cookie. OAuth flow ends on backend redirect.
   - What's unclear: Should backend use (a) URL fragment with single-use nonce, (b) short-lived cookie swap, or (c) POST-redirect to SPA that exchanges a one-time code?
   - Recommendation: Option (c) — backend redirects to `/oauth/finish?state=<one-time-code>`; SPA mounts → POSTs code to `/api/v1/auth/oauth/exchange` → receives `{access_token, user}` in JSON; refresh cookie already set on redirect response. Keeps access token out of browser history entirely.

2. **Per-theme font bundling strategy**
   - What we know: 3 themes × 2-4 font families × ~2 weights = 6-12 woff2 files totaling ~200KB.
   - What's unclear: Do we preload all theme fonts or lazy-load by active theme? Does org switch at runtime? (CONTEXT says theme is org-scoped, locked after login — so no runtime switching.)
   - Recommendation: Lazy-load the active theme's fonts only. Create 3 theme-font entry files (`themes/legal-professional.fonts.ts`); dynamic-import after auth resolves and org's theme is known. Ship English variant only of each font file (most @fontsource packages already split by language subset).

3. **WebSocket session resumption**
   - What we know: Phase 03 established WebSocket at `/api/ws/intake/{session_id}` with close codes 4001/4003. Backend supports reconnect.
   - What's unclear: Does backend replay missed messages on reconnect, or does frontend need to GET /messages since X timestamp?
   - Recommendation: Planner to coordinate with Phase 03 implementation — check existing intake.py router. If no replay, frontend should refetch `['intake', sessionId, 'messages']` on `connected` event to catch up.

4. **Exact shadcn block versions (sidebar-07, login-01, dashboard-01)**
   - What we know: UI-SPEC references shadcn blocks for layout shells.
   - What's unclear: Are these blocks available in the `shadcn@2.3.0` CLI version, or only in 3.x+?
   - Recommendation: Planner should verify block availability via `npx shadcn@2.3.0 view sidebar-07` at plan-check time. If blocks require 3.x, fall back to hand-assembling from primitives — the 2.3.0 primitive set is sufficient.

5. **Dark mode per theme — explicit palettes or invert-only?**
   - What we know: D-20 item 4 requires `prefers-color-scheme` dark mode support; D-25 declares 3 themes.
   - What's unclear: Does each theme get a hand-tuned dark palette, or is it a rule-based inversion?
   - Recommendation: Hand-tune per theme. Rule-based inversion breaks WCAG contrast for accent colors — e.g., navy (#1E3A5F) on dark-zinc background has insufficient contrast; dark-mode navy should shift to lighter luminance (~#4A7DC4) to hit 4.5:1 on dark surfaces.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js ≥ 20 | Vite 6, Vitest 3, Playwright 1.59 | presumed (Phase 01 ran Vite 6) | ≥ 20 | n/a |
| npm/pnpm | package install | presumed | — | — |
| Chromium | Playwright E2E, headless screenshots | presumed (Phase 01 uses snap chromium per user global CLAUDE.md) | — | manual test |
| WebKit + Firefox | Playwright cross-browser | likely missing | — | `npx playwright install` in Wave 0 |
| FastAPI backend running | manual E2E, SSO testing | requires `uvicorn` | — | dev-only mode with mocked backend via MSW |
| Google OAuth credentials | SSO smoke test | depends on env | — | dev stub provider for tests |
| Microsoft Azure app registration | SSO smoke test | depends on env | — | dev stub provider for tests |
| Python 3.11+ | authlib, FastAPI | presumed (Phase 01) | — | — |

**Missing dependencies with no fallback:**
- Google/Microsoft OAuth credentials for live SSO flow — required for manual smoke test but NOT for unit tests (mock with MSW) or plan-execute phase. Planner should add a "configure OAuth app registrations" task with clear owner (user).

**Missing dependencies with fallback:**
- WebKit/Firefox browsers for Playwright — install in Wave 0.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Vitest 3.3.x + @testing-library/react 16.3.x (unit/component); Playwright 1.59.x (E2E) |
| Config file | `frontend/vitest.config.ts`, `frontend/playwright.config.ts` — see Wave 0 |
| Quick run command | `cd frontend && npm run test -- --run <file>` (per-file) |
| Full suite command | `cd frontend && npm run test:all` (alias: `npm run test && npm run test:e2e`) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FRONTEND-01 | Chat UI renders messages, input modality toggle works | component | `npx vitest run src/features/chat/components/ChatInput.test.tsx` | ❌ Wave 0 |
| FRONTEND-01 | Chat WebSocket auto-reconnects with exponential backoff | unit | `npx vitest run src/features/chat/hooks/useWebSocket.test.ts` | ❌ Wave 0 |
| FRONTEND-01 | LLM streaming renders char-by-char with cursor | component | `npx vitest run src/features/chat/components/StreamingMessage.test.tsx` | ❌ Wave 0 |
| FRONTEND-01 | Optimistic message send + ack + retry flow | component | `npx vitest run src/features/chat/components/ChatPage.test.tsx` | ❌ Wave 0 |
| FRONTEND-02 | Analysis progress panel updates from WebSocket | component | `npx vitest run src/features/chat/components/AnalysisProgressPanel.test.tsx` | ❌ Wave 0 |
| FRONTEND-02 | React Query cache updates on `analysis_progress` event | unit | `npx vitest run src/features/chat/hooks/useWebSocket.test.ts` | ❌ Wave 0 |
| FRONTEND-06 | Dashboard table renders, filters apply, toggles to cards | component | `npx vitest run src/features/dashboard/components/IntakeTable.test.tsx` | ❌ Wave 0 |
| FRONTEND-06 | Virtual list renders 200 intakes without layout thrash | component | `npx vitest run src/features/dashboard/components/IntakeVirtualList.test.tsx` | ❌ Wave 0 |
| FRONTEND-07 | Markdown memo renders with GFM + slug IDs | component | `npx vitest run src/features/output/components/MarkdownMemo.test.tsx` | ❌ Wave 0 |
| FRONTEND-07 | Export menu opens format options, triggers download | component | `npx vitest run src/features/output/components/ExportMenu.test.tsx` | ❌ Wave 0 |
| FRONTEND-08 | Admin tabs switch, form validates with zod schema | component | `npx vitest run src/features/admin/components/OrgProfile.test.tsx` | ❌ Wave 0 |
| FRONTEND-08 | Setup wizard advances through 6 steps | component | `npx vitest run src/features/admin/components/SetupWizard.test.tsx` | ❌ Wave 0 |
| FRONTEND-09 | Mobile bottom nav renders < 768px, sidebar hidden | component | `npx vitest run src/shared/components/MobileBottomNav.test.tsx` | ❌ Wave 0 |
| FRONTEND-09 | Layout reflows at sm/md breakpoints without horizontal scroll | e2e | `npx playwright test tests/e2e/responsive.spec.ts` | ❌ Wave 0 |
| FRONTEND-10 | VoiceRecorder starts/stops, emits Blob with correct MIME | component | `npx vitest run src/features/chat/components/VoiceRecorder.test.tsx` | ❌ Wave 0 |
| FRONTEND-10 | Transcript review allows inline edit + re-record | component | `npx vitest run src/features/chat/components/TranscriptReview.test.tsx` | ❌ Wave 0 |
| D-19 WCAG 2.2 AA | No axe-core violations on all primary routes | e2e | `npx playwright test tests/e2e/a11y.spec.ts` | ❌ Wave 0 |
| D-21 SSO | Google OAuth redirect returns access token + sets refresh cookie | integration (backend) | `pytest backend/tests/integration/test_oauth.py::test_google_flow` | ❌ Wave 0 |
| D-21 SSO | Microsoft OAuth redirect returns access token + sets refresh cookie | integration (backend) | `pytest backend/tests/integration/test_oauth.py::test_microsoft_flow` | ❌ Wave 0 |
| D-22 | Access token never written to localStorage/sessionStorage | e2e | `npx playwright test tests/e2e/auth-storage.spec.ts` | ❌ Wave 0 |
| D-22 | 401 response triggers silent refresh + retry | unit | `npx vitest run src/features/auth/api.test.ts` | ❌ Wave 0 |
| D-25 | `data-theme` attribute applies correct CSS vars | component | `npx vitest run src/shared/components/ThemeProvider.test.tsx` | ❌ Wave 0 |
| D-27 | `useTranslation('chat')` lazy-loads chat namespace | integration | `npx vitest run src/shared/i18n/config.test.ts` | ❌ Wave 0 |
| D-29 | Critical safety banner non-dismissible | component | `npx vitest run src/features/safety/components/SafetyBanner.test.tsx` | ❌ Wave 0 |
| D-35 | Initial JS bundle < 200KB gzipped | build-check | `cd frontend && npm run build && node scripts/check-bundle-size.mjs` | ❌ Wave 0 |
| D-35 | Lighthouse Performance > 90 mobile | e2e | `npx playwright test tests/e2e/lighthouse.spec.ts` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `npm run test -- --run <changed-file>` (Vitest single-file)
- **Per wave merge:** `npm run test` (Vitest full suite, no E2E)
- **Phase gate:** `npm run test:all` — Vitest + Playwright + axe + bundle-size check all green before `/gsd:verify-work`

### Wave 0 Gaps

Wave 0 must create the entire test infrastructure since Phase 08 is the first frontend phase:

- [ ] `frontend/vitest.config.ts` — Vitest + jsdom + testing-library setup
- [ ] `frontend/vitest.setup.ts` — jest-dom matchers, MSW server start, cleanup
- [ ] `frontend/playwright.config.ts` — chromium/firefox/webkit projects, trace on retry
- [ ] `frontend/tests/e2e/` directory with baseline config
- [ ] `frontend/src/test/utils.tsx` — custom render with Router + QueryClient + i18n providers
- [ ] `frontend/src/test/msw/handlers.ts` — shared API mock handlers for unit + e2e
- [ ] `frontend/src/test/msw/server.ts` — Node MSW server for Vitest
- [ ] `frontend/src/test/msw/browser.ts` — browser MSW worker for Playwright
- [ ] `frontend/scripts/check-bundle-size.mjs` — fails if main chunk > 200KB gzipped
- [ ] `frontend/.storybook/` (optional) — component documentation harness
- [ ] Framework install: `npm install -D vitest @vitest/ui @testing-library/react @testing-library/jest-dom @testing-library/user-event jsdom @playwright/test @axe-core/playwright msw rollup-plugin-visualizer`
- [ ] Playwright browsers: `npx playwright install chromium webkit firefox`
- [ ] Backend integration test scaffold: `backend/tests/integration/test_oauth.py` with authlib test harness (mock discovery endpoints, stub token exchange)

## Project Constraints (from CLAUDE.md)

No project-level `./CLAUDE.md` exists in repo root (only user-global). User-global CLAUDE.md directives that apply to this phase:

- **Use deterministic port hashing for dev servers** — `port = 8700 + (hash('alea-intake') % 1300)`. Existing Vite config uses 5173 — plans should override to the hashed port.
- **Write dev screenshots to `$HOME/`** (snap Chromium sandbox), not `/tmp/`. Clean up after reading.
- **Run tests automatically after code changes** — don't ask first. Fix lint/test failures before reporting back (up to 2-3 attempts).
- **Front-end design principles** (from user-global) — distinctive typography (no Arial/system-fallback fonts alone), cohesive color via CSS vars, purposeful motion, spatial composition. UI-SPEC already encodes these via @fontsource and the three-theme palettes.
- **Browser testing via MCP chrome-devtools** — Playwright is the automated test runner, but manual visual verification during development uses MCP chrome-devtools `navigate_page` → `wait_for` → `take_screenshot`.

## Sources

### Primary (HIGH confidence)

- **shadcn/ui Theming:** https://ui.shadcn.com/docs/theming — CSS variable approach, token conventions, dark mode structure
- **shadcn/ui Vite Install (v4):** https://ui.shadcn.com/docs/installation/vite — Tailwind v4 path; confirms `shadcn@2.3.0` required for Tailwind v3
- **shadcn@2.3.0 Vite Install (v3):** https://github.com/shadcn-ui/ui/blob/shadcn%402.3.0/apps/www/content/docs/installation/vite.mdx — Tailwind v3 config, postcss, utils.ts
- **Authlib Starlette Google Demo:** https://github.com/authlib/demo-oauth-client/blob/master/starlette-google-login/app.py — canonical FastAPI/Starlette OAuth pattern
- **Authlib FastAPI Docs:** https://docs.authlib.org/en/latest/client/fastapi.html — FastAPI integration guidance
- **remarkjs/react-markdown:** https://github.com/remarkjs/react-markdown — safe-by-default rendering, plugin composition
- **TanStack Query Docs — Query Invalidation:** https://tanstack.com/query/v5/docs/framework/react/guides/query-invalidation
- **TanStack Virtual:** https://tanstack.com/virtual/latest — virtualization library
- **Playwright Accessibility Testing:** https://playwright.dev/docs/accessibility-testing — @axe-core/playwright WCAG tags
- **React Router v7 Automatic Code Splitting:** https://reactrouter.com/explanation/code-splitting
- **Vite Code Splitting + manualChunks:** https://v3.vitejs.dev/guide/build — Rollup manualChunks reference
- **MDN MediaRecorder API:** https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder
- **npm registry version checks (2026-04-03):** react 19.2.4, tailwindcss 3.4.18, @tanstack/react-query 5.96.2, @tanstack/react-virtual 3.13.23, zustand 5.0.12, react-i18next 17.0.2, react-markdown 10.1.0, wavesurfer.js 7.12.5, vitest 3.3.3, @playwright/test 1.59.1, shadcn 2.3.0
- **PyPI version checks:** authlib 1.6.9, httpx-oauth 0.16.1

### Secondary (MEDIUM confidence)

- **LogRocket — TanStack Query WebSockets:** https://blog.logrocket.com/tanstack-query-websockets-real-time-react-data-fetching/
- **Strapi — React Markdown Security Guide:** https://strapi.io/blog/react-markdown-complete-guide-security-styling
- **HackerOne — Secure Markdown Rendering in React:** https://www.hackerone.com/blog/secure-markdown-rendering-react-balancing-flexibility-and-safety
- **dev.to — WebSocket Reconnection with Exponential Backoff:** https://dev.to/hexshift/robust-websocket-reconnection-strategies-in-javascript-with-exponential-backoff-40n1
- **WebSocket.org — Reconnection Guide:** https://websocket.org/guides/reconnection/
- **Borstch — TanStack Virtual vs react-window:** https://borstch.com/blog/development/comparing-tanstack-virtual-with-react-window-which-one-should-you-choose
- **Akoskm — Vitest Browser Mode + Playwright:** https://akoskm.com/react-component-testing-with-vitests-browser-mode-and-playwright/
- **Medium — Authlib Azure AD + FastAPI:** https://medium.com/@sankalpmohate/oauth-2-0-and-openid-connect-with-azure-ad-login-using-fastapi-a3792b067ba6
- **Remix Blog — Faster Lazy Loading in React Router v7.5+:** https://remix.run/blog/faster-lazy-loading
- **Medium — Lazy Loading i18next:** https://pranavpandey1998official.medium.com/lazy-loading-localization-with-react-i18next-3ebb5383fabe

### Tertiary (LOW confidence — flagged for plan-check verification)

- **Various 2026 comparative blog posts** on Vitest vs Jest, Playwright vs Cypress — used for ecosystem-standard confirmation only; specific claims (e.g., "2-4x faster") not independently benchmarked
- **WaveSurfer Record plugin v7 API** — documented via example description; planner should verify against live demo at https://wavesurfer.xyz/examples/?record.js before coding VoiceRecorder component

## Metadata

**Confidence breakdown:**
- Standard Stack: **HIGH** — all versions verified against npm/pypi on research date; libraries are ecosystem-dominant for each use case
- Architecture Patterns: **HIGH** — patterns sourced from official docs and active 2026 community usage
- Pitfalls: **MEDIUM-HIGH** — shadcn@2.3.0 gotcha verified via shadcn's own docs; MediaRecorder MIME and React 19 useFlushSync pitfalls documented in library issues; others inferred from CONTEXT.md constraints plus known React-ecosystem gotchas
- Authlib SSO backend pattern: **HIGH** — canonical code pulled directly from Authlib's own demo repository
- Performance budget strategies: **MEDIUM** — manualChunks pattern is standard but hitting <200KB with i18n + 3 themes + shadcn is aggressive and will require iterative tuning during implementation

**Research date:** 2026-04-03
**Valid until:** 2026-05-03 (30 days — React/Vite/shadcn ecosystem is stable but Tailwind v3 → v4 migration pressure will grow; re-verify shadcn@2.3.0 availability if plan delays beyond 30 days)
