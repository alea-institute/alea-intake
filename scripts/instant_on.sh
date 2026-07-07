#!/usr/bin/env bash
# Instant-on 3-persona validation — one command to run the moment the dev LLM key lands.
#
# Prerequisite (human, ~1 min — see INSTANT-ON-RUNBOOK.md): set the LLM key + a cheap
# model on alea-intake-dev and let it redeploy. Then run THIS from the repo root:
#
#     scripts/instant_on.sh
#     ALEA_SMOKE_BASE=https://<other-host> scripts/instant_on.sh   # override target
#
# It (1) preflights /health, (2) drives all 3 personas end-to-end (register -> consent
# -> intake -> narrative -> PDF upload -> analyze -> memo -> export), (3) hard-checks
# BUG-3 (LLM actually extracting facts now), (4) runs the deterministic FOLIO IRI oracle
# (folio_check.py, RUB-INTAKE-05), and (5) prints a per-persona summary vs ANSWER-KEYS.
# Exit codes: 0 all good; 2 preflight failed; 3 LLM still returning 0 facts (BUG-3);
# 4 a FOLIO IRI failed to resolve. Rubric judging + evidence pack are the next step.
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$REPO/backend/.venv/bin/python"
BASE="${ALEA_SMOKE_BASE:-https://alea-intake-dev-production.up.railway.app}"
PERSONA_ROOT="$REPO/docs/evidence/persona-campaign/personas"
RUNS="$REPO/docs/evidence/persona-campaign/runs"
PERSONAS=(landlord-tenant immigration family-custody)

export ALEA_SMOKE_BASE="$BASE"
echo "======================================================================"
echo "  INSTANT-ON persona validation  ->  $BASE"
echo "======================================================================"

# --- 1. Preflight -----------------------------------------------------------
echo; echo "[1/4] Preflight health check (smoke_live.py) ..."
if ! "$PY" "$REPO/scripts/smoke_live.py" "$BASE"; then
  echo "!! Preflight FAILED — the dev server is not healthy. Fix the deploy first." >&2
  exit 2
fi

# --- 2. Drive all three personas -------------------------------------------
echo; echo "[2/4] Running 3 personas end-to-end ..."
for p in "${PERSONAS[@]}"; do
  echo "  --- $p ---"
  "$PY" "$REPO/scripts/persona_run.py" "$PERSONA_ROOT/$p" "$BASE" || \
    echo "  (persona_run exited non-zero for $p — inspecting run.json below)"
done

# --- 3. BUG-3 gate: is the LLM actually extracting? -------------------------
echo; echo "[3/4] BUG-3 gate — confirming the LLM produced claims ..."
TOTAL_CLAIMS=$("$PY" - "$RUNS" "${PERSONAS[@]}" <<'PYEOF'
import json, sys
from pathlib import Path
runs = Path(sys.argv[1]); total = 0
for name in sys.argv[2:]:
    p = runs / name / "run.json"
    if not p.exists():
        print(f"  {name}: NO run.json", file=sys.stderr); continue
    a = (json.loads(p.read_text()).get("analysis") or {})
    n = len(a.get("claims") or [])
    total += n
    print(f"  {name}: claims={n} gaps={len(a.get('gaps') or [])} "
          f"questions={len(a.get('questions') or [])}", file=sys.stderr)
print(total)
PYEOF
)
echo "  total claims across personas: ${TOTAL_CLAIMS:-0}"
if [ "${TOTAL_CLAIMS:-0}" -eq 0 ]; then
  echo "!! BUG-3 STILL PRESENT: 0 facts/claims extracted across all personas." >&2
  echo "   The dev LLM key/model is not functional — extraction silently returns []." >&2
  echo "   Verify the ALEA_* LLM key + model on alea-intake-dev, redeploy, rerun." >&2
  exit 3
fi

# --- 4. Deterministic FOLIO IRI oracle -------------------------------------
echo; echo "[4/4] Deterministic FOLIO IRI check (folio_check.py, RUB-INTAKE-05) ..."
if ! "$PY" "$REPO/scripts/folio_check.py" --all; then
  echo "!! One or more mapped FOLIO IRIs failed to resolve/root — see rows above." >&2
  echo "   (Personas ran and extracted; this is a mapping-quality FAIL, not a deploy issue.)" >&2
  exit 4
fi

echo
echo "======================================================================"
echo "  ✅ Personas ran, LLM extracted claims, all FOLIO IRIs resolve."
echo "  NEXT (agent): judge each run vs the LOCKED rubric (intake-quality v1.1)"
echo "  + the hidden ANSWER-KEYS oracle, then build the evidence pack."
echo "    keys:   docs/evidence/persona-campaign/personas/ANSWER-KEYS.md"
echo "    rubric: docs/rubrics/intake-quality-v1.md"
echo "    pack:   docs/evidence/persona-campaign/pack.html"
echo "======================================================================"
