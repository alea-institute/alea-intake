---
phase: 08-frontend-application
plan: 04
subsystem: ui
tags: [react, websocket, zustand, react-query, streaming, optimistic-ui, shadcn, chat]

# Dependency graph
requires:
  - phase: 08-02
    provides: ThemeProvider, auth store, apiFetch, i18n config, useReducedMotion hook
  - phase: 03
    provides: WebSocket message protocol (client_message, message_ack, llm_stream, etc.)
provides:
  - useWebSocket hook with exponential-backoff reconnect and React Query cache sync
  - useWSStore Zustand store for WebSocket connection state
  - Message/WSEvent/WSCommand/Modality/ConnectionStatus types
  - ChatMessage component with asymmetric layout, avatar/badge, modality icon, hover timestamp
  - StreamingMessage component with char-by-char cursor and stop button
  - ChatInput component with text/voice/document modality toggle
  - ConnectionBanner component with theme-specific disconnect copy
  - ChatPage with optimistic UI and 5s timeout failover
  - MessageList with auto-scroll and streaming message rendering
  - useIntakeMessages React Query hook for message history
  - 6 shadcn primitives (avatar, badge, scroll-area, textarea, tooltip, alert)
affects: [08-05, 08-06, admin, output]

# Tech tracking
tech-stack:
  added: [@radix-ui/react-avatar, @radix-ui/react-tooltip, @radix-ui/react-scroll-area]
  patterns: [WebSocket-to-React-Query cache sync, optimistic UI with timeout failover, exponential backoff with jitter]

key-files:
  created:
    - frontend/src/features/chat/types.ts
    - frontend/src/features/chat/store.ts
    - frontend/src/features/chat/hooks/useWebSocket.ts
    - frontend/src/features/chat/hooks/useIntakeSession.ts
    - frontend/src/features/chat/api.ts
    - frontend/src/features/chat/ChatPage.tsx
    - frontend/src/features/chat/components/ChatMessage.tsx
    - frontend/src/features/chat/components/StreamingMessage.tsx
    - frontend/src/features/chat/components/ChatInput.tsx
    - frontend/src/features/chat/components/ConnectionBanner.tsx
    - frontend/src/features/chat/components/MessageList.tsx
    - frontend/src/components/ui/avatar.tsx
    - frontend/src/components/ui/badge.tsx
    - frontend/src/components/ui/scroll-area.tsx
    - frontend/src/components/ui/textarea.tsx
    - frontend/src/components/ui/tooltip.tsx
    - frontend/src/components/ui/alert.tsx
  modified:
    - frontend/package.json
    - frontend/vitest.setup.ts

key-decisions:
  - "queueMicrotask for WebSocket mock (survives fake timers, unlike setTimeout)"
  - "ConnectionBanner uses shared error keys from common namespace rather than theme-scoped chat keys for consistency"
  - "ChatPage disables input when wsStatus !== connected (prevents user sending into void)"
  - "matchMedia + scrollIntoView polyfills added to vitest.setup.ts for jsdom compatibility"

patterns-established:
  - "WebSocket cache sync: handleEvent switch dispatches to queryClient.setQueryData/invalidateQueries per event type"
  - "Optimistic UI: create pending message in cache, send via ws, 5s timeout marks failed, message_ack confirms"
  - "New array reference on every setQueryData (Pitfall 2 from RESEARCH.md)"
  - "Auth-failure close codes (4001/4003) prevent reconnect to avoid infinite loop"

requirements-completed: [FRONTEND-01, FRONTEND-02]

# Metrics
duration: 11min
completed: 2026-04-06
---

# Phase 8 Plan 4: Chat Interface Summary

**WebSocket-driven chat page with optimistic UI, char-by-char LLM streaming, exponential-backoff reconnect, and modality toggle for text/voice/document input**

## Performance

- **Duration:** 11 min
- **Started:** 2026-04-06T03:00:55Z
- **Completed:** 2026-04-06T03:12:52Z
- **Tasks:** 3
- **Files modified:** 27

## Accomplishments

- **WebSocket lifecycle hook** with exponential backoff (1s-30s + jitter), React Query cache sync for 5 event types, and auth-failure short-circuit
- **Chat UI components** per D-02/D-03/D-04: asymmetric message layout, streaming cursor with reduced-motion support, input bar with modality toggle
- **Full ChatPage** with optimistic send (D-07), 5s timeout failover, connection banner (D-06), and stream cancel support

## WebSocket Event Handling

The `useWebSocket` hook is the central nervous system. All server events flow through a single `handleEvent` switch:

| Event | Cache Mutation |
|-------|---------------|
| `message_ack` | `setQueryData` -- replace pending message clientId with server id, status pending->sent |
| `llm_stream` | `setQueryData` -- append token to streaming message, or create new if first token |
| `analysis_progress` | `setQueryData` -- replace progress object |
| `safety_alert` | `invalidateQueries` -- triggers refetch of safety alerts |
| `fact_extracted` | `invalidateQueries` -- triggers refetch of facts |

## Optimistic UI Flow (D-07)

```
User types + Enter
  -> Create Message with status='pending', add to cache
  -> Send client_message via WebSocket
  -> Start 5s timeout
  
If message_ack arrives < 5s:
  -> Update cache: status='sent', assign server id
  
If no ack in 5s:
  -> Update cache: status='failed' (red border + retry affordance)
```

## Connection State Machine (D-06)

```
connecting --[onopen]--> connected --[onclose:1006]--> disconnected
     ^                                    |
     |                                    v
     +--------[setTimeout]----- reconnecting (backoff + jitter)

connected --[onclose:4001/4003]--> error (NO reconnect)
```

Backoff schedule: `[1000, 2000, 4000, 8000, 16000, 30000]ms` + random 0-300ms jitter per attempt.

## Bundle Size

| Chunk | Raw | Gzipped |
|-------|-----|---------|
| ChatPage lazy chunk | 105.7KB | 33.0KB |
| Main (index) | 181.0KB | 57.4KB |
| Budget (main) | - | 200KB |

ChatPage is lazy-loaded via `react-router-dom` dynamic import -- does not impact initial page load.

## Task Commits

Each task was committed atomically:

1. **Task 1: WebSocket hook + Zustand store + types + shadcn primitives** -- `7fe872b` (feat)
2. **Task 2: ChatMessage + StreamingMessage + ChatInput components** -- `f2d6d33` (feat)
3. **Task 3: ChatPage assembly with optimistic send + ConnectionBanner** -- `59543d6` (feat)

## Files Created/Modified

- `frontend/src/features/chat/types.ts` -- Message, WSEvent, WSCommand, Modality, ConnectionStatus types
- `frontend/src/features/chat/store.ts` -- Zustand store for WebSocket connection state
- `frontend/src/features/chat/hooks/useWebSocket.ts` -- WebSocket lifecycle hook with backoff reconnect + cache sync
- `frontend/src/features/chat/hooks/useWebSocket.test.ts` -- 8 tests for WebSocket hook
- `frontend/src/features/chat/hooks/useIntakeSession.ts` -- React Query hook for fetching message history
- `frontend/src/features/chat/api.ts` -- API fetch function for messages
- `frontend/src/features/chat/ChatPage.tsx` -- Full chat page with optimistic UI
- `frontend/src/features/chat/ChatPage.test.tsx` -- 6 tests for ChatPage + ConnectionBanner
- `frontend/src/features/chat/components/ChatMessage.tsx` -- Asymmetric message with avatar/badge, modality icon, tooltip
- `frontend/src/features/chat/components/ChatMessage.test.tsx` -- 5 tests
- `frontend/src/features/chat/components/StreamingMessage.tsx` -- Streaming with cursor + stop button
- `frontend/src/features/chat/components/StreamingMessage.test.tsx` -- 5 tests
- `frontend/src/features/chat/components/ChatInput.tsx` -- Modality toggle + auto-grow textarea
- `frontend/src/features/chat/components/ChatInput.test.tsx` -- 6 tests
- `frontend/src/features/chat/components/ConnectionBanner.tsx` -- Disconnect/reconnect banner
- `frontend/src/features/chat/components/MessageList.tsx` -- Message list with auto-scroll
- `frontend/src/components/ui/{avatar,badge,scroll-area,textarea,tooltip,alert}.tsx` -- 6 shadcn primitives

## shadcn Primitives Installed

Total after this plan: 7 (button from Plan 01, + 6 new: avatar, badge, scroll-area, textarea, tooltip, alert).

## Decisions Made

- **queueMicrotask for WS mock:** `setTimeout(0)` in WebSocket mock gets caught by `vi.useFakeTimers`; `queueMicrotask` survives because microtasks are not affected by fake timers
- **ConnectionBanner uses common error keys:** Shared `common:errors.websocketDisconnect` and `common:errors.sessionExpired` rather than per-theme chat keys, for copy consistency across components
- **Input disabled on disconnect:** `ChatInput` receives `disabled` prop when WebSocket is not connected, preventing user from sending messages into the void
- **Polyfills in vitest.setup.ts:** Added `matchMedia` (for `useReducedMotion`) and `scrollIntoView` (for `MessageList` auto-scroll) since jsdom doesn't implement these

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed pre-existing unused imports in LoginPage.test.tsx**
- **Found during:** Task 3 (build verification)
- **Issue:** `vi` and `afterEach` imported but unused in LoginPage.test.tsx, causing TypeScript build error
- **Fix:** Removed unused imports
- **Files modified:** frontend/src/features/auth/LoginPage.test.tsx
- **Verification:** `npm run build` succeeds
- **Committed in:** 59543d6 (Task 3 commit)

**2. [Rule 3 - Blocking] Added matchMedia polyfill for jsdom**
- **Found during:** Task 2 (StreamingMessage tests)
- **Issue:** `useReducedMotion` hook calls `window.matchMedia` which jsdom doesn't implement
- **Fix:** Added matchMedia mock to vitest.setup.ts
- **Files modified:** frontend/vitest.setup.ts
- **Committed in:** f2d6d33 (Task 2 commit)

**3. [Rule 3 - Blocking] Added scrollIntoView polyfill for jsdom**
- **Found during:** Task 3 (ChatPage tests)
- **Issue:** MessageList calls `endRef.current.scrollIntoView()` which jsdom doesn't implement
- **Fix:** Added `Element.prototype.scrollIntoView = () => {}` to vitest.setup.ts
- **Committed in:** 59543d6 (Task 3 commit)

---

**Total deviations:** 3 auto-fixed (3 blocking)
**Impact on plan:** All fixes necessary for test and build correctness. No scope creep.

## Known Stubs

None -- all components render real data flows. Voice recording and document upload modality buttons are structurally wired (toggle exists, mode switches) but actual recording/upload functionality comes in Plan 08-05.

## Issues Encountered

- **WebSocket mock + fake timers interaction:** Initial test mock used `setTimeout(0)` for auto-connect, which was blocked by `vi.useFakeTimers`. Switched to `queueMicrotask` which is not affected by fake timer mode.
- **Double MemoryRouter nesting:** `renderWithProviders` already wraps in `MemoryRouter`, causing "cannot render Router inside Router" error when ChatPage tests added their own. Fixed by using `render` directly with a custom `QueryClientProvider` wrapper.

## User Setup Required

None -- no external service configuration required.

## Next Phase Readiness

- Chat UI foundation complete -- voice recording (Plan 08-05) can wire into the modality toggle
- WebSocket hook handles all 5 event types -- analysis progress panel (future) can read from React Query cache
- ChatPage lazy-loaded; no impact on initial bundle size
- All 54 frontend tests pass

## Self-Check: PASSED

- All 22 created files verified present on disk
- All 3 task commits verified in git log (7fe872b, f2d6d33, 59543d6)
- 54 tests pass, build succeeds, bundle within budget

---
*Phase: 08-frontend-application*
*Plan: 04*
*Completed: 2026-04-06*
