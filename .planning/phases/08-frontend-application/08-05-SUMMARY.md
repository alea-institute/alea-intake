---
phase: 08-frontend-application
plan: 05
subsystem: ui
tags: [wavesurfer, voice-recording, safety-alerts, react, zustand, react-query, radix-ui, accessibility]

# Dependency graph
requires:
  - phase: 08-02
    provides: ThemeProvider, apiFetch, i18n config, MSW test infra
  - phase: 08-04
    provides: WebSocket hooks, ChatInput, ChatPage, chat store, ConnectionBanner
provides:
  - VoiceRecorder with wavesurfer.js live waveform and MIME-safe recording
  - TranscriptReview with inline edit, audio playback, low-confidence highlights
  - DocumentUploader with type/size validation
  - AnalysisProgressPanel with mobile collapse and React Query wiring
  - SafetyBanner (critical-tier non-dismissible) + SafetyDrawer with default hotlines
  - SafetyNotificationBadge (elevated-tier count badge)
  - ChatInput wired to switch between text/voice/document modality surfaces
affects: [08-06, 09-integration-testing, 10-deployment]

# Tech tracking
tech-stack:
  added: ["@radix-ui/react-dialog", "@radix-ui/react-alert-dialog", "@radix-ui/react-separator"]
  patterns: ["wavesurfer Record plugin mimeType at create-time (not startRecording)", "Zustand for local UI state (drawer open/close)", "WebSocket-populated React Query cache with enabled:false"]

key-files:
  created:
    - frontend/src/features/chat/components/VoiceRecorder.tsx
    - frontend/src/features/chat/components/TranscriptReview.tsx
    - frontend/src/features/chat/components/DocumentUploader.tsx
    - frontend/src/features/chat/components/AnalysisProgressPanel.tsx
    - frontend/src/features/safety/components/SafetyBanner.tsx
    - frontend/src/features/safety/components/SafetyDrawer.tsx
    - frontend/src/features/safety/components/SafetyNotificationBadge.tsx
    - frontend/src/features/safety/hooks/useSafetyAlerts.ts
    - frontend/src/features/safety/api.ts
    - frontend/src/features/safety/store.ts
    - frontend/src/components/ui/sheet.tsx
    - frontend/src/components/ui/dialog.tsx
    - frontend/src/components/ui/alert-dialog.tsx
    - frontend/src/components/ui/separator.tsx
  modified:
    - frontend/src/features/chat/components/ChatInput.tsx
    - frontend/src/features/chat/ChatPage.tsx
    - frontend/public/locales/en/chat.json
    - frontend/public/locales/en/safety.json

key-decisions:
  - "RecordPlugin mimeType set at create-time not startRecording (TypeScript type mismatch)"
  - "SafetyBanner uses button with role=alert for clickable non-dismissible banner"
  - "AnalysisProgressPanel uses enabled:false React Query (WebSocket-only data source)"
  - "ChatInput conditionally renders modality surfaces (voice/document) instead of always showing textarea"

patterns-established:
  - "Safety feature module: api.ts + store.ts + hooks/ + components/ pattern"
  - "Non-dismissible alert: button element with role=alert + aria-live=assertive"
  - "WebSocket-only data: useQuery with enabled:false + staleTime:Infinity"

requirements-completed: [FRONTEND-02, FRONTEND-10]

# Metrics
duration: 10min
completed: 2026-04-06
---

# Phase 8 Plan 05: Voice, Analysis Progress, and Safety Alerts Summary

**Voice recording with wavesurfer.js waveform, analysis progress panel with mobile collapse, and three-tier safety alert system with default hotlines**

## Performance

- **Duration:** 10 min
- **Started:** 2026-04-06T03:33:33Z
- **Completed:** 2026-04-06T03:44:08Z
- **Tasks:** 4
- **Files modified:** 25

## Accomplishments
- VoiceRecorder with live waveform via wavesurfer.js Record plugin, MIME-safe recording (webm opus preferred, mp4 fallback), 3-min max duration, 44px touch targets
- TranscriptReview with editable textarea, audio playback, per-word low-confidence highlighting (threshold 0.6)
- DocumentUploader with PDF/DOCX/JPG/PNG/TIFF type validation and 25MB size limit with i18n errors
- AnalysisProgressPanel reads from WebSocket-populated React Query cache, shows stage/iteration/completeness/next, collapses on mobile
- SafetyBanner renders non-dismissible critical-tier alert with per-theme copy and links to SafetyDrawer
- SafetyDrawer contains 3 default hotlines (National DV Hotline, 988 Crisis Lifeline, Childhelp)
- SafetyNotificationBadge shows elevated-tier count with bell icon
- ChatInput wired to conditionally render VoiceRecorder/DocumentUploader based on active modality
- 27 tests pass across 5 test files

## Task Commits

Each task was committed atomically:

1. **Task 1: VoiceRecorder + TranscriptReview + DocumentUploader** - `6467073` (feat)
2. **Task 2: AnalysisProgressPanel with mobile collapse + React Query wiring** - `e05a031` (feat)
3. **Task 3: Safety alerts -- critical banner + drawer + elevated badge** - `fd2dfcc` (feat)
4. **Task 4: Wire VoiceRecorder and DocumentUploader into ChatInput** - `f6eaddd` (feat)

## Files Created/Modified
- `frontend/src/features/chat/components/VoiceRecorder.tsx` - Tap-to-record with wavesurfer.js Record plugin, live waveform, elapsed timer
- `frontend/src/features/chat/components/TranscriptReview.tsx` - Inline-edit textarea + audio player + low-confidence word highlights
- `frontend/src/features/chat/components/DocumentUploader.tsx` - File input with type/size validation and i18n errors
- `frontend/src/features/chat/components/AnalysisProgressPanel.tsx` - Persistent collapsible progress panel reading from React Query cache
- `frontend/src/features/safety/components/SafetyBanner.tsx` - Critical-tier non-dismissible banner with per-theme copy
- `frontend/src/features/safety/components/SafetyDrawer.tsx` - Safety resources sheet with default hotlines + alert-specific resources
- `frontend/src/features/safety/components/SafetyNotificationBadge.tsx` - Elevated-tier badge with count on bell icon
- `frontend/src/features/safety/hooks/useSafetyAlerts.ts` - React Query hook fetching from /api/v1/intakes/{sessionId}/safety
- `frontend/src/features/safety/api.ts` - Safety alert REST API fetch wrapper
- `frontend/src/features/safety/store.ts` - Zustand store for drawer open/close state
- `frontend/src/components/ui/sheet.tsx` - shadcn Sheet (side drawer) primitive
- `frontend/src/components/ui/dialog.tsx` - shadcn Dialog primitive
- `frontend/src/components/ui/alert-dialog.tsx` - shadcn AlertDialog primitive
- `frontend/src/components/ui/separator.tsx` - shadcn Separator primitive
- `frontend/src/features/chat/components/ChatInput.tsx` - Modified to conditionally render voice/document surfaces
- `frontend/src/features/chat/ChatPage.tsx` - Wired SafetyBanner + SafetyDrawer + AnalysisProgressPanel

## Decisions Made
- **RecordPlugin mimeType at create-time:** TypeScript types define `startRecording(options?: MediaTrackConstraints)` which doesn't include mimeType. The mimeType belongs in `RecordPlugin.create()` options instead.
- **Button with role=alert for SafetyBanner:** The critical banner is both clickable (opens drawer) and an alert. Using `<button role="alert" aria-live="assertive">` combines both semantics.
- **WebSocket-only data for AnalysisProgressPanel:** Progress data flows exclusively from WebSocket events, so React Query is used with `enabled: false` and `staleTime: Infinity` -- never fetched via HTTP.
- **Conditional modality rendering in ChatInput:** Instead of always rendering textarea, ChatInput now hides it when voice/document modality is active and shows the appropriate surface component.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed RecordPlugin mimeType TypeScript error**
- **Found during:** Task 3 (build check)
- **Issue:** `startRecording({ mimeType: mime })` fails TypeScript check because `RecordPluginDeviceOptions = MediaTrackConstraints` doesn't include `mimeType`
- **Fix:** Moved mimeType to `RecordPlugin.create()` options where it's properly typed
- **Files modified:** `frontend/src/features/chat/components/VoiceRecorder.tsx`
- **Verification:** `npm run build` passes
- **Committed in:** fd2dfcc (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Type-safe fix, no behavioral change. MIME type is still set correctly per Pitfall 3.

## Issues Encountered
- i18n not initialized in test environment causes translation keys to render as raw keys (e.g., `common:cta.startRecording`). Tests updated to match raw key patterns where needed. This is consistent with how other Plan 08-04 tests handle it.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Chat page is now fully featured: text + voice + document input, analysis progress, safety alerts
- Ready for integration testing and end-to-end flows
- SafetyNotificationBadge available for use in chat header (not yet wired to a header component)

## Self-Check: PASSED

- All 14 created files verified present on disk
- All 4 task commits verified in git log (6467073, e05a031, fd2dfcc, f6eaddd)
- 27 tests pass across 5 test files
- Build passes, bundle within 200KB budget

---
*Phase: 08-frontend-application*
*Completed: 2026-04-06*
