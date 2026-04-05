# Phase 8: Frontend Application - Context

**Gathered:** 2026-04-05
**Status:** Ready for UI-phase / planning

<domain>
## Phase Boundary

React frontend application with conversational chat UI (three aesthetic themes tied to deployment profile), WebSocket-driven real-time analysis progress, intake dashboard, admin configuration, voice recording, output display with export, SSO authentication, i18n (7 languages), WCAG 2.2 AA accessibility, and mobile-responsive layouts. This is the first major frontend phase — the UI that consumers and professionals will actually use.

</domain>

<decisions>
## Implementation Decisions

### Chat Interface Design
- **D-01:** Aesthetic tied to deployment profile. Three themes mapping to Phase 7 OutputProfile: law_firm → Legal-professional (serif headers, restrained palette, navy + warm neutrals + single accent); legal_aid → Modern conversational (rounded, friendly, system sans-serif); court_self_help → Courthouse classic (editorial serif, strong typographic hierarchy). Org admin selects theme based on deployment type.
- **D-02:** Asymmetric message layout: consumer left with avatar/initial, system right with subtle badge. Modality icon per message (text/voice/doc). Timestamp on hover. Document-like subtle backgrounds, not traditional bubbles.
- **D-03:** Inline input bar with modality toggle. Single input bar with three modality buttons: text (default), mic (voice), paperclip (document). Active modality highlighted. Voice shows waveform. Document shows file preview + extraction status. Consistent across all three aesthetics.
- **D-04:** Character-by-character LLM streaming with cursor indicator. Message grows dynamically. Stop button during streaming.

### State Management & Data Flow
- **D-05:** Zustand + React Query. Zustand for local UI state (current intake, WebSocket connection, UI prefs). React Query for server state (intakes, messages, analysis results) with automatic caching/refetching/optimistic updates.
- **D-06:** WebSocket lifecycle via Zustand store with auto-reconnect (exponential backoff) + React Query cache invalidation. Inbound messages invalidate relevant caches. Connection state (connecting/connected/disconnected/error) exposed as subscribable state. useWebSocket hook for scoped access.
- **D-07:** Optimistic UI for sent messages — show immediately with pending indicator, confirm on WebSocket ack. Failed sends show error state with retry.
- **D-08:** Persistent analysis progress panel (collapsible on mobile) showing current stage, iteration number, completeness score, next stage preview. Updates in real-time from orchestrator broadcasts. Matches Phase 4 D-15.

### Dashboard & Navigation
- **D-09:** Hybrid table ↔ card view (user toggles). Table (dense, default for professionals): matter ID, consumer name, area of law, jurisdiction, status, last activity, completeness %. Card view: more visual for lower-volume use cases. Sidebar filters: status, area, jurisdiction, date range, assigned professional. Quick-search by name/ID.
- **D-10:** Left sidebar + top bar, responsive collapse. Persistent sidebar (Dashboard, New Intake, Admin if permitted). Top bar (org switcher, user menu, notifications). Sidebar collapses to icons on tablet, hamburger on mobile.

### Admin Interface Design
- **D-11:** Both setup wizard AND tabbed sections — org admin chooses at first-run and can revisit. Wizard: org profile → deployment type → screening protocols → output profiles → research tools → KB. Tabbed: Organization, Research Tools, Knowledge Base, Screening Protocols, Output Profiles, Users, Usage & Budgets.
- **D-12:** Both card view AND table view for protocol management (user toggles). Cards: name, severity tier (color-coded), description, trigger count, activation toggle, edit. Table: dense listing. Filter by tier, "Create Custom Protocol" button.

### Voice Recording UX
- **D-13:** Tap-to-record with live waveform + transcript review. Tap mic → live waveform + timer → tap to stop → transcript appears in review panel.
- **D-14:** Inline edit with audio playback. Transcript in editable text area with audio player. Low-confidence words highlighted (from ASR confidence). Approve sends to pipeline; Re-record discards.

### Output Display & Export UX
- **D-15:** Profile-switcher tabs with markdown preview. Output page has tabs for each generated profile (e.g., "Law Firm Memo", "Consumer Summary"). Selected tab renders markdown as styled HTML with legal formatting. TOC sidebar for long memos.
- **D-16:** One-click export with format menu (PDF/DOCX/JSON). Export button opens format menu. Click → server generates → browser download. Loading indicator during generation. Recently-exported formats cached for quick re-download.

### Mobile Responsiveness
- **D-17:** Bottom nav bar + full-screen views + collapsible progress panel. Mobile (<768px): bottom nav with 3-4 icons (Chat, Dashboard, Admin, Profile). Full-screen chat/dashboard/admin. Progress panel collapses to top banner with tap-to-expand. Touch targets min 44px. Voice recording gets full-screen modal.
- **D-18:** Tailwind default breakpoints: sm (640), md (768), lg (1024), xl (1280). Mobile-first CSS.

### Accessibility
- **D-19:** Target WCAG 2.2 AA across all flows. Critical for consumer-facing (legal aid, court self-help) audiences.
- **D-20:** Full a11y suite: (1) keyboard-reachable everything with logical tab order, (2) screen reader announcements for chat/progress/errors, (3) prefers-reduced-motion disables streaming animations, (4) prefers-color-scheme dark mode support, (5) focus trap in modals, (6) skip-to-content link, (7) live regions for WebSocket updates.

### Authentication & Login Flow
- **D-21:** Email/password + SSO (user choice). Frontend offers both login methods. SSO buttons for Google, Microsoft. **Backend SSO work included in this phase** — OAuth endpoints, provider integrations, token exchange.
- **D-22:** Access token in-memory only (XSS-safe). Refresh token in httpOnly secure cookie. Auto-refresh on 401. Silent refresh preserves user flow; redirect to login only on refresh failure. Draft messages preserved in localStorage to avoid data loss.

### Error & Empty States
- **D-23:** Contextual errors with recovery actions. Every error shows: what happened (plain language), why it matters, what user can do (retry, contact admin). Network errors inline. WebSocket disconnects show reconnecting banner. Form errors inline per field. Global error boundary catches crashes.
- **D-24:** Illustrated empty states with primary actions. Empty dashboard: "No intakes yet" with illustration + action. Empty KB: guided upload. Empty states as onboarding opportunities. Soft illustrations matching active aesthetic.

### Theme System & Org Branding
- **D-25:** CSS custom properties with theme data attributes. Three themes as CSS custom property sets (--color-primary, --font-display, etc.). Applied via `data-theme="professional|conversational|courthouse"` on root. Tailwind extends with CSS variables. Instant theme switching.
- **D-26:** Org branding overrides via inline CSS custom properties. Org uploads logo + sets accent color in admin. These override theme defaults at runtime. Logo in top bar + exports. Accent overrides --color-accent. Theme base stays intact.

### i18n & Localization
- **D-27:** Full i18n infrastructure via react-i18next. Ship with 7 LSC-recommended languages: English, Spanish, Chinese (Mandarin and Cantonese, grouped as Chinese), Vietnamese, Korean, Tagalog/Filipino, Russian. Namespaced JSON translation files. Language selector in user menu + browser detection.
- **D-28:** LLM thinks in English, frontend translates. Backend LLM outputs stay in English (best reasoning). Frontend translates UI chrome AND LLM-generated content to user's selected language. Parallel outputs: consumers see translated version, legal professionals can review English original alongside.

### Critical Safety Alert UX
- **D-29:** Critical-tier alerts (DV, self-harm, child abuse) = persistent non-dismissible banner + safety resources drawer. Banner at top of chat. Click opens drawer with: "Are you safe right now?" question, hotlines (National DV, 988 Crisis, Childhelp, etc.), local resources if location known, safety planning link. Professional view adds "escalate to supervisor" action.
- **D-30:** Elevated-tier alerts (stalking, sexual assault, substance, mental health, immigration detention) = notification badge on chat header. Click to see list with resources. Non-interrupting, surfaces at natural pauses. Professional view adds "mark as addressed" action.

### Professional Oversight & Handoff
- **D-31:** Both live observation mode AND after-the-fact review — org chooses. Live: "Live Intakes" list shows active conversations. Open one for read-only view with analysis progress + gaps. "Take over" button enables interactive mode (send messages as Attorney, pause AI autonomy, edit/approve AI messages before sending). Consumer sees when human joins.
- **D-32:** Multi-party intakes via party switcher + per-party threads. Party switcher at top. Each party has own conversation thread. Facts attributed via party_id. Professional view shows parties side-by-side on desktop. Consumer sees only their own thread.

### Onboarding & First-Run
- **D-33:** All three consumer onboarding modes built — admin org chooses which to enable: (1) minimal (consent + name + start), (2) tutorial walkthrough (guided feature tour), (3) deployment-aware (law firm attorney context / legal aid org context / court self-help instructions).
- **D-34:** Both admin onboarding modes built — user org admin chooses: (1) setup wizard (org profile → deployment → protocols → output profiles → research tools → KB), (2) dashboard with inline tips.

### Performance & Loading Strategy
- **D-35:** Mobile-first performance targets: LCP < 2.5s on simulated 3G, initial JS bundle < 200KB gzipped, total page weight < 1MB on initial load, Lighthouse Performance score > 90. Critical for legal aid/court self-help users on older devices + slower connections.
- **D-36:** Skeletons (not spinners) for initial renders. Route-based code splitting: chat, dashboard, admin, output as separate bundles. Message history paginated (50/page) with "load earlier" button. Intake list paginated with virtual scrolling for 100+ intakes.

### Claude's Discretion
- Specific React component structure and file organization
- Exact color palette values per theme (within the aesthetic direction)
- Specific icon library choice
- Specific illustration style for empty states
- Exact Zustand store structure
- React Query cache key conventions
- Specific SSO provider implementations (Google OIDC, Microsoft Azure AD flows)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Dependencies
- `.planning/phases/01-foundation-security/01-CONTEXT.md` — JWT auth, refresh tokens, roles
- `.planning/phases/03-input-narrative-capture/03-CONTEXT.md` — WebSocket chat, voice, documents, multi-party
- `.planning/phases/04-core-analysis-pipeline/04-CONTEXT.md` — Analysis orchestrator stages, progress UX (D-15)
- `.planning/phases/05-pre-research-exploration-safety/05-CONTEXT.md` — Three-tier safety alerts (critical/elevated/advisory)
- `.planning/phases/07-output-export/07-CONTEXT.md` — Output profiles (law_firm, legal_aid, court_self_help)

### Existing Code
- `frontend/package.json` — React 18 + Vite + TypeScript + Tailwind 3.x scaffold
- `frontend/src/App.tsx` — Existing scaffold to build on
- `backend/app/routers/intake.py` — WebSocket endpoint `/api/ws/intake/{session_id}`
- `backend/app/routers/analysis.py` — Analysis REST API
- `backend/app/routers/output.py` — Output generation and export endpoints

### Requirements
- `.planning/REQUIREMENTS.md` §Frontend Visualization — FRONTEND-01, FRONTEND-02, FRONTEND-06, FRONTEND-07, FRONTEND-08, FRONTEND-09, FRONTEND-10

### Design Reference
- LSC (Legal Services Corporation) language recommendations — informs i18n language set
- WCAG 2.2 AA specification — accessibility target

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Vite + React + TypeScript + Tailwind 3.x scaffold** from Phase 1 — minimal starting point
- **Backend WebSocket + REST APIs** from Phases 3-7 — complete backend ready to consume

### Established Patterns
- Backend returns JSON with consistent error formats
- JWT auth with refresh tokens
- WebSocket at `/api/ws/intake/{session_id}` with ?token= query param
- REST API base: `/api/v1/...`

### Integration Points
- Frontend consumes existing backend API (no new backend work except SSO per D-21)
- Theme system parallels Phase 7's output profiles
- Safety alert UI consumes Phase 5's three-tier screening events
- Analysis progress UI consumes Phase 4's WebSocket broadcasts

</code_context>

<specifics>
## Specific Ideas

- Three aesthetics tied to deployment profile (not user preference) — maintains consistency per org
- LLM always thinks in English for best reasoning; frontend translates outputs to user language
- Parallel language outputs enable legal professional review alongside consumer version
- "Build both/all, let admin choose" pattern appears multiple times — configurable frontend, not opinionated
- Critical safety alerts are non-dismissible banner (life-safety > UX convenience)
- Performance targets explicitly aimed at mobile/slow connections (legal aid/court audiences)
- LSC's 7 recommended languages ship by default

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. Phase 9 handles fact-mapping visualizations (graph, matrix, narrative-anchored).

</deferred>

---

*Phase: 08-frontend-application*
*Context gathered: 2026-04-05*
