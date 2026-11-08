#!/bin/sh
set -e

# Run Alembic migrations unless explicitly skipped
if [ "$ALEA_SKIP_MIGRATIONS" != "true" ]; then
  echo "Running database migrations..."
  cd /app/backend && uv run alembic upgrade head || echo "Migration skipped (may not be configured)"
fi

# Report the build revision before starting the application
echo "Starting ALEA Intake (commit: ${GIT_COMMIT_SHA:-unknown})"

# Start the application
exec uv run uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
