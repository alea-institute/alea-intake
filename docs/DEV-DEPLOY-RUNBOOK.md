# Dev Deploy Runbook — `alea-intake-dev` on Railway

The canonical **dev/test server**. It auto-deploys `master` and runs on PostgreSQL
(pgvector). Use it to smoke-test merged work in a production-like environment.

| | |
|---|---|
| **URL** | https://alea-intake-dev-production.up.railway.app |
| **Railway project** | `alea-tools` (`357ab7e1-d7cd-465e-b22b-74d6d2c4ea2e`) |
| **App service** | `alea-intake-dev` (`4c79fd77-8369-4cc3-a4ec-670b0d4f3fd1`) |
| **DB service** | `alea-intake-dev-db` — `pgvector/pgvector:pg17`, private-only |
| **Environment** | `production` (`6172ae0a-a07d-479e-887b-50e5df5c9d24`) |
| **Tracks** | GitHub `alea-institute/alea-intake` @ **`master`**, auto-deploy on push |
| **Dev test user** | `dev-smoke@example.com` / `DevSmoke123!` |

## Deploying

**Push to `master` → Railway auto-builds and deploys.** No manual step. A typical
incremental build is ~3-5 min (Docker layer cache); a cold build of the full ML stack
(torch + sentence-transformers + faiss + weasyprint) is ~15-20 min.

```bash
# typical flow: land work on master, dev deploys itself
git checkout master && git merge --ff-only <feature-branch> && git push origin master
```

Watch the deploy:
```bash
railway logs --service alea-intake-dev          # build + runtime logs
# or poll status via the GraphQL API (see "Deploy status" below)
```

## Environment variables (set on `alea-intake-dev`)

- `ALEA_DATABASE_BACKEND=postgresql`
- `ALEA_DB_HOST=alea-intake-dev-db.railway.internal`, `ALEA_DB_PORT=5432`,
  `ALEA_DB_NAME=alea_intake`, `ALEA_DB_USER=alea`, `ALEA_DB_PASSWORD=<secret>`
- `ALEA_SKIP_MIGRATIONS=true` — Alembic is not wired; `app.main` lifespan runs
  `create_all` on startup.
- `ALEA_MASTER_KEY_PATH=/app/backend/data/master.key` (auto-generated at startup)
- `ALEA_CORS_ORIGINS`, `ALEA_FRONTEND_BASE_URL`, `ALEA_OAUTH_REDIRECT_BASE_URL` →
  the public https URL. `ALEA_SECRET_KEY` set.
- Deployment mode defaults to **single-tenant** (no `ALEA_DEPLOYMENT_MODE`), so all
  tables live in the `public` schema.

## Smoke test (T+ after a deploy)

**Automated (recommended):** runs the full REST journey (auth → consent gate →
practice-area binding → validation) and reports pass/fail. Stdlib only.

```bash
python3 scripts/smoke_live.py                 # tests the dev server
python3 scripts/smoke_live.py https://other   # or any base URL
```

Manual spot-checks:

```bash
BASE=https://alea-intake-dev-production.up.railway.app
curl -fsS $BASE/health | jq '{status, db: .database.status}'          # healthy / up
curl -fsS $BASE/api/practice-areas | jq '[.practice_areas[].id]'      # ["personal_injury"]
# auth round-trip
curl -fsS -X POST $BASE/api/v1/auth/login -H 'content-type: application/json' \
  -d '{"email":"dev-smoke@example.com","password":"DevSmoke123!"}' -o /dev/null -w '%{http_code}\n'  # 200
```
Browser: log in → accept consent → **New intake** → confirm the practice-area
chip-row (`Generic` + `Personal Injury`) and that selecting **Personal Injury** swaps
the welcome copy.

## PostgreSQL gotchas (and the fixes that are in `master`)

The app was SQLite-first; running it on Postgres surfaced asyncpg strictness that
SQLite tolerated. All fixed in `backend/app/db/`:

1. **NullPool** (`engine.py`) — asyncpg connections are event-loop-bound; a pooled
   connection reused across loops raises `got Future attached to a different loop` /
   `another operation is in progress`. The Postgres engine uses `NullPool` (fresh
   connection per checkout). **Do not** re-add `pool_pre_ping`/QueuePool without
   pinning the engine to the serving loop.
2. **Single-tenant → `public`** (`session.py`) — session schema routing follows the
   deployment mode (`get_schema_translate_map`). Single-tenant maps `tenant`/`shared`
   → `None` (public), matching `create_all`. Multi-tenant uses named schemas.
3. **tz-aware timestamps** (`db/base.py`) — a Base `type_annotation_map`
   `{datetime: DateTime(timezone=True)}` makes all `Mapped[datetime]` columns
   `TIMESTAMPTZ`; the code inserts `datetime.now(timezone.utc)`.

> Note: the Phase 13 **demo** service ran on SQLite specifically to dodge these. With
> the above fixes, Postgres is the dev backend and exercises the pgvector path.

## Resetting the dev database

The dev DB is **private** (no public TCP proxy), so connect from inside Railway's
network via `railway ssh`. `create_all` only creates missing tables — if a column
type changed, drop + rebuild:

```bash
# Drop + recreate the public schema, then let the app rebuild on next start.
railway ssh --service alea-intake-dev "/app/backend/.venv/bin/python - <<'PY'
import asyncio
from sqlalchemy import text
from app.db.engine import get_engine, dispose_engine
async def m():
    e = get_engine()
    async with e.begin() as c:
        await c.execute(text('DROP SCHEMA public CASCADE'))
        await c.execute(text('CREATE SCHEMA public'))
        await c.execute(text('CREATE EXTENSION IF NOT EXISTS vector'))
    await dispose_engine()
asyncio.run(m())
PY"
# then restart/redeploy the service so the lifespan create_all rebuilds tables
```

## Deploy status (GraphQL)

```bash
TOKEN=$(python3 -c "import json,os;print(json.load(open(os.path.expanduser('~/.railway/config.json')))['user']['token'])")
curl -s -X POST https://backboard.railway.com/graphql/v2 \
  -H "Authorization: Bearer $TOKEN" -H 'content-type: application/json' \
  -d '{"query":"query{deployments(first:1,input:{projectId:\"357ab7e1-d7cd-465e-b22b-74d6d2c4ea2e\",environmentId:\"6172ae0a-a07d-479e-887b-50e5df5c9d24\",serviceId:\"4c79fd77-8369-4cc3-a4ec-670b0d4f3fd1\"}){edges{node{status meta}}}}"}'
```

## Remote CLI auth (when traveling / no local browser)

`railway login` needs a TTY. In a non-TTY/remote shell, wrap it:
`script -qfc "railway login --browserless" /tmp/pair.log`, then open the printed
`railway.com/cli-login?...` URL on any device and confirm the pairing code. For fully
non-interactive use, set a project token: `RAILWAY_TOKEN=<token>`.
