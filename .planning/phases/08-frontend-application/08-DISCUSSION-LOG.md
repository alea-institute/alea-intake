# Phase 8: Frontend Application - Discussion Log

> **Audit trail only.** Decisions are in CONTEXT.md.

**Date:** 2026-04-05
**Phase:** 08-frontend-application
**Areas discussed:** Chat interface design, State management & data flow, Dashboard & navigation, Admin interface design, Voice recording UX, Output display & export, Mobile responsiveness, Accessibility, Authentication & login flow, Error & empty states, Theme system & org branding, i18n & localization, Critical safety alert UX, Professional oversight & handoff, Onboarding & first-run, Performance & loading strategy

---

## Key Architectural Decisions

- **Three aesthetic themes** tied to Phase 7 deployment profiles (law_firm/legal_aid/court_self_help) — NOT user preference
- **LLM thinks in English, frontend translates** — best reasoning + parallel outputs for professional review
- **"Build both/all, org admin chooses"** pattern — configurable frontend across many UX options
- **Critical safety alerts are non-dismissible** — life-safety > UX convenience
- **Mobile-first performance** (LCP < 2.5s on 3G) — legal aid/court audiences
- **7 LSC languages** ship by default: English, Spanish, Chinese, Vietnamese, Korean, Tagalog/Filipino, Russian
- **SSO backend work** included in this phase (scope expansion beyond Phase 1 auth)

---

## User's Direct Input (selected highlights)

### Chat aesthetic
"Customized to the end user — some users might be legal professional (who get the legal professional aesthetic) and other users might be layperson legal consumers (who get the modern conversational rounded), and some users might be judicial (who get Courthouse classic)."

### Admin onboarding
"Organization Admin can choose — between (1) Wizard and (2) Tabbed sections with inline forms (with sensible defaults)."

### Protocol management
"Both — with User being able to toggle between Card View and Table View."

### i18n scope
"Full i18n infrastructure + English + Spanish + the other languages that the Legal Services Corporation recommends: Chinese (Mandarin/Cantonese), Vietnamese, Korean, Tagalog/Filipino, Russian"

### LLM translation strategy
"LLM outputs in English (back end) but the front end gets translated to the user's selected language — parallel outputs allowing review by both (1) consumers and (2) legal professionals (who usually speak English as their native tongue), and also more helpful since LLMs 'think' best in English."

### Professional oversight
"Build Both. Organization can decide which it wants."

### Consumer onboarding
"Build all three, with the Admin Organization deciding which to turn on."

### Dashboard layout
"Hybrid: switchable table ↔ card view"

### SSO
"Can we give the user a choice to use either (1) Email/password + refresh token flow or (2) SSO options (e.g., Oauth from Google, Microsoft, etc.)."

---

## Deferred Ideas
None — Phase 9 handles fact-mapping visualizations.
