#!/bin/sh
set -e

# Run Alembic migrations unless explicitly skipped
if [ "$ALEA_SKIP_MIGRATIONS" != "true" ]; then
  echo "Running database migrations..."
  cd /app/backend && uv run alembic upgrade head || echo "Migration skipped (may not be configured)"
fi

echo "Starting ALEA Intake (commit: ${GIT_COMMIT_SHA:-unknown})"

# Showcase URLs may contain visitor secrets; never log their request lines.
case "${ALEA_SHOWCASE_MODE:-false}" in
  1|[Tt]|[Tt][Rr][Uu][Ee]|[Yy]|[Yy][Ee][Ss]|[Oo][Nn]) set -- --no-access-log ;;
  *) set -- ;;
esac
exec uv run uvicorn app.main:app "$@" --host 0.0.0.0 --port "${PORT:-8000}"
