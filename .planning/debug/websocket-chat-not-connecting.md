---
status: awaiting_human_verify
trigger: "WebSocket never connects on ChatPage. Send button stays disabled. No WS network requests."
created: 2026-04-03T00:00:00Z
updated: 2026-04-03T00:02:00Z
---

## Current Focus

hypothesis: CONFIRMED and FIXED - Three issues resolved: (1) Vite proxy missing ws:true, (2) message type mismatch, (3) ack format mismatch.
test: All 57 frontend tests pass, all 20 backend tests pass.
expecting: WebSocket connects in dev, messages are sent/acknowledged correctly.
next_action: Human verification in browser

## Symptoms

expected: WebSocket connects to backend at /api/ws/intake/{sessionId}?token={jwt}, chat input becomes enabled, user can send messages
actual: No WebSocket connection attempt. Send button stays disabled. Text input accepts typing but message can't be sent. No WS requests visible in network tab.
errors: No console errors related to WebSocket. The page renders correctly otherwise.
reproduction: 1) Register user via API, 2) Login at /login, 3) Grant consent at /consent, 4) Click "New intake" on dashboard, 5) Intake creates (POST /api/v1/intake/ returns 201), 6) ChatPage renders at /chat/1, 7) Input field shows but Send disabled, 8) No WS connection in network
started: WebSocket hook was built in Phase 8 Plan 04. The ChatPage was modified during Railway deployment debugging to change how sessionId is resolved.

## Eliminated

- hypothesis: useWebSocket hook never fires because sessionId stays empty after intake creation
  evidence: Wrote test ChatPage.newflow.test.tsx - WebSocket IS created with correct URL (ws://localhost:3000/api/ws/intake/42?token=test-token-abc) after intake creation. The resolvedSessionId state update correctly triggers the useWebSocket effect.
  timestamp: 2026-04-03T00:00:30Z

- hypothesis: accessToken is null when useWebSocket runs
  evidence: RequireAuth guard prevents ChatPage from rendering without accessToken. Test confirms token is passed correctly to WebSocket URL.
  timestamp: 2026-04-03T00:00:30Z

- hypothesis: navigate() causes component remount losing resolvedSessionId state
  evidence: React Router v6 with createBrowserRouter does not remount on param-only changes. Even if it did, useState initializer would correctly initialize from the new rawSessionId.
  timestamp: 2026-04-03T00:00:30Z

## Evidence

- timestamp: 2026-04-03T00:00:10Z
  checked: vite.config.ts proxy configuration
  found: proxy config has '/api' -> 'http://localhost:8000' with changeOrigin:true but NO ws:true option
  implication: WebSocket upgrade requests to /api/ws/... are NOT forwarded to the backend in dev mode. The browser sends the upgrade request to Vite, which handles it as HTTP (not WebSocket), causing the connection to fail.

- timestamp: 2026-04-03T00:00:20Z
  checked: ChatPage.newflow.test.tsx - tested /chat/new flow end-to-end
  found: WebSocket IS created after intake creation. Test passes. URL is correct. WS store reaches 'connected' status.
  implication: The useWebSocket hook logic is correct. The code DOES call new WebSocket() with the right URL. The issue is infrastructure (proxy), not application logic.

- timestamp: 2026-04-03T00:00:25Z
  checked: Frontend WSCommand type vs backend message handler
  found: Frontend sends type:'client_message' (types.ts line 57), backend checks for 'text_message' (intake.py line 449). No handler for 'client_message' exists.
  implication: Even after WS connects, messages would be silently dropped. Secondary bug.

- timestamp: 2026-04-03T00:00:26Z
  checked: Backend message_ack format vs frontend WSEvent type
  found: Backend sends {type:'message_ack', message_id, sequence_number} (intake.py line 551-555). Frontend expects {type:'message_ack', client_id, id, timestamp} (types.ts line 45).
  implication: Even if messages were sent correctly, acks would not be processed properly. Tertiary bug.

## Resolution

root_cause: Vite dev server proxy config missing `ws: true` option, preventing WebSocket upgrade requests from being forwarded to the FastAPI backend. Additionally, frontend/backend WebSocket message protocol was mismatched (frontend sent 'client_message' but backend expected 'text_message', and backend ack format lacked client_id/id/timestamp fields the frontend needed for optimistic update reconciliation).
fix: 1) Added ws:true to Vite proxy config (vite.config.ts). 2) Changed frontend WSCommand type from 'client_message' to 'text_message' (types.ts, ChatPage.tsx). 3) Updated backend message_ack to include client_id, id, and timestamp fields (intake.py).
verification: All 57 frontend tests pass (11 files). All 20 backend tests pass (test_intake_chat.py: 17, test_voice_intake.py: 3). Awaiting human browser verification.
files_changed: [frontend/vite.config.ts, frontend/src/features/chat/types.ts, frontend/src/features/chat/ChatPage.tsx, backend/app/routers/intake.py]
