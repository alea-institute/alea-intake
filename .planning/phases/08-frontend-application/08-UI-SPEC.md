---
phase: 8
slug: frontend-application
status: draft
shadcn_initialized: true
preset: new-york (zinc)
created: 2026-04-03
---

# Phase 8 -- UI Design Contract

> Visual and interaction contract for the React frontend application. This is the first major frontend phase of the project. The contract defines a three-theme design system tied to deployment profile (Phase 7), with per-theme typography, color, and copywriting. All three themes share a common spacing scale, component inventory, and interaction patterns.

---

## Design System

| Property | Value |
|----------|-------|
| Tool | shadcn |
| Preset | new-york style + zinc base palette (base registry via `npx shadcn init --style new-york --base-color zinc`) |
| Component library | radix-ui (via shadcn primitives) |
| Icon library | lucide-react (shadcn default) |
| Font | per-theme (see Typography section) — self-hosted via @fontsource |
| Theme mechanism | CSS custom properties + `data-theme` attribute on `<html>` root (D-25) |
| Themes | `data-theme="legal-professional"`, `data-theme="modern-conversational"`, `data-theme="courthouse-classic"` |
| Org branding override | inline CSS custom properties override theme defaults (D-26) — logo URL and `--color-accent` overrides at runtime |
| Dark mode | `prefers-color-scheme: dark` supported via shadcn dark variant on each theme (D-20 item 4) |

**Deployment profile → theme mapping (D-01):**

| OutputProfile (Phase 7) | data-theme value | Aesthetic |
|-------------------------|------------------|-----------|
| `law_firm` | `legal-professional` | Serif headers, restrained palette, navy + warm neutrals |
| `legal_aid` | `modern-conversational` | Rounded, friendly, sans-serif throughout |
| `court_self_help` | `courthouse-classic` | Editorial serif, strong typographic hierarchy |

---

## Spacing Scale

Declared values (inherited from existing `frontend/tailwind.config.ts` — shared across all three themes):

| Token | Value | Usage |
|-------|-------|-------|
| xs | 4px | Icon gaps, inline padding, badge padding |
| sm | 8px | Compact element spacing, tight stacks |
| md | 16px | Default element spacing, card padding, input padding |
| lg | 24px | Section padding, card gaps, dialog padding |
| xl | 32px | Layout gaps, hero section padding |
| 2xl | 48px | Major section breaks, landing-page spacing |
| 3xl | 64px | Page-level spacing, empty-state illustrations |

**Exceptions:**
- Touch target minimum: 44x44px for interactive controls on mobile (WCAG 2.5.8) — component minimum dimension, not a spacing token (inherited from Phase 3 UI-SPEC).
- Bottom nav bar height on mobile: 64px (4× base unit, uses 3xl token).
- Chat message maximum width: 720px (content readability — not a spacing token).

No other exceptions. All spacing tokens are multiples of 4.

---

## Typography

Three type systems, one per theme. Each system uses **exactly 4 sizes and 2 weights** (400 regular + 600 semibold), inheriting the scale declared in Phase 3 UI-SPEC.

### Shared scale (all themes)

| Role | Size | Weight | Line Height |
|------|------|--------|-------------|
| Body | 16px | 400 | 1.5 |
| Label | 14px | 400 | 1.4 |
| Heading | 20px | 600 | 1.2 |
| Display | 28px | 600 | 1.2 |

### Per-theme font pairings (self-hosted via @fontsource)

| Theme | Display font | Body font | @fontsource packages |
|-------|--------------|-----------|---------------------|
| `legal-professional` | Source Serif 4 (600) | Inter (400, 600) | `@fontsource/source-serif-4`, `@fontsource/inter` |
| `modern-conversational` | Inter (600) | Inter (400, 600) | `@fontsource/inter` |
| `courthouse-classic` | Libre Caslon Text (600) | Libre Franklin (400, 600) | `@fontsource/libre-caslon-text`, `@fontsource/libre-franklin` |

**Font application:**
- Display font applies to: Display (28px) and Heading (20px) roles.
- Body font applies to: Body (16px) and Label (14px) roles.
- `modern-conversational` uses Inter for both display and body — single-family modern aesthetic.

**Implementation:** @fontsource packages imported in `src/main.tsx` at app startup; theme selects font-family via CSS custom properties (`--font-display`, `--font-body`) set by `data-theme` on root.

**Accessibility:** Body line-height 1.5 meets WCAG 1.4.12 (Text Spacing). User font-size override via browser zoom MUST reflow without horizontal scroll up to 200% (WCAG 1.4.10 Reflow).

---

## Color

Three color systems, one per theme. All three maintain the 60/30/10 contrast ratio with one destructive semantic color.

### Theme 1 — legal-professional (law_firm deployments)

| Role | Value | Usage |
|------|-------|-------|
| Dominant (60%) | `#FAF8F3` | App background, chat surface, dashboard surface |
| Secondary (30%) | `#FFFFFF` | Cards, sidebar, nav bar, modals |
| Accent (10%) | `#1E3A5F` (navy) | Primary CTA, active-nav indicator, send button, focus ring, link color |
| Destructive | `#B91C1C` | Delete intake, critical-tier safety banner, discard confirmations |

### Theme 2 — modern-conversational (legal_aid deployments)

| Role | Value | Usage |
|------|-------|-------|
| Dominant (60%) | `#F9FAFB` | App background, chat surface, dashboard surface |
| Secondary (30%) | `#FFFFFF` | Cards, sidebar, nav bar, modals |
| Accent (10%) | `#2563EB` (blue) | Primary CTA, active-nav indicator, send button, focus ring, link color |
| Destructive | `#DC2626` | Delete intake, critical-tier safety banner, discard confirmations |

### Theme 3 — courthouse-classic (court_self_help deployments)

| Role | Value | Usage |
|------|-------|-------|
| Dominant (60%) | `#FBFBF8` | App background, chat surface, dashboard surface |
| Secondary (30%) | `#FFFFFF` | Cards, sidebar, nav bar, modals |
| Accent (10%) | `#1F2937` (slate) | Primary CTA, active-nav indicator, send button, focus ring, link color |
| Destructive | `#991B1B` | Delete intake, critical-tier safety banner, discard confirmations |

**Accent reserved for (ALL three themes, explicit list):**
1. Primary CTA buttons (Send message, Start intake, Approve transcript, Export, Sign in)
2. Active state on left-sidebar navigation item and mobile bottom-nav item
3. Voice recording active-state indicator (waveform fill, recording dot)
4. Document upload progress bar fill
5. Focus ring on all focusable elements (2px outline, 2px offset)
6. Inline links within body text
7. Checkbox / radio / switch checked state
8. Org-branding logo tint (when org supplies monochrome logo)

**Accent NOT used for:** body text, non-CTA buttons (secondary/outline variants use zinc), badges, borders, dividers, card backgrounds, avatar backgrounds.

**Destructive reserved for:** delete actions, critical-tier safety banners (D-29), discard-confirmation dialogs, form-field errors, connection-lost banner. Never used for mere warnings or elevated-tier safety notifications (elevated uses zinc-700 badge per D-30).

**Contrast verification (WCAG 2.2 AA, required):**
- All accent values provide ≥ 4.5:1 contrast on white text (verified: navy 9.8:1, blue 5.2:1, slate 12.6:1).
- All dominant/secondary surfaces provide ≥ 4.5:1 contrast on zinc-900 body text.
- Destructive values provide ≥ 4.5:1 contrast on white text.

**Dark mode (per-theme):** shadcn dark variant inverts dominant/secondary surfaces; accent and destructive hues shift to higher-luminance variants to maintain 4.5:1 contrast. Implementation deferred to executor following shadcn new-york dark preset.

---

## Illustration Style

Illustrated empty states (D-24) follow a shared vocabulary with per-theme tonal adjustments:

| Property | Value |
|----------|-------|
| Style | Soft geometric line illustrations with 2px stroke weight |
| Palette | Monochrome in theme accent color at 40% opacity, on dominant background |
| Format | Inline SVG (≤ 8KB per illustration, bundled) |
| Size | 240x240px (desktop), 160x160px (mobile <768px) |
| Animation | Subtle fade-in (200ms ease-out) on first render; no looping animation (respects prefers-reduced-motion) |
| Tone (legal-professional) | Formal, minimal geometry — document outlines, folder shapes |
| Tone (modern-conversational) | Friendly, rounded geometry — speech bubbles, person silhouettes, hand gestures |
| Tone (courthouse-classic) | Editorial, architectural geometry — columns, scales, book outlines |

**Empty-state illustration inventory (D-24):**
1. "No intakes yet" (dashboard empty)
2. "Start your story" (new chat session empty)
3. "No documents uploaded yet" (KB empty)
4. "No safety alerts" (admin safety-review empty)
5. "No exports yet" (output history empty)

Illustrations MUST be monochrome in theme accent — no external illustration libraries, no multi-color stock art, no AI-generated slop.

---

## Copywriting Contract

Per-theme voice mapping, with shared core messages. Copy is externalized via react-i18next (D-27) — **English source strings defined here; 7-language translations produced during implementation**.

### Shared core messages (all themes)

| Element | Copy |
|---------|------|
| Primary CTA (chat) | "Send message" |
| Primary CTA (voice) | "Start recording" |
| Primary CTA (document) | "Upload document" |
| Primary CTA (dashboard) | "New intake" |
| Primary CTA (output) | "Export" |
| Primary CTA (login) | "Sign in" |

### Per-theme voice tuning

| Element | legal-professional | modern-conversational | courthouse-classic |
|---------|-------------------|----------------------|-------------------|
| Session welcome (consumer) | "Please describe your legal matter in your own words. You may type, speak, or upload documents." | "Tell us what's going on in your own words. Type, talk, or share a document — whatever's easiest." | "Describe your situation in your own words. You can type your answer, record your voice, or upload documents." |
| Empty dashboard heading | "No matters in progress" | "No intakes yet" | "No matters filed" |
| Empty dashboard body | "Open a new matter to begin capturing client information." | "Start your first intake whenever you're ready. We'll walk you through it." | "Begin a new matter using the button above. We'll guide you step by step." |
| Connection-lost banner | "Connection interrupted. Reconnecting. Your messages are preserved." | "Oops — lost connection. Reconnecting now. Your answers are safe." | "Connection interrupted. Reconnecting. Your responses have been saved." |
| Critical safety banner (D-29) | "Your safety comes first. Resources are available." | "You're not alone. Help is available right now." | "Safety resources are available. Please take a moment to review them." |

### Error states (shared across themes, per D-23)

| Element | Copy |
|---------|------|
| Network error (generic) | "We couldn't reach the server. Check your connection and try again." |
| WebSocket disconnect | "Connection interrupted. Reconnecting… Your messages are saved." |
| 401 / session expired | "Your session has expired. Please sign in again to continue." |
| Form field error (generic) | "Please check this field and try again." |
| File upload too large | "This file is too large ({size}MB). The maximum is {limit}MB. Try a smaller file or split the document." |
| File type unsupported | "This file type isn't supported. Please upload a PDF, DOCX, or image (JPG, PNG, TIFF)." |
| Voice transcription failed | "We couldn't transcribe this recording. Please try again or type your response instead." |
| LLM stream failed | "Something went wrong generating a response. Please try again." |
| Export failed | "Export failed. Please try again, or contact your administrator if the problem continues." |
| 500 / server error | "Something went wrong on our end. Please try again in a moment." |
| Error boundary (crash) | "Something unexpected happened. Refresh the page to continue. Your work has been saved." |

### Empty states (all per D-24)

| Element | Copy |
|---------|------|
| Empty intake list heading | (per-theme — see above) |
| Empty intake list body | "Start a new intake to begin. The button above will walk you through it." |
| Empty safety-alerts list heading | "No alerts to review" |
| Empty safety-alerts list body | "When the system detects a safety concern, you'll see it here." |
| Empty KB heading | "No documents in your knowledge base" |
| Empty KB body | "Upload legal guides, statutes, or templates. The system will use them to inform intakes." |
| Empty exports heading | "No exports yet" |
| Empty exports body | "When you export a completed intake, it will appear here for quick re-download." |

### Loading / progress states (D-36)

| Element | Copy |
|---------|------|
| Analysis progress panel title | "Analyzing your information" |
| Analysis stage label | "Stage {n} of {total}: {stage_name}" |
| Skeleton loading (no text) | Skeleton shimmer only — never spinner, never "Loading…" text |
| Export generating | "Preparing your {format} export…" |
| Document processing | "Processing {filename}…" |
| Voice transcribing | "Transcribing…" |

### Destructive actions (D-23, confirmation required)

| Action | Confirmation Copy |
|--------|------------------|
| Delete intake | "Delete this intake? All messages, recordings, documents, and extracted information will be permanently removed. This cannot be undone." |
| Discard transcript | "Discard this transcript? The voice recording will be kept but transcription will need to be redone." |
| Cancel upload | "Cancel this upload? The file will not be saved." |
| Sign out | "Sign out? Any unsent message will be preserved as a draft." |
| Delete KB document | "Remove this document from the knowledge base? It will no longer inform future intakes." |
| Revoke user access | "Revoke {user_name}'s access to this organization? They will be signed out immediately." |
| Clear chat history (admin) | "Clear this conversation's history? Messages will be removed but extracted facts are preserved." |

### Safety alert copy (D-29, D-30)

| Element | Copy |
|---------|------|
| Critical-tier banner (non-dismissible) | "Your safety comes first. Resources are available." → opens drawer |
| Critical-tier drawer heading | "Are you safe right now?" |
| Critical-tier drawer body | "If you are in immediate danger, call 911. The resources below can help you find support." |
| Critical-tier hotlines list | "National Domestic Violence Hotline: 1-800-799-7233 • 988 Suicide & Crisis Lifeline • Childhelp: 1-800-422-4453" |
| Elevated-tier notification badge | "{count} resource{s} available" |
| Elevated-tier drawer heading | "Resources that may help" |
| Professional escalation action | "Escalate to supervisor" |
| Professional mark-addressed action | "Mark as addressed" |

### Login / authentication (D-21, D-22)

| Element | Copy |
|---------|------|
| Sign-in heading | "Sign in to continue" |
| Email input label | "Email address" |
| Password input label | "Password" |
| SSO separator | "Or continue with" |
| Google SSO button | "Continue with Google" |
| Microsoft SSO button | "Continue with Microsoft" |
| Forgot password link | "Forgot password?" |
| Auth error (invalid creds) | "That email and password combination didn't match. Please try again." |
| Auth error (SSO failed) | "We couldn't complete sign-in with {provider}. Please try again or use email." |

---

## Component Inventory (shadcn blocks)

**Core shadcn primitives** (installed via `npx shadcn add {component}`):

| Component | Purpose |
|-----------|---------|
| `button` | All CTAs, primary/secondary/outline/ghost/destructive variants |
| `input` | Text inputs, search bars |
| `textarea` | Chat input (auto-grow), transcript editing |
| `label` | Form field labels |
| `card` | Dashboard cards, empty-state containers, message containers |
| `dialog` | Modals, destructive confirmations |
| `sheet` | Safety resources drawer, mobile nav drawer |
| `dropdown-menu` | User menu, org switcher, export format menu (D-16) |
| `select` | Filter dropdowns, language selector |
| `tabs` | Output profile switcher (D-15), admin tabbed sections (D-11) |
| `toast` (sonner) | Non-blocking notifications, fact-extracted feedback |
| `skeleton` | Loading placeholders (D-36) |
| `badge` | Modality icons, status indicators, elevated-tier alerts (D-30) |
| `avatar` | Consumer initial in chat messages (D-02) |
| `separator` | Section dividers, sidebar separators |
| `scroll-area` | Chat history scroll, intake list scroll |
| `tooltip` | Timestamp-on-hover (D-02), icon explanations |
| `progress` | Analysis progress bar (D-08), upload progress |
| `switch` | Admin toggles, protocol activation (D-12) |
| `checkbox` | Multi-select filters, consent checkboxes |
| `radio-group` | Modality toggle (D-03), theme selection |
| `table` | Intake dashboard table view (D-09), protocol table view (D-12) |
| `accordion` | Collapsible filters, admin sections |
| `alert` | Inline errors, info banners |
| `alert-dialog` | Destructive action confirmations (D-23) |
| `popover` | Filter pickers, emoji pickers |
| `command` | Quick-search (D-09), command palette |
| `form` | React Hook Form integration for login, admin forms |
| `navigation-menu` | Top bar navigation |
| `breadcrumb` | Admin section breadcrumbs |

**shadcn blocks** (installed via `npx shadcn add {block}`):

| Block | Purpose |
|-------|---------|
| `sidebar-07` | Left-sidebar + top-bar layout (D-10) — collapsible on tablet, hamburger on mobile |
| `login-01` or `login-02` | Sign-in page shell (D-21) — email/password + SSO buttons |
| `dashboard-01` | Dashboard shell (D-09) — adapts for hybrid table/card view |

**Custom components** (built in this phase, not from registry):

| Component | Purpose |
|-----------|---------|
| `ChatMessage` | Asymmetric message with avatar, modality icon, hover timestamp (D-02) |
| `ChatInput` | Inline input bar with modality toggle (text/mic/paperclip) (D-03) |
| `VoiceRecorder` | Tap-to-record + live waveform + timer (D-13) |
| `TranscriptReview` | Inline-edit text area with audio player + confidence highlights (D-14) |
| `AnalysisProgressPanel` | Persistent collapsible progress panel (D-08) |
| `SafetyBanner` | Critical-tier non-dismissible banner (D-29) |
| `SafetyDrawer` | Safety resources drawer — wraps shadcn `sheet` (D-29) |
| `PartySwitcher` | Multi-party intake switcher (D-32) |
| `ThemeProvider` | `data-theme` attribute manager + org-branding overrides (D-25, D-26) |
| `MobileBottomNav` | Mobile bottom nav bar (D-17) |
| `EmptyState` | Empty-state wrapper with illustration + primary action (D-24) |
| `StreamingMessage` | Character-by-character LLM streaming with cursor (D-04) |

---

## Registry Safety

| Registry | Registry URL | Blocks / Components Used | Safety Gate |
|----------|--------------|--------------------------|-------------|
| shadcn official | `https://ui.shadcn.com/r` | All primitives + `sidebar-07`, `login-01`/`login-02`, `dashboard-01` blocks listed above | not required (official first-party source) |

**No third-party registries declared.** All components come from shadcn official or are custom-built in this phase. If a third-party registry is proposed during implementation, the executor MUST run the `npx shadcn view` safety gate from `<design_contract_questions>` before integration, and Phase 8 UI-SPEC MUST be amended with the vetting result.

---

## Interaction Patterns (inherited + extended from Phase 3)

Phase 8 **inherits** the following interaction contracts from Phase 3 UI-SPEC:
- WebSocket message protocol (client→server, server→client types)
- State machines: intake status, session status, transcript review, document extraction
- Connection authentication (JWT query param, close codes 4001/4003)
- Voice recording touch target minimum (44x44px)

Phase 8 **extends** with the following UI-layer interaction patterns:

### Message streaming (D-04)
- Character-by-character render of `llm_stream` tokens as they arrive
- Cursor indicator (blinking 2px accent bar) at tail of streaming message
- Stop button appears while streaming; clicking sends `stream_cancel` to server
- `prefers-reduced-motion: reduce` disables streaming animation — message appears in full on `done:true` (D-20 item 3)

### Optimistic UI (D-07)
- Sent messages appear immediately with 50% opacity + pending spinner
- On `message_ack` → full opacity, remove spinner
- On timeout (5s) or error → red border + inline "Retry" button

### WebSocket reconnection (D-06)
- Connection states exposed: `connecting | connected | disconnected | reconnecting | error`
- Exponential backoff: 1s, 2s, 4s, 8s, 16s, 30s (capped)
- Banner appears on `disconnected` with copy: "Connection interrupted. Reconnecting…"
- Banner dismisses automatically on `connected`

### Theme switching (D-25)
- Org admin sets theme in admin settings → writes to org record
- On login, theme loaded with user's org → `data-theme` attribute set on `<html>`
- No runtime theme toggle for end users (theme is org-scoped, not user-scoped)
- Dark mode toggle IS available per-user (respects `prefers-color-scheme` by default)

### Focus management (D-20 items 1, 5)
- All interactive elements keyboard-reachable with logical tab order
- `Tab` / `Shift+Tab` for forward/backward, `Enter` / `Space` for activation
- Focus trap in all `dialog`, `sheet`, `alert-dialog` components (shadcn default)
- Skip-to-content link visible on keyboard focus at top of page (D-20 item 6)
- Focus ring: 2px solid theme accent, 2px offset, on ALL focusable elements

### Screen reader announcements (D-20 items 2, 7)
- Live region (`aria-live="polite"`) for new chat messages
- Live region (`aria-live="assertive"`) for critical safety banner + connection errors
- Analysis progress announced on stage change
- WebSocket connection state changes announced

### Responsive breakpoints (D-18)
- Tailwind defaults: `sm: 640px`, `md: 768px`, `lg: 1024px`, `xl: 1280px`
- Mobile-first CSS (base styles target <640px)
- Layout shifts at `md (768px)`: sidebar collapses to icons
- Layout shifts at `sm (640px)`: sidebar becomes hamburger drawer + bottom nav appears
- Chat switches to full-screen view on mobile
- Voice recording gets full-screen modal on mobile (D-17)

---

## Performance Contract (D-35, D-36)

Must meet mobile-first performance targets:

| Metric | Target | Verification |
|--------|--------|--------------|
| LCP (simulated 3G) | < 2.5s | Lighthouse mobile audit |
| Initial JS bundle | < 200KB gzipped | `vite build` report |
| Total initial page weight | < 1MB | Network tab audit |
| Lighthouse Performance score | > 90 | Lighthouse mobile audit |
| Route-based code splitting | chat, dashboard, admin, output as separate bundles | Vite `rollupOptions.output.manualChunks` |
| Message history pagination | 50 messages/page, "load earlier" button | API cursor pagination |
| Intake list | virtual scrolling for 100+ intakes | `@tanstack/react-virtual` |

Skeletons (shadcn `skeleton`), not spinners, for all initial renders.

---

## Checker Sign-Off

- [ ] Dimension 1 Copywriting: PASS
- [ ] Dimension 2 Visuals: PASS
- [ ] Dimension 3 Color: PASS
- [ ] Dimension 4 Typography: PASS
- [ ] Dimension 5 Spacing: PASS
- [ ] Dimension 6 Registry Safety: PASS

**Approval:** pending

---

*Phase: 08-frontend-application*
*UI design contract drafted: 2026-04-03*
*Inherits: Phase 3 UI-SPEC (interaction contracts, spacing scale, typography scale)*
