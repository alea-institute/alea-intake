#!/bin/sh
set -e

# Run Alembic migrations unless explicitly skipped
if [ "$ALEA_SKIP_MIGRATIONS" != "true" ]; then
  echo "Running database migrations..."
  cd /app/backend && uv run alembic upgrade head || echo "Migration skipped (may not be configured)"
fi

# Start the application
exec uv run uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
