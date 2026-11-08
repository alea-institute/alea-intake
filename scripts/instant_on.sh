#!/usr/bin/env bash
# One campaign, all eight personas, on one deployed commit. No server LLM key.
# Supply PERSONA_LLM_API_KEY, ALEA_SMOKE_BASE, and the preview header credential.
# Optional PERSONA_TOKEN_RATES JSON maps model IDs to USD/million [input, output].
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec "$REPO/backend/.venv/bin/python" "$REPO/scripts/persona_run.py" "$@"
