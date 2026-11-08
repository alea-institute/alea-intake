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
The entrypoint enables Uvicorn proxy headers. Set `ALEA_FORWARDED_ALLOW_IPS` to
the Coolify proxy network address or CIDR so only that proxy supplies the forwarded
scheme; never set it to `*`. Keep a single uvicorn worker: guest erase and socket
writes share an in-process lock. Configure forwarded scheme trust before rollout,
and verify that the cookie has Secure set through the public HTTPS domain.
Configure the proxy to omit query strings, Authorization, Cookie and preview/key
headers from access logs; never retain the preview link in logs or evidence.
Application access logging is disabled in showcase mode.

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
