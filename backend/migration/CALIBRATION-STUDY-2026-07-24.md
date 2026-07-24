# Operating-point calibration — evidence and recommendation (2026-07-24)

**This is a study. It changes nothing.** No file under `app/` was edited, no threshold moved, no
dependency pin touched. It exists so the adoption decision recorded in
[`README.md`](README.md) ("a calibration pass over that trio is a good follow-up operation") can
be made on numbers instead of intuition.

- Tools: [`sweep.py`](sweep.py) (the grid), [`combine_lab.py`](combine_lab.py) (the averaging oddity), [`sweep_gold.json`](sweep_gold.json) (concept-level labels).
- Raw output: [`captures/sweep.json`](captures/sweep.json), [`captures/sweep-tables.md`](captures/sweep-tables.md), [`captures/combine-lab.md`](captures/combine-lab.md).
- Guards: [`../tests/test_migration_sweep.py`](../tests/test_migration_sweep.py) — 15 tests of the harness, including the fidelity proof and a "the study changed nothing" assertion.
- Cost: $0. Same rules as the migration harness — `PYTHONHASHSEED=0`, no LLM, no network, no database, no ontology download. Full sweep runs in ~3 seconds.

---

## TL;DR

- The two knobs are **not independent**. The accept test factorizes into a **corroborated bar** (`threshold`, for candidates two stages found) and a **solo bar** (`threshold / penalty`, for candidates one stage found). Every degraded-mode number in the sweep is a function of the ratio alone.
- The production point sets the solo bar at **0.714**, which is *above* the score the library gives alea's dominant matching shape (short claim name → long FOLIO label = 0.675), and only **0.022** below the cliff at which a whole narrative resolves to nothing with embeddings down.
- **Recommended: `SINGLE_STAGE_PENALTY` 0.7 → 0.85, `confidence_threshold` 0.50 → 0.55.** Corroborated bar up (kills a junk cluster the migration itself created), solo bar down 0.714 → 0.647 (restores both rows on the delta report's watch list). Measured: precision 0.667 → 0.769 healthy, F1 0.635 → 0.678 healthy and 0.643 → 0.678 degraded, 4 concepts dropped (all wrong), 3 added (2 right), canaries green with 4× the margin. **Confidence: medium-high on the direction, medium on the exact numbers.**
- **Do not touch `specificity_penalty`** (folio-resolve ≥ 0.3.0's new knob). Damping it lifts the good short-name case and the junk one-shared-word case *together*; the bars can separate them, precisely because the specificity penalty is what pushed them apart in the first place. Measured worse at every threshold.
- The averaging oddity is **real, provable, and reproducible end to end** — but at either operating point it is worth **zero** on this corpus. The `floor` remedy is free (identical outputs here) and buys monotonicity; the obvious generalization (`coverage`) does *not* fix it; the textbook fix (`presence`) fixes it and rescales every confidence in the system.
- **The biggest lever is not the operating point.** With query expansion off, precision is **1.000** in both modes at both points: 100% of the false positives on this corpus are manufactured by alea's own lay-language expansion vocabulary (`"claim"` → `"insurance claim"`, `"warranty"` → `"consumer protection"`, `"rent"` → `"housing"`). That is a separate operation and out of scope here.

---

## 1. Method

### What is measured

`sweep.py` builds the candidate pool **once per (specificity, embedding-mode) pair** by running
the real `_stage_embedding` and `_stage_label_prefix`, then evaluates every grid point over that
pool with the real `_combine_score`. Neither knob can change what the stages retrieve or score —
both are consumed strictly downstream in `_combine_and_rank` — so this is a reconstruction, not
an approximation.

`verify_reference()` proves it: at the production point the reconstruction must reproduce
`resolve_concepts` exactly, per narrative, in both embedding modes. It does
(`test_reconstruction_equals_the_real_resolver`), and the reference point also reproduces the
signed-off migration capture row for row (`test_reference_matches_the_signed_off_migration_capture`).

The knobs are swept **in-process**: `SINGLE_STAGE_PENALTY` by setting the module attribute inside
a `try/finally`, `confidence_threshold` through `ConceptResolutionConfig`, `specificity_penalty`
by wrapping the scorer at the resolver's call site. `test_sweeping_restores_every_patched_attribute`
asserts no residue.

### Grid

| axis | values |
|---|---|
| `SINGLE_STAGE_PENALTY` | 0.5, 0.6, **0.7**, 0.8, 0.9, 1.0 — plus a refinement pass at 0.75 / 0.80 / 0.85 / 0.90 |
| `confidence_threshold` | 0.35, 0.40, 0.45, **0.50**, 0.55, 0.60 — plus 0.525 / 0.575 in the refinement pass |
| `specificity_penalty` | 0.0, 0.3, 0.5, 0.7, **1.0** — separate axis, run at penalty 0.7 and 0.85 |
| combine rule | **current**, floor, presence, coverage (§5) |

**The specificity axis was available.** The pinned wheel (folio-resolve 0.1.0) has no
`specificity_penalty` parameter, but the committed pin is `folio-resolve>=0.1.0`, which already
permits the sibling checkout's v0.3.0. The sweep reads it in a **child process** with
`PYTHONPATH` set, leaving the parent — and therefore the whole main grid and the fidelity check —
on exactly what production imports. Nothing was installed and no pin moved. The axis carries its
own confound guard: at `specificity_penalty=1.0` the v0.3.0 scorer must reproduce the pinned
wheel **bit-identically** on the corpus, or the axis would be measuring a version difference
rather than the knob. It does (`bit_identical_at_1.0: true`).

### The gold labels

Precision and recall need concept-level judgments the migration corpus does not carry —
`corpus.json` is hashed into every capture and must not move, so the study's labels live in
`sweep_gold.json`. The rubric is **closed world**: the mini-ontology is 41 hand-written nodes, so
each narrative's correct mappings can be enumerated; `good` lists them, `ambiguous` holds the
judgment calls (excluded from both precision and recall), and everything else that gets accepted
counts as a false positive — including branch roots and the sandbox placeholder.

### Limitations — read these before acting on the numbers

- **26 synthetic narratives, 41 synthetic concepts.** The corpus was built to exercise the *migration*, not to be a representative intake sample. Everything below describes shapes, not rates.
- **33 labeled gold items per mode.** One decision moves F1 by roughly ±0.02. Differences below ~0.04 are not signal. This is why the recommendation is argued from *counted* flips (4 dropped, 3 added, each named) rather than from an F1 ranking.
- **The labels are one engineer's judgment.** Contested calls were routed to `ambiguous` rather than decided, but a different reviewer would move some rows.
- **The embedding stand-in is generous.** Binary-term cosine retrieves anything with a shared token; a real sentence-transformers backend with `top_k=20` truncation produces more weak-retrieval cases, which matters in §5.
- **The best grid point by mean F1 is not the recommendation.** `(0.6, 0.4)` scores 0.686; it gets there by lowering both bars, which re-admits the `place_trap` row the corpus exists to catch. Chasing the metric here would be overfitting to 26 narratives.

---

## 2. Finding: the two knobs are one bar and a ratio

`_combine_score` gives a candidate found by **one** stage `penalty × score`, and a candidate found
by **two** stages their mean (the weights are equal, 0.3 / 0.3). So the accept test is:

```
one stage:   score ≥ threshold / penalty      <- the SOLO BAR
two stages:  mean(stages) ≥ threshold         <- the CORROBORATED BAR
```

Consequences, all confirmed in `captures/sweep.json`:

- With embeddings **down**, every candidate is solo, so **degraded-mode behavior depends only on the ratio `t/p`** — six penalty values × six thresholds collapse to 31 distinct ratios, and every metric is a pure function of the ratio. (`sweep.py` prints no ratio mismatches.)
- With embeddings **healthy**, most candidates are corroborated, so healthy behavior tracks `threshold` almost alone: the healthy F1 row is *identical* for penalties 0.5 → 0.8 and moves only at 0.9 / 1.0, where the solo bar drops far enough to admit new solo candidates.
- Therefore **retuning one knob silently retunes the degraded operating point.** Lowering the penalty to "be less punitive" *raises* the solo bar and makes degraded mode stricter — the opposite of the intent. This is the single most useful thing the sweep found.

Mean F1 over the coarse grid (⚠ = a canary fails at that point):

| penalty \ threshold | 0.35 | 0.40 | 0.45 | 0.50 | 0.55 | 0.60 |
|---|---|---|---|---|---|---|
| **0.5** | 0.6448 | 0.5813 ⚠ | 0.5199 ⚠ | 0.3175 ⚠ | 0.339 ⚠ | 0.3276 ⚠ |
| **0.6** | 0.6415 | 0.6862 | 0.6321 ⚠ | 0.5515 ⚠ | 0.5208 ⚠ | 0.3276 ⚠ |
| **0.7** | 0.6415 | 0.6597 | 0.6505 | **0.6389** | 0.6331 ⚠ | 0.5616 ⚠ |
| **0.8** | 0.6811 | 0.6597 | 0.6505 | 0.63 | 0.6666 | 0.6217 ⚠ |
| **0.9** | 0.6685 | 0.6597 | 0.6505 | 0.63 | 0.6515 | 0.6666 |
| **1.0** | 0.6637 | 0.6855 | 0.6505 | 0.63 | 0.6515 | 0.6401 |

Bold = the production point. The full set of tables (precision, recall, per-mode F1, flip counts)
is in `captures/sweep-tables.md`.

---

## 3. Finding: both bars sit on the wrong side of a narrow window

Because the test factorizes, each bar can be audited as an ordered list of the decisions it
makes. These are the corpus's candidates around the production bars, tagged with the gold
judgment (full lists in `captures/sweep-tables.md`).

**Solo bar — production `0.5 / 0.7 = 0.714`:**

| score | verdict | example |
|---|---|---|
| 0.797 | good ×4 | "I was fired…" → *Wrongful Termination Claim* |
| 0.736 | good ×3, bad ×2 | "Arbitration" → *Arbitration Rules* / "rent" → *Housing Authority* |
| **0.714** | ← **production bar** | |
| 0.704 | bad | "claim for breach of contract" → *Retaliation Claim* |
| 0.699 | **good** | "a collector keeps calling…" → *Fair Debt Collection Practices Act* |
| 0.675 | **good** | "Habitability" → *Breach of Warranty of Habitability* |
| 0.645 | bad ×5 | *Wrongful Termination Claim* / *Premises Liability Claim* for any narrative containing "claim" |

The good rows at 0.699 and 0.675 are exactly the two entries on the delta report's **watch list** —
non-marginal concepts (baseline confidence 0.63) the migration dropped. They are not lost to the
scorer swap; they are lost to the bar. The window that separates them from the junk cluster is
**(0.645, 0.675]**, and the production bar sits above it.

**Corroborated bar — production `0.50`:**

| score | verdict | example |
|---|---|---|
| 0.602 | bad | "claim for breach of contract" → *Retaliation Claim* |
| 0.5875 | **good** | "Habitability" → *Breach of Warranty of Habitability* |
| 0.5266 | **bad ×4** | *Premises Liability Claim* / *Wrongful Termination Claim* for "Retaliation Claim" |
| **0.500** | ← **production bar** | |
| 0.4993 | bad | *Breach of Contract Claim* for "Retaliation Claim" |
| 0.47–0.478 | good ×4, bad ×2, ambiguous ×1 | *Employment Law* for "I was fired…" |

The four-item cluster at 0.5266 is a **post-migration artifact**: under the retired scorer,
"Retaliation Claim" → *Premises Liability Claim* scored `1/3` (one shared word over the longer
side) and never came close to the bar. The library's word-overlap-with-reverse-credit scores the
expanded query `"legal claim"` → *Premises Liability Claim* at 0.645, which is enough to clear
0.5 once the embedding stage corroborates it. The migration's own delta report classifies those
rows as **intended_fix** ("recall gained on a legal-content narrative") because `compare.py`
reasons about narrative *categories*, not concept identity. That is a finding about the migration
tooling, not just the operating point — see §7.

Window for the corroborated bar: **(0.5266, 0.5875]**.

---

## 4. Finding: the production point has almost no canary margin

The EMBED-DEGRADE canary fails when a recall-sensitive narrative resolves to **nothing** with the
embedding stage down. Because degraded mode depends only on `t/p`, each narrative has a single
ratio at which it goes silent — its best solo score. The lowest among recall-sensitive narratives
is **0.736** ("Arbitration" → *Arbitration Rules*).

| solo bar | outcome |
|---|---|
| 0.714 | production — canaries green |
| **0.736** | **cliff**: `n-prefix-2` resolves nothing in degraded mode |
| 0.75 | the coarse grid's first failure — `(0.6, 0.45)`, `(0.8, 0.6)` |
| 0.786+ | 5 to 11 narratives go silent |

Production sits **0.022** from the cliff. A threshold nudge of +0.02, or a penalty "softening" to
0.6, breaks the BUG-9 cascade the migration was built to protect. The recommended point sits
0.089 away — four times the margin.

---

## 5. Recommendation

### `SINGLE_STAGE_PENALTY` 0.7 → **0.85**, `confidence_threshold` 0.50 → **0.55**

Corroborated bar **0.55** (inside the (0.5266, 0.5875] window), solo bar **0.647** (inside the
(0.645, 0.675] window). Full row in `captures/sweep.json` (`refine`, penalty 0.85 / threshold 0.55).

| | production (0.7 / 0.5) | recommended (0.85 / 0.55) |
|---|---|---|
| healthy | P 0.667 · R 0.606 · F1 0.635 | **P 0.769 · R 0.606 · F1 0.678** |
| embeddings down | P 0.783 · R 0.545 · F1 0.643 | **P 0.769 · R 0.606 · F1 0.678** |
| canaries | green, 0.022 from the cliff | green, 0.089 from the cliff |
| top-1 changes | — | 0 healthy, 1 degraded |

Every flip, named:

- **Dropped (healthy), 4 — all wrong.** *Premises Liability Claim* and *Wrongful Termination Claim*, from both "Retaliation Claim" and "claim for breach of contract". No true positive is lost in either mode.
- **Added (degraded), 3 — two right, one wrong.** *Fair Debt Collection Practices Act* for the debt narrative and *Breach of Warranty of Habitability* for "Habitability" — **both delta-report watch-list rows** — plus *Retaliation Claim* for "claim for breach of contract" (wrong).
- Healthy and degraded converge on identical precision/recall, i.e. the cascade degrades in *quantity* rather than changing *character*. That is a property worth having independent of the F1.

### Why not the higher-scoring points

- `(0.6, 0.4)` — best mean F1 (0.686). Both bars drop; the corroborated bar at 0.4 re-admits *Employment Law* for "Unauthorized Employment", the `place_trap` row the corpus exists to catch, and the accepted-concept count per narrative rises 36 → 46. Better metric, worse behavior.
- `(1.0, 0.4)` — 0.686, and `penalty = 1.0` deletes the single-stage penalty entirely, which is a policy change (uncorroborated evidence weighs the same as corroborated), not a calibration.
- `(0.8, 0.35)` — 0.681 with 31 flips. Too much movement for the evidence available.

### Confidence

- **Direction: medium-high.** The corroborated bar should go up and the solo bar should come down. Both are argued from named, individually inspectable rows, both windows are visible in the score distribution, and the direction reverses two known watch-list losses while removing a cluster the migration itself introduced.
- **Exact values: medium.** `0.85 / 0.55` is the cleanest pair landing inside both windows, but the windows are defined by *two* corpus rows apiece. On a real intake sample the windows will sit elsewhere. What generalizes is the method: the solo bar belongs above one-shared-word overlap and at or below the short-claim-name → long-FOLIO-label shape.
- **Weakest link:** the gold labels. If "Retaliation Claim" → *Wrongful Termination Claim* is judged acceptable (it is not, but it is a judgment), the healthy half of the recommendation evaporates. The degraded half — which restores both watch-list rows and quadruples the canary margin — does not depend on that call.

### Specificity penalty: leave it alone

folio-resolve v0.3.0 added `specificity_penalty` explicitly for alea's shape ("consumers whose
queries are shorter than their targets by construction … can damp it (0.3-0.5)"). Measured, it is
the wrong instrument here:

| specificity | mean F1 @ (0.7 / 0.5) | mean F1 @ (0.85 / 0.55) |
|---|---|---|
| **1.0** (production) | **0.6389** | **0.678** |
| 0.7 | 0.625 | 0.63 |
| 0.5 | 0.625 | 0.625 |
| 0.3 | 0.625 | 0.625 |
| 0.0 | 0.6202 | 0.625 |

The reason is structural, not incidental. Damping lifts the good case and the junk case together:

| pair | spec 1.0 | 0.5 | 0.0 |
|---|---|---|---|
| "Habitability" → *Breach of Warranty of Habitability* (good) | 0.675 | 0.797 | 0.920 |
| "legal claim" → *Wrongful Termination Claim* (junk) | 0.645 | 0.763 | 0.880 |

The gap stays ~0.03 wide and simply slides up the scale, so no threshold separates them any
better than before. The specificity penalty is what created the separation the bars exploit;
damping it destroys the very window §3 recommends aiming at. **Keep the call site as it is — no
`specificity_penalty` argument at all.**

---

## 6. The average-combine oddity

Full derivation, minimal cases and remedy tables: [`captures/combine-lab.md`](captures/combine-lab.md).

### It is real, and worse than the README says

For a candidate the label stage scores `L`, unretrieved gives `penalty × L` and retrieved at
cosine `e` gives `(e + L)/2`. So at the production point:

- **Rank inversion** whenever `e < 0.4 × L`.
- **Accept inversion** — a candidate that would have been *returned* unretrieved is *dropped* once retrieved — whenever `L ≥ 0.714` and `e < 1.0 − L`. At `L` = 0.714 every cosine below **0.286** flips an accepted concept to rejected.

Reproduced end to end through the real `resolve_concepts` — one query, one concept, varying only
the embedding stage:

| embedding stage | concepts resolved | confidence |
|---|---|---|
| returns nothing | **1** | 0.5152 |
| returns it at cosine 0.10 | **0** | — |
| returns it at cosine 0.20 | **0** | — |
| returns it at cosine 0.30 | **1** | 0.518 |

### Remedies

| rule | evidence-monotone | worst drop | keeps the confidence scale | corpus effect (both points) |
|---|---|---|---|---|
| `current` | **no** | 0.20 | — | — |
| `floor` — `max(current, penalty × best stage)` | **yes** | 0 | yes (identical solo/exact scores) | rescores 20–30 candidates, **0 flips, 0 rank moves** |
| `coverage` — `avg × penalty^(missing weight / total)` | **no** | 0.35 | shifts (solo exact 0.693 → 0.771) | 8 accepts / 4 rejects, F1 ≈ recommended point |
| `presence` — missing stage = 0 over full weight | **yes** | 0 | **no** (solo exact 0.693 → 0.297) | needs `threshold ≈ 0.2`; 19 accepts even then |

*Evidence-monotone* = adding a stage never lowers the score. That is the property under study;
the other columns show what each remedy costs elsewhere.

Three conclusions:

1. **`coverage` is a trap.** Grading the single-stage penalty by how much stage weight is missing is the intuitive generalization, and it is *less* monotone than the status quo (worst drop 0.35 vs 0.20). Worth recording so nobody re-derives it.
2. **`presence` is correct and expensive.** It is the textbook fix, but it rescales every confidence in the system: stored `ConceptMapping` confidences, the 0.85 LLM-stage gate, `exploration_confidence_threshold`, `unmapped.py`'s `1 - best_score/threshold`, and anything a human has learned to read. Not worth it for this defect.
3. **`floor` is free and, on this corpus, worth nothing.** It rescores 20 candidates at the production point and 30 at the recommended one, and changes **no** accept decision and **no** ranking in either. Every inversion-region candidate here sits far below the bar. The end-to-end reproduction above shows the shape exists; the corpus's generous cosine stand-in means it does not *occur* here. In production — real sentence-transformer cosines, `top_k=20` truncation — weak retrievals in the low tenths are ordinary.

**Recommendation: adopt `floor` only if the operating-point change is adopted, and only as insurance.** It is a two-line change with a provable invariant, zero measured behavior delta, and it removes a class of bug that is invisible to this corpus by construction. If the appetite is for one change at a time, defer it — the evidence says it is not urgent, only cheap.

---

## 7. Two findings outside the brief

### The expansion vocabulary, not the operating point, is the first-order lever

`sweep.py` re-runs both operating points with alea's lay-language query expansion switched off:

| point | expansions | P healthy | R healthy | P degraded | R degraded |
|---|---|---|---|---|---|
| production 0.7 / 0.5 | on | 0.667 | 0.606 | 0.783 | 0.545 |
| production 0.7 / 0.5 | **off** | **1.000** | 0.333 | **1.000** | 0.303 |
| recommended 0.85 / 0.55 | on | 0.769 | 0.606 | 0.769 | 0.606 |
| recommended 0.85 / 0.55 | **off** | **1.000** | 0.333 | **1.000** | 0.333 |

**Every single false positive on this corpus is manufactured by query expansion**, and the worst
of them cannot be fixed by any threshold:

- `"claim"` → `["insurance claim", "legal claim", "cause of action"]`. Any narrative containing the word "claim" therefore searches for `"insurance claim"`, which scores **0.92** against *Insurance Claims* and pulls a healthy embedding hit alongside it — 0.71 combined, above any sane bar. This is the top-ranked false positive in two narratives, in both modes, at every grid point.
- `"legal claim"` reduces to the single content word `{claim}` (the library drops "legal" as filler), which scores **0.645** against any `* Claim` label — the junk cluster of §3.
- `"warranty"` → `"consumer protection"` puts *Consumer Protection Law* on top of a habitability complaint at 0.92.
- `"rent"` → `"housing"` puts *Housing Authority* — an agency — on a rent narrative at 0.736.

Expansion buys ~+0.27 recall for ~−0.33 precision. That trade may well be right for consumer
intake, but it is currently unexamined, and it is where the next calibration operation should go.
Two cheap shapes suggest themselves (neither measured here, both out of scope): drop expansions
whose content-word set collapses to a single generic token, and score expansion-derived hits at a
discount relative to hits on the narrative itself.

### `compare.py` classifies by category, so it can bless a precision loss

The four-row junk cluster at 0.5266 arrived in the migration's delta report as
**intended_fix — "recall gained on a legal-content narrative"** (`n-exact-label`,
`n-word-order-2`). At concept level the gained candidates are wrong. `compare.py`'s heuristic —
recall-sensitive narrative + gained candidates = good — is the right default for a *migration*
gate, but it cannot see concept identity, which is why this study needed its own gold file. A
worthwhile follow-up: teach `compare.py` to consult `sweep_gold.json` when it exists, so a future
migration cannot bank a precision regression as a fix.

---

## 8. What changes if adopted

**Source (2 lines):**

- `app/services/folio/concept_resolver.py:63` — `SINGLE_STAGE_PENALTY: float = 0.7` → `0.85`, with a comment pointing here.
- `app/services/folio/concept_resolver.py:84` — `confidence_threshold: float = 0.5` → `0.55`.

**Tests that must move (verified by simulation, not guesswork** — the full suite was run with both
knobs patched in-process at session start; exactly these fail, and nothing else does):

- `tests/test_concept_resolver.py:48` — `assert config.confidence_threshold == 0.5` → `0.55`.
- `tests/test_folio_resolve_pin.py:200` — `assert concept_resolver.SINGLE_STAGE_PENALTY == 0.7` → `0.85`.
- `tests/test_migration_sweep.py` — 4 tests pin the study's reference point; `sweep.REF_PENALTY` / `REF_THRESHOLD` move with the source and the reference capture is re-taken.

**Nothing else in the 1,266-test suite depends on the operating point.** No behavioral test, no
router test, no analysis-pipeline test changes. That is the strongest single argument that the
blast radius is small — and also a mild warning that the operating point is under-tested outside
these two assertions.

**Also needs a decision (not required, but it is inconsistent today):**

- `app/config.py:68` — `folio_confidence_threshold: float = 0.5` is *reported* by `GET /folio/admin` (`app/routers/folio_admin.py:116`) but never wired into `ConceptResolutionConfig`. After adoption it would report a stale number. Either wire it up (so the operating point is configurable in one place) or drop it.
- `app/services/folio/unmapped.py:73` — an independent `confidence_threshold: float = 0.5` feeds `unmapped_confidence = 1 - best_score/threshold`. Unrelated code path, same magic number; worth a comment either way.
- Stored `ConceptMapping.confidence` values written before the change keep their old meaning. Nothing recomputes them. Acceptable for a ±0.05 shift on the same scale — and a decisive argument against the `presence` remedy, which would move the scale itself.

**Migration-harness follow-up:** re-take `captures/candidate.json` after adoption and re-run
`compare.py` against the committed `baseline.json`. The delta will be non-empty by design; the
two watch-list rows should come back and the 0.5266 cluster should go. That run is the adoption's
own evidence pack.

**Rollback:** revert the two constants. No data migration, no schema change, no re-index.

---

## 9. Reproducing

```bash
cd backend
.venv/bin/python migration/sweep.py            # grid + refinement + specificity axis + ablation
.venv/bin/python migration/sweep.py --verify   # fidelity check only
.venv/bin/python migration/combine_lab.py      # the averaging oddity
.venv/bin/python -m pytest tests/test_migration_sweep.py
```

The specificity axis needs a folio-resolve ≥ 0.3.0 source checkout beside this repo; without one
it is skipped and says so in the output. Everything else is self-contained.
