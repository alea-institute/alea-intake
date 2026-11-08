# Dev deployment: Coolify on hetzner-dev

The existing Coolify application `alea-intake` auto-deploys GitHub `master` on
`hetzner-dev`. Its HTTPS domains are `alea-intake.dev.openlegalstandard.org` and
`intake.dev.openlegalstandard.org`. Use the Coolify GitHub App integration; keep
one build at a time and use its deployment logs to check the rollout.

## Build and runtime configuration

Build the repository Dockerfile with `VITE_SHOWCASE_MODE=true` and
`SOURCE_COMMIT` set to the deployed Git commit. The image maps this to
`GIT_COMMIT_SHA`, which `/health` reports as `commit`.

Configure these runtime environment variables through Coolify's secret settings.
This document contains names only for private configuration:

- `ALEA_SHOWCASE_MODE=true`
- `ALEA_DATABASE_BACKEND=postgresql`
- `ALEA_DB_HOST`, `ALEA_DB_PORT`, `ALEA_DB_NAME`, `ALEA_DB_USER`, `ALEA_DB_PASSWORD`
- `ALEA_SECRET_KEY`
- `ALEA_FORWARDED_ALLOW_IPS` (the Coolify proxy network address or CIDR; never `*`;
  defaults to `127.0.0.1` for a local proxy)
- `ALEA_REFERENCE_MODEL`
- `ALEA_SHOWCASE_IDLE_TTL_SECONDS`
- `ALEA_PREVIEW_PASSPHRASE` (non-empty until launch)
- **Showcase analysis budget** (showcase mode only; authenticated deployments
  keep 10 iterations, one fact_map + gap_analyze round per jurisdiction, and
  their current prompts). Defaults target a guest run in about 3 minutes and
  about $0.75 on `claude-sonnet-5-5`, about 8 analysis LLM calls for a 50-fact
  intake (1 issue_spot, 2 exploration, 3 fact_map batches run concurrently with
  1 procedural-gap call, 1 question_gen), plus up to 2 semantic-fit calls when
  FOLIO resolves claim concepts:
  - `ALEA_SHOWCASE_MAX_ITERATIONS` (default `1`) caps orchestrator iterations;
    a capped run ends as `max_iterations`, which the showcase page accepts.
  - `ALEA_SHOWCASE_ANALYSIS_ROUNDS` (default `1`) caps fact_map + gap_analyze
    rounds per iteration. Each round maps every fact to every claim, so a
    three-jurisdiction run otherwise repeats the same work three times.
  - `ALEA_SHOWCASE_EXPLORATION_MAX_ROUNDS` (default `1`) caps exploration rounds.
  - Output caps: `ALEA_SHOWCASE_MAX_CLAIMS` (`8`, total; issue_spot asks for
    6 and leaves 2 for exploration), `ALEA_SHOWCASE_MAX_GAPS` (`8` LLM
    procedural gaps), `ALEA_SHOWCASE_MAX_QUESTIONS` (`8`),
    `ALEA_SHOWCASE_MAX_MAPPINGS_PER_FACT` (`2`),
    `ALEA_SHOWCASE_MAX_FACTS_PER_EXTRACTION` (`20`) and
    `ALEA_SHOWCASE_RATIONALE_WORDS` (`12`).
- `ALEA_ANTHROPIC_JSON_EFFORT` (`low|medium|high|xhigh|max|none`; empty
  default means `low` in showcase mode and unset elsewhere) sends
  `output_config.effort` on Anthropic structured (JSON) calls only; chat
  replies keep the model default. `none` sends nothing. The pinned
  alea-llm-client accepts only `low|medium|high|max` and rejects `xhigh`
  before sending, so do not set `xhigh` until the client allows it.
- The other wall-time knobs
  are `ALEA_SHOWCASE_CONCURRENT_ANALYSES` and `ALEA_SHOWCASE_ANALYSIS_QUEUE`
  (bounded analysis slots) and `ALEA_SHOWCASE_EXTRACTION_TIMEOUT_SECONDS`
  (document text extraction). Each LLM call in analysis is also bounded in code:
  inputs are batched, list lengths are capped, client retries are off, and a
  failed call retries once with a compact request before it degrades to an
  empty result (`backend/app/services/llm_bounds.py`).

Do not configure a server-side LLM API key; visitors supply their own key.
Use the dedicated showcase database and restricted role. Apply
`scripts/showcase_db_setup.sql` using `psql` as the existing PostgreSQL instance
administrator, then configure the role's authentication through the deployment's
secret mechanism. Exclude this database from backups. Do not change other apps'
database permissions. Session end purges the session graph and files; the idle
sweeper uses `ALEA_SHOWCASE_IDLE_TTL_SECONDS` for abandoned sessions.

Set the Coolify healthcheck path to `/health`, start period to **30 seconds**,
interval to **10 seconds**, and retries to **15**. Set an explicit container
memory limit within the host's available budget before deployment; check peak
startup use and leave memory for the other services. After rollout, inspect
`docker ps` health and free memory on hetzner-dev to confirm other apps remain
healthy. Do not add a second deployment GitHub Action.

## Preview access and verification

The app's preview gate protects pages, assets, APIs and WebSocket upgrades.
Only `GET /health` is anonymous while the gate is enabled. Share preview access
privately: opening `/__preview?key=` with the configured passphrase sets an
HttpOnly, SameSite=Lax cookie (Secure over HTTPS) and redirects to `/`. The cookie
contains an HMAC signed with `ALEA_SECRET_KEY`, never the passphrase itself.
`ALEA_PREVIEW_COOKIE_DAYS` sets the cookie's lifetime (default 30; 0 makes it a
browser-session cookie).

The entrypoint enables Uvicorn proxy headers. Set `ALEA_FORWARDED_ALLOW_IPS` to
the Coolify proxy network address or CIDR so only that proxy supplies the forwarded
scheme; never set it to `*`. Keep a single uvicorn worker: guest erase and socket
writes share an in-process lock. Configure forwarded scheme trust before rollout,
and verify that the cookie has Secure set through the public HTTPS domain.
Configure the proxy to omit query strings, Authorization, Cookie and preview/key
headers from access logs; never retain the preview link in logs or evidence.
Application access logging is disabled in showcase mode.

### Cloudflare Access (owner sign-in without the passphrase)

A Cloudflare Access hostname in front of the app can admit the owner by email
one-time PIN. Access adds a signed `Cf-Access-Jwt-Assertion` header to every
proxied request, WebSocket upgrades included, and the gate accepts a valid token
in place of the passphrase. Set:

- `ALEA_CF_ACCESS_TEAM_DOMAIN`: the Zero Trust team domain
  (`<team>.cloudflareaccess.com`, no scheme).
- `ALEA_CF_ACCESS_AUD`: the Access application's Application Audience (AUD) tag.
- `ALEA_CF_ACCESS_EMAILS` (optional): comma-separated email allowlist. Empty
  accepts any identity the Access policy admits.

The token path turns on only when both the team domain and AUD are set, and only
while `ALEA_PREVIEW_PASSPHRASE` keeps the gate enabled. The app verifies RS256
signatures against `https://<team-domain>/cdn-cgi/access/certs` (cached for one
hour; an unknown key id forces at most one refetch per minute) and checks `aud`,
`iss`, `exp` and `iat`. A request that bypasses Cloudflare cannot forge a token,
and a refused or unverifiable token falls back to the passphrase check (401, or
WebSocket close 1008). Set the Access session duration in the Access application;
the app sets no cookie for token requests. Omit `Cf-Access-Jwt-Assertion` from
proxy access logs as well.

The harness sends `X-Preview-Key` from `PERSONA_PREVIEW_KEY`. The live probe reads
only `VERIFY_PREVIEW_KEY`; load it privately into the process environment, then run:

```bash
scripts/verify-showcase.sh https://intake.dev.openlegalstandard.org --mode gated --commit <deployed-commit>
```

Repeat for the other domain. The probe prints one pass/fail line per check,
checks the commit, guest consent and creation, missing LLM key rejection,
cross-guest isolation, and loss of access after session end. It requires only
curl and python3. It does not call an LLM or print credentials. Its HTTP checks
prove resources are inaccessible after purge; the backend retention tests prove
zero remaining graph rows and uploaded files.

## Lift the access gate

After launch acceptance, remove or empty `ALEA_PREVIEW_PASSPHRASE` in Coolify and
redeploy. No proxy Basic authentication is used: guest authentication needs the
Authorization header. Unsetting the variable makes the app public, including
WebSocket upgrades. Run without preview credentials:

```bash
scripts/verify-showcase.sh https://intake.dev.openlegalstandard.org --mode public --commit <deployed-commit>
```

Repeat for both domains and complete anonymous narrative and curated-example
journeys in a real browser. To restore preview access, set the passphrase and
redeploy. Changing it or `ALEA_SECRET_KEY` invalidates existing preview cookies.

## Shipping an image built off the deploy box (2026-11-08)

Never build images on hetzner-dev. Build on the home box, then ship and restart:

1. `docker build --build-arg SOURCE_COMMIT=<sha> --build-arg VITE_SHOWCASE_MODE=true -t <app-uuid>:<sha> .`
2. `docker save <app-uuid>:<sha> | gzip -1 | ssh hetzner-dev 'gunzip | docker load'`
3. Point the Coolify app at that commit (`git_commit_sha`), then use the Coolify **restart**
   action, which recreates the container from the existing `<app-uuid>:<sha>` tag.

Known trap: a Coolify **deploy** rebuilds on the box even when the image exists, because any
environment or commit change counts as a build-impacting change. That build does not pass
`VITE_SHOWCASE_MODE`, so the site serves the standard sign-in page instead of the showcase.
If a deploy ran anyway, re-run step 2 (which retags the correct image) and restart. Check the
served bundle: the page at `/` must show the showcase, and `/health` must report `<sha>`.

PR preview deployments are disabled for this app, and auto-deploy is paused while the app is
pinned to the PR1 branch for the showcase demo. Re-enable auto-deploy and repoint to `master`
when PR1 merges.

The Cloudflare Access hostname `intake.damienriehl.com` (twin tunnel, Damien-only one-time PIN)
reaches the same app; the preview gate trusts its Access JWT (settings above).
