---
phase: 13
name: practice-area-customization-demo
status: discussed
created: 2026-05-06
demo_date: 2026-05-06
---

# Phase 13 — Practice-Area Customization (Live Demo)

## Demo framing

Live presentation today. The "wow moments" are (in priority order):
1. **Process** — audience watches `/gsd-discuss-phase` → `/gsd-plan-phase` → `/gsd-execute-phase` shape a new practice area in real time, on stage.
2. **Artifact** — the deployed intake actually behaves differently for the new practice area.

Personal injury is the **baked-in seed practice**. During the demo, audience suggests a practice area (e.g., immigration, patent prosecution, family law) and the GSD/Claude flow generates a working config for it live, pushes, Railway redeploys, audience tries it.

## Architecture decision — locked

The existing intake is **conversational/LLM-guided**, not form-based (see `backend/app/services/intake/conversation.py:18`). So "customizing for a practice area" = changing the LLM's guidance, topic checklist, and welcome message — **not** adding form sections.

**Practice area = a configuration record** with these fields:
- `id` — slug (e.g., `personal_injury`, `immigration`)
- `display_name` — e.g., "Personal Injury"
- `welcome_message` — practice-tailored opener for consumer/professional modes
- `system_prompt` — LLM guidance specialized for this practice (replaces or extends `INTAKE_SYSTEM_PROMPT`)
- `key_topics` — checklist the conversation should cover (PI: liability theory, injuries, medical bills, lost wages, insurance carriers, statute of limitations)
- `extraction_hints` — practice-specific entities the extraction layer should look for (optional, post-MVP)

**Storage:** YAML files in `backend/app/services/intake/practice_areas/<id>.yaml`, loaded at startup. Reasons:
- Adding a practice = creating one file → trivially scriptable from a `/gsd-execute-phase` task
- No DB migration required → instant deploy
- Diff-friendly → audience sees the actual file generated on screen

**Session binding:** add `practice_area_id: str | None` to the session model. Default `None` = generic intake (current behavior). When set, conversation service loads that practice's config and uses it as the system prompt.

**Frontend:** practice-area selector chip-row on the landing/welcome screen. PI baked + any new practices the demo creates appear automatically.

## Deployment & branching strategy — locked

- **Branch:** `demo/practice-customization` off master
- **Railway service:** new service in `alea-tools` project named `alea-intake-demo` pointed at this branch, auto-deploy on push
- **Stable demo URL** (note for Damien: bookmark after first deploy)
- **Env vars:** copy from `alea-intake-dev` Railway service (see memory: reference_railway_deploy.md)
- **Pre-bake fallback:** PI config + mechanism + UI selector all merged and deployed before the talk. If live demo stalls, the existing PI experience already shows the differentiation.

## Live-demo execution plan

**Pre-talk (ships before demo):**
1. Practice-area config loader + YAML schema
2. `personal_injury.yaml` — full content (welcome, system prompt, topic checklist)
3. Session model accepts `practice_area_id`; conversation service uses practice's system prompt when set
4. Frontend: practice-area chip selector wired to session creation
5. Tests for loader and session-binding
6. Deployed to Railway demo URL, smoke-tested with PI

**On stage:**
1. Audience picks a practice area (e.g., "immigration")
2. Run `/gsd-discuss-phase` — Claude asks ~5 targeted questions: what are the key topics in immigration intake? what's the LLM persona? unique safety considerations?
3. Run `/gsd-plan-phase` — generates a plan to add `immigration.yaml`
4. Run `/gsd-execute-phase` — writes the YAML, runs tests, commits
5. `git push` → Railway redeploys (~60-90s)
6. Audience refreshes, picks "Immigration" from chip-row, walks through tailored intake

## Scope guardrails

- **In scope:** config-driven practice-area system, PI seed, UI selector, demo branch, Railway deploy, tests for loader/session-binding
- **Out of scope:** practice-specific extraction schemas (post-MVP), per-practice analysis pipeline tuning, admin UI for editing practices, multi-tenant practice scoping, auth-gated practices
- **Deferred ideas:** if a practice needs custom safety triggers (e.g., domestic violence in family law), document but don't implement live

## Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| Live execute hangs / network slow | Pre-baked PI deploy is the fallback. Continue talking through architecture while audience explores PI. |
| Generated YAML has bugs | Tests for loader run during `/gsd-execute-phase`; bad YAML fails fast before push. |
| LLM gives weird answers for new practice | System prompt template includes "stay on topics: {topics}" guard. Pre-test with at least 3 practice areas before talk. |
| Railway env var missing on new service | Copy env vars from `alea-intake-dev` during pre-talk setup; verify `/health` endpoint before going on stage. |
| Audience picks a sensitive practice (e.g., criminal defense, immigration enforcement) | Have a pre-prepared "sensitive practice" disclaimer; safety alert layer already exists. |

## Resolved decisions (confirmed 2026-05-06)

- **Selector UI:** chip-row above the welcome message, `Generic` as default; selecting a chip re-renders the welcome card with the practice's tailored copy.
- **Transcript metadata:** `practice_area_id` stored on the session record only; messages inherit by association. No per-message stamping. Extraction-layer awareness deferred.
- **Railway exposure:** new Railway service `alea-intake-demo` under the `alea-tools` project, pointed at branch `demo/practice-customization`, env vars copied from `alea-intake-dev`. Existing `alea-intake-dev` untouched.

## Next step

Run `/gsd-plan-phase 13` to generate the implementation plan. Time budget: aim for the pre-talk build to fit in <2 hours.
