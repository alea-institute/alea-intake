# Deferred Items — Phase 14

Out-of-scope discoveries logged during execution (not fixed; see scope boundary).

## From plan 14-01 (Task 3 ruff check)

Pre-existing ruff `F841` lint errors in `backend/app/services/analysis/orchestrator.py`,
unrelated to the 14-01 changes (confirmed present on the pre-edit `HEAD~2` version):

- `resume()` ~line 182: local variable `session_id` assigned but never used.
- `_evaluate_convergence()` ~line 609/611: local variable `current_avg` assigned but never used.

These are in methods 14-01 did not modify (`_run_parallel_jurisdictions` was the only
behavioral edit). Left untouched per the executor scope boundary. Safe to clean up in a
future housekeeping pass.
