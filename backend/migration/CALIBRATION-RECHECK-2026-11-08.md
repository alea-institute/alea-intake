# Calibration recheck — 2026-11-08

The offline sweep on locked **folio-resolve 0.2.0** supports adopting penalty **0.85**,
threshold **0.55**, and the **floor** combine rule. Results reproduce the July study on
0.1.0; there is no material contradiction.

Run from `backend/` (also replayed against the original resolver and sweep from the
verified base commit, without editing production files):

```bash
PYTHONHASHSEED=0 PYTHONPATH=.:/tmp/alea-u1-verification "/home/damienriehl/Coding Projects/alea-intake/backend/.venv/bin/python" migration/sweep.py --no-spec-axis --out /tmp/alea-calibration-recheck-current
```

No network, database, ontology download, or LLM calls. The optional specificity axis was
excluded because it requires a newer library. Reconstruction fidelity and the claim-fitness
canary passed. A separate evaluation of 0.85 / 0.55 with `rule="floor"` produced:

| Operating point | Mode | TP | FP | FN | Precision | Recall | F1 | Accepted (including 6 ambiguous) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 0.70 / 0.50, weighted average | Healthy | 20 | 10 | 13 | 0.6667 | 0.6061 | 0.6349 | 36 |
| 0.70 / 0.50, weighted average | Degraded | 18 | 5 | 15 | 0.7826 | 0.5455 | 0.6429 | 29 |
| 0.85 / 0.55, floor | Healthy | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 32 |
| 0.85 / 0.55, floor | Degraded | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 32 |

Mean F1 improves **0.6389 → 0.6780**. All canaries remain green. As in the original study,
0.60 / 0.40 has the highest raw grid mean F1 (0.6862), but re-admits the known place-trap
false positive. The recommended point still meets the study's precision/recall tradeoff.

The predicted acceptance changes are unchanged:

- Healthy: remove Premises Liability and Wrongful Termination Claim from each of
  `n-exact-label` and `n-word-order-2` (four false positives).
- Degraded: add Fair Debt Collection Practices Act to `n-expansion-debt` and Breach of
  Warranty of Habitability to `n-homonym-habitability` (two true positives), plus Retaliation
  Claim to `n-word-order-2` (one false positive).
- Floor versus weighted average at the adopted point: **zero acceptance or ranking changes**.
  The separate weak-hit reproduction exercises the defect this corpus does not expose.

Sandbox verification used a temporary Python startup hook to redirect the imported library's
log to `/tmp` and poll the asyncio selector: the sandbox blocks its cross-thread wakeup
socket. The hook changes neither scoring nor retrieval and is removed from the delivered diff.
The baseline and adopted sweep JSON captures are identical. The sweep's historical
`current` arm now explicitly preserves the old weighted average;
fidelity checks compare the floor reconstruction with the adopted production resolver.

Verification after adoption: the focused resolver, sweep, and library-boundary suite passed
**63 tests**. Existing tests inspected: `test_concept_resolver.py`,
`test_migration_sweep.py`, and `test_folio_resolve_pin.py`. Added scenarios cover the 0.80
single-stage signal, weaker corroboration, the environment override, and the predicted
healthy/degraded golden concept sets.

The implementation and tests were already present when this verification session began.
The existing test-first receipts were inspected, and seven new scenario cases were replayed
against the original resolver loaded in memory from the base commit: **7 failed, 29 deselected**.
For example, `test_weak_corroboration_floors_at_best_penalized_signal[0.1-0.8-None]`
failed with `0.45000000000000007 == 0.68 ± 6.8e-07`; the environment-override case
failed with `assert 1 == 0`. This replay did not modify production files.

Commands from `backend/` used `PYTHONHASHSEED=0`,
`PYTHONPATH=.:/tmp/alea-u1-verification`, `HF_HUB_OFFLINE=1`, and
`TRANSFORMERS_OFFLINE=1`, with the specified shared-venv interpreter:

```bash
"/home/damienriehl/Coding Projects/alea-intake/backend/.venv/bin/python" -m pytest tests/test_concept_resolver.py tests/test_migration_sweep.py tests/test_folio_resolve_pin.py -q -p no:cacheprovider
"/home/damienriehl/Coding Projects/alea-intake/backend/.venv/bin/python" -m pytest tests/ -q -p no:cacheprovider
```

The ordinary full-suite command stops at **1 collection error**:
`tests/test_document_intake.py` cannot import `pymupdf`. The current shared venv has
folio-resolve 0.2.0 but lacks PyMuPDF, despite its existing declaration in `pyproject.toml`.
No packages were installed and no dependency files were changed.

Running the same full-suite command with `--continue-on-collection-errors` finished with
**1268 passed, 3 skipped, 8 failed, 1 collection error** (57.78 seconds). All eight
failures also report missing `pymupdf`. The calibration suite is green; full-suite
acceptance remains blocked on restoring the already-declared package in the shared venv.
`git diff --check` passed. No additional mechanisms were built.
