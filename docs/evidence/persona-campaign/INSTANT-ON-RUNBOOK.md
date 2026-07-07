# Instant-On Validation Runbook — alea-intake persona UAT

The persona campaign is **code-complete and deployed** (BUG-1 extraction wiring,
BUG-2 conversation LLM, RUB-10 plain-language, deadline engine — all on `master`,
deployed to `alea-intake-dev`). The **only** thing blocking the 3-persona live
retest is **BUG-3**: the dev server's LLM provider is non-functional (key
missing/invalid), so `extract_facts` silently returns `[]`.

This runbook makes the retest **one command** the moment the key lands.

---

## Step 0 — Human prerequisite (~1 min): give the dev server a working LLM key

Requires Railway access (the CLI was de-authed — re-auth or use a project token):

```bash
# Re-auth the Railway CLI (browserless pairing) …
script -qfc "railway login --browserless" /tmp/pair.log   # open the printed URL, confirm
# … OR export a project token:  export RAILWAY_TOKEN=…

# Point the dev service at a working, CHEAP model (policy 5 — don't burn gpt-4 in a dev loop):
railway variables --service alea-intake-dev \
  --set "ALEA_LLM_API_KEY=<openai-or-anthropic-key>" \
  --set "ALEA_LLM_PROVIDER=openai" \
  --set "ALEA_LLM_MODEL=gpt-4o-mini"        # or anthropic + claude-haiku
railway redeploy --service alea-intake-dev  # fast restart; wait for /health healthy
```

> Exact env var names: confirm against `backend/app/services/llm_service.py` /
> `app/config.py` (`ALEA_*` prefix). `/health` reports `llm_provider: "configured"`
> as a **hardcoded string** — it does NOT prove a live key. The real proof is
> Step 1 below extracting > 0 facts.

## Step 1 — The one command (agent, from repo root)

```bash
scripts/instant_on.sh
# or against a different host:
ALEA_SMOKE_BASE=https://<host> scripts/instant_on.sh
```

It runs, in order:

1. **Preflight** — `smoke_live.py` (`/health` healthy + db up). Exit **2** on failure.
2. **3 personas end-to-end** — `persona_run.py` for `landlord-tenant`, `immigration`,
   `family-custody` (register → consent → intake → WS narrative → PDF upload →
   analyze → results → memo → export). Writes `runs/<persona>/run.json`.
3. **BUG-3 gate** — sums `claims` across the three runs. If **0**, prints the
   "BUG-3 still present" diagnosis and exits **3** (the LLM key is still wrong).
4. **Deterministic FOLIO oracle** — `folio_check.py --all` (RUB-INTAKE-05):
   every mapped `folio_iri` must resolve, be non-deprecated, and be well-rooted.
   Exit **4** if any IRI fails.

Exit **0** = personas ran, the LLM extracted claims, and every FOLIO IRI is valid.

## Step 2 — Judge + evidence pack (agent, after a clean Step 1)

Not scripted — this is the judgment pass (gestalt lane 2):

- Score each `runs/<persona>/run.json` against the **locked rubric**
  `docs/rubrics/intake-quality-v1.md` (v1.1 — deadlines required/50-state,
  ~6th-grade reading level, en/es/zh, GATE blockers 01/04/05/08/09/15) **and** the
  hidden `personas/ANSWER-KEYS.md` oracle (expected issues incl. unspoken GATE
  issues, computed deadlines, FOLIO concepts, gap questions).
- Deterministic sidecar checks: export integrity (RUB-15), i18n/plain-language
  (RUB-10), deadline computation vs the answer key (RUB-08/09).
- Emit the evidence pack `pack.html` + `manifest.json` (portfolio template),
  one finding per decision, ID-addressable for Damien's review.
- Iterate personas → expand toward 8–10 for the final pass (policy 5: cheap model,
  synthetic items while iterating).

---

## Why this is safe to run repeatedly

`persona_run.py` registers a fresh throwaway account per run and is idempotent at
the campaign level; `folio_check.py` is read-only and deterministic (near-zero
token cost). The only app-side spend is the LLM extraction/memo calls for 3
personas on a **cheap** model — a few cents. Full 8–10 persona pass only after the
3-persona pass reads clean against the rubric.
