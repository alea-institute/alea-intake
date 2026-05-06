# Phase 13 Demo Runbook — Practice-Area Customization

**Talk date:** 2026-05-06
**Branch:** `demo/practice-customization`
**Demo URL:** https://alea-intake-demo-production.up.railway.app
**Railway service:** `alea-intake-demo` in `alea-tools` project
**Railway service id:** `86f796a8-b8a7-49fa-830d-b410bbfa8937`
**Railway DB service:** `alea-intake-demo-db` (separate from dev)
**Demo user (already registered):** `demo@example.com` / `DemoPass123!`
**DB backend:** SQLite at `/app/data/alea_intake.db` on a Railway Volume (persists across redeploys). PostgreSQL is **not** used for the demo because of a pre-existing asyncpg "another operation in progress" bug that also affects `alea-intake-dev`. The demo Postgres service `alea-intake-demo-db` was created but is dormant.
**Railway DB password (dormant Postgres):** stored at `/tmp/demo-pg-pass.txt` on the dev box
**alea-tools project id:** `357ab7e1-d7cd-465e-b22b-74d6d2c4ea2e`

---

## Pre-talk checklist (T-30 min)

- [ ] **Demo URL live** — `curl -fsS https://alea-intake-demo-production.up.railway.app/health` returns `{"status":"healthy"}` (or at least `{"status":"degraded"}` with `database.status: "up"`)
- [ ] **Practice-areas endpoint** — `curl -fsS https://alea-intake-demo-production.up.railway.app/api/practice-areas | jq '.practice_areas[].id'` returns at least `personal_injury`
- [ ] **Browser sanity** — open the demo URL in a browser, register a fresh user (any `name@example.com`), click *New intake*, confirm chip-row visible with `Generic` + `Personal Injury` chips
- [ ] **PI welcome swap** — click `Personal Injury`, confirm welcome copy changes to PI text
- [ ] **Begin intake works** — click *Begin intake*, get a session, send a test message ("rear-ended last Tuesday"), confirm follow-up is PI-flavored
- [ ] **Claude Code (web) connected** to the Linux box, terminal sized for projector, font size up
- [ ] **Working directory:** `/home/damienriehl/Coding Projects/alea-intake`, on `demo/practice-customization`
- [ ] **`git status` clean**, `git pull` if anything happened upstream
- [ ] **Backup browser tab** pinned to demo URL (in case the live one crashes mid-talk)
- [ ] **emergency-configs/** directory open in a side editor pane in case live YAML generation fails
- [ ] **Screen brightness up**, browser zoom 110-125% so the chip-row and welcome copy are readable from the back row
- [ ] **Network is stable** — tether-on-tether if conference wifi is suspect; Railway redeploys need a working connection

---

## On-stage script

### Hook (~30s)

> "I'm going to build a custom legal intake for whatever practice area you shout out. Live. Right now. While you watch."

### Audience pick (~30s)

Take **one** suggestion. Repeat it back, write it on a sticky note for yourself.
> "Immigration. OK, so a lawyer working with clients on immigration matters."

### Show baseline (~60s)

Switch to the deployed app:
1. Open demo URL, log in (or use an existing session)
2. Click *New intake* → show the chip-row
3. Click `Generic` → show the generic welcome
4. Click `Personal Injury` → show the PI welcome rewrites the page in place; click *Begin intake* and send "I was rear-ended last Tuesday" — read the LLM follow-up aloud (it'll mention injuries / insurance / damages, very different from generic)
5. Land the point: > "That's the difference. Same UI, same code path -- different config, different LLM guidance, different conversation. The audience-suggested practice doesn't exist yet. We're going to make it exist in the next 8 minutes."

### Run the loop (~6-8 min)

Back in the terminal on `demo/practice-customization`:

```bash
/gsd-discuss-phase 14   # or whatever the next free phase number is
```

Tell GSD: *"Add a new practice area: immigration"* (or whatever the audience picked). Answer the questions on stage in plain English. Talking points while answering:
- "GSD is asking me what topics matter for this practice -- in immigration, it's status, family ties, deadlines, removal proceedings."
- "I'm shaping the LLM's voice -- be trauma-informed, never give legal advice, flag urgent deadlines."

Then:
```bash
/gsd-plan-phase   # generates the implementation plan -- usually one tiny YAML file
/gsd-execute-phase   # writes the YAML, runs loader tests, commits
git push
```

### Bridge while Railway redeploys (~60-90s)

Talk through what just happened:
- "What you just saw: a YAML file. Practice areas are config, not code. Adding one is one file."
- "The LLM system prompt is the leverage point -- everything else is plumbing."
- "Hand-coding intake forms doesn't scale. Config-driven intake plus a sharp prompt does."

(Watch Railway logs in another tab if you want — `railway logs --service alea-intake-demo` — but don't make the audience watch a build progress bar.)

### Reveal (~60s)

When the deploy completes (build is fast for incremental changes — likely 60-120s for a YAML-only change since Docker layer cache should hit):
1. Refresh the demo URL
2. Click the new chip (e.g., "Immigration")
3. Show the practice-aware welcome copy and disclaimer
4. Click *Begin intake*, send a realistic message ("My visa expires in 30 days and I just got laid off"), read the LLM follow-up aloud
5. Compare in your head to what the generic intake would have said

### Land it (~30s)

> "That's not a static demo. That's the system writing itself. Anyone in this room could do this for their own practice -- patent prosecution, family law, mass torts, whatever. Forty lines of YAML and you've got a tailored intake."

---

## Failure modes & responses

| If this happens | Do this |
|---|---|
| **Railway redeploy slow / stuck** | Keep talking through architecture. If it doesn't come up in 3 min, pivot: "the same mechanism works for PI, here's the live deployed version" -- show PI again. Don't apologize. |
| **Generated YAML fails loader tests** | `git reset --hard HEAD~1`, paste the matching emergency YAML from `.planning/phases/13-practice-area-customization-demo/emergency-configs/<practice>.yaml`, commit, push. Audience sees the same outcome. |
| **LLM follow-up doesn't sound practice-aware** | Pivot: "and this is why eval matters -- in production we'd catch this with regression tests on prompt-following." Then show the YAML and explain you'd refine the system prompt. |
| **Audience picks a sensitive practice** (criminal defense for accused, mass torts, etc.) | Use the family-law `disclaimer` pattern as a template. Acknowledge the sensitivity ("this is intake, not advice; safety screening still applies"). |
| **Audience picks something with weak training data for the LLM** | The system prompt does most of the work -- the LLM doesn't need to know niche law, just to ask focused questions. Show that the system prompt itself encodes the expertise. |
| **Network drops during push** | Open the Railway dashboard in the second browser tab, drop the YAML file directly into the GitHub UI on the demo branch -- Railway will pick it up. |
| **Demo URL just dies** | `railway logs --service alea-intake-demo` to diagnose. Worst case, point audience to the architecture diagram and walk through what *would* have happened. |

---

## Practice areas to pre-mention if audience asks

These three are pre-baked in `emergency-configs/` (validated by the loader, ready to paste):
- **Immigration** — country of origin, status, family, USCIS deadlines, removal proceedings, has trauma-informed disclaimer
- **Patent prosecution** — invention disclosure, prior art, inventors, public-disclosure one-year bar, USPTO actions, no disclaimer (technical not sensitive)
- **Family law** — marital status, children, court orders, financial picture, safety screening, has DV hotline disclaimer

If the audience picks one of these and live generation fails, you have the file ready.

---

## Dry-run results — measured 2026-05-06

**Railway redeploy timing measured directly (not via /gsd-* loop, just the deploy step):**

| Test | Change | Push → SUCCESS | Notes |
|---|---|---|---|
| Canary | Trailing comment on PI yaml | **183 s** (3:03) | First incremental build, some cold-cache overhead |
| YAML add | New `dryrun_test.yaml` in configs/ | **123 s** (2:03) | Cache warm; this is the realistic on-stage number |

**Implication:** the deploy step alone is ~2 min on stage. Plan accordingly:
- **/gsd-discuss-phase + /gsd-plan-phase + /gsd-execute-phase**: budget 4–6 min depending on how many discuss-phase questions you let it ask
- **`git push` → Railway deploys → audience refreshes**: 2–3 min while you bridge with architecture talk
- **Total on-stage**: 6–9 min from "OK, immigration" to "and there's the new chip"

**Time budget:** target ≤ 8 min on stage. Hard ceiling 12 min — if discuss-phase asks more than 5 questions, cut it short ("got it, plan now") and move on. Never skip plan-phase or execute-phase — those are part of the show.

**To run a dry run yourself:**
```bash
cd "/home/damienriehl/Coding Projects/alea-intake"
git checkout -b dryrun/<practice>
/gsd-discuss-phase 14   # or next free phase
# answer "add a practice area: <practice>"
/gsd-plan-phase
/gsd-execute-phase
# observe timing in your head
git checkout demo/practice-customization
git branch -D dryrun/<practice>
```

---

## Live demo command cheat-sheet

```bash
# Switch to the demo branch
cd "/home/damienriehl/Coding Projects/alea-intake" && git checkout demo/practice-customization

# Watch logs
railway logs --service alea-intake-demo

# Manual redeploy if auto-deploy hangs
TOKEN=$(python3 -c "import json; print(json.load(open('/home/damienriehl/.railway/config.json'))['user']['token'])")
curl -s -X POST https://backboard.railway.com/graphql/v2 \
  -H "Authorization: Bearer $TOKEN" -H 'content-type: application/json' \
  -d '{"query":"mutation{serviceInstanceDeployV2(serviceId:\"86f796a8-b8a7-49fa-830d-b410bbfa8937\", environmentId:\"6172ae0a-a07d-479e-887b-50e5df5c9d24\", commitSha:\"HEAD-SHA-HERE\")}"}'

# Smoke test (paste into another terminal)
curl -fsS https://alea-intake-demo-production.up.railway.app/health
curl -fsS https://alea-intake-demo-production.up.railway.app/api/practice-areas | jq '.practice_areas[].id'
```

---

## Post-talk

- [ ] Decide if `demo/practice-customization` should merge to master (the practice-area mechanism is genuinely useful beyond the demo) or stay branch-only
- [ ] Tear down the Railway demo service if no longer needed (saves spend)
- [ ] Write up what worked / what didn't into `.planning/phases/13-practice-area-customization-demo/POST-MORTEM.md`
