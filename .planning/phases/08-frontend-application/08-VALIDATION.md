---
phase: 08
slug: frontend-application
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-05
---

# Phase 08 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Vitest 3.3 + @testing-library/react + jsdom; Playwright 1.59 + @axe-core/playwright for E2E; MSW 2.12 for API mocks |
| **Config file** | frontend/vitest.config.ts, frontend/playwright.config.ts |
| **Quick run command** | `cd frontend && npx vitest run --reporter=dot` |
| **Full suite command** | `cd frontend && npx vitest run && npx playwright test` |
| **Estimated runtime** | ~30s unit/component; ~90s E2E + axe scans |
| **Bundle gate** | `cd frontend && node scripts/check-bundle-size.mjs` (fails if main chunk > 200KB gzipped) |

## Sampling Rate

- **After every task commit:** Run component tests for modified feature folder
- **After every plan wave:** Run full Vitest suite + bundle gate
- **Before `/gsd:verify-work`:** Full Vitest + Playwright + bundle gate all green
- **Max feedback latency:** 30s for unit tests, 200s for full suite

## Wave 0 Requirements

Plan 08-01 (Foundation) establishes test infrastructure. All other plans create tests inline via TDD. No separate Wave 0 test-stub creation needed.

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Theme switching visually correct | D-01 | Visual regression | Switch org theme, verify fonts/colors change |
| Voice recording mic permission | FRONTEND-10 | Browser permission | Record in Chrome/Safari/Firefox, verify waveform |
| Critical safety banner non-dismissible | D-29 | UX verification | Trigger DV protocol, verify banner persists |
| PDF export renders correctly | FRONTEND-07 | Visual check | Export memo, open in Preview/Acrobat |
| i18n language switch | D-27 | Visual verification | Switch to Spanish/Chinese/etc, verify UI + content |
| Mobile responsive layouts | FRONTEND-09 | Real device testing | Test on iPhone/Android at 375px/414px widths |
| Screen reader flows | D-19 | A11y verification | Test with VoiceOver/NVDA on chat, dashboard, admin |

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or inline TDD
- [x] Sampling continuity maintained across waves
- [x] Wave 0 infrastructure covered by Plan 08-01
- [x] Bundle budget enforced via check-bundle-size.mjs gate
- [x] axe-core accessibility scans in Playwright E2E
- [x] `nyquist_compliant: true` set

**Approval:** pending
