# alea-intake → folio-resolve migration harness

Retire-the-fork prep for row 4 of [`folio-resolve/docs/migration/SCHEDULE.md`](../../../folio-resolve/docs/migration/SCHEDULE.md).
alea-intake is the heaviest external consumer of FOLIO concept matching: a three-stage cascade
(embedding → label/prefix → LLM) with a hand-rolled Stage-2 scorer, a weighted combine, and a
hand-curated geographic gate in the semantic-fit validator.

This directory is the **golden baseline** that guards the swap. It exists so the migration is
provable rather than hopeful: capture behavior before, swap internals, capture after, and classify
every difference.

## Why the bar here is *not* "empty delta"

folio-mapper's migration expected a byte-identical delta — it was the **donor** of the library's
scorer, so consuming the library had to be a pure internals swap. alea-intake is different: its
Stage-2 label scorer was a genuinely different, hand-rolled set-intersection ratio
(`common / max(len(query_words), len(label_words))`, plus a flat `0.9` substring constant and a
flat `0.7` prefix constant), and its geographic rejection was a hand-curated list of continent
names plus `"republic of"`-style phrase markers. Replacing those with the library's
word-order-invariant scorer and `PlaceNameGate` **must** move numbers.

So `compare.py` classifies rather than merely diffs. `corpus.json` records, per row, what the
migration is *supposed* to do (`score_pairs[].expect`, `fit[].expect_reject`) and every delta lands
in one of three buckets:

- **intended_fix** — the row moved the way the corpus says it should
- **regression** — it moved the wrong way, or a row marked "must not move" moved
- **neutral** — no directional expectation

Any regression, or any canary failure, exits non-zero.

## Seams captured

All deterministic — **$0 LLM spend, no ontology download, no network, no database.** The FOLIO
instance and the embedding backend are offline stand-ins owned by the harness (identical before and
after the swap), so the only thing that can move is alea-intake's own code.

| Seam | Drives |
|---|---|
| `expansion` | `term_expansions.expand_legal_terms` / `get_branch_signals` |
| `stopword` | `concept_resolver._is_stopword_only` |
| `combine` | `concept_resolver._combine_score` (fixed stage-score tuples) |
| `label_score` | the Stage-2 label scorer, isolated through `_stage_label_prefix` with a one-candidate stub |
| `resolve` | `concept_resolver.resolve_concepts` end to end (LLM stage disabled) |
| `resolve_no_embed` | the same, with the embedding backend raising (BUG-9 cascade) |
| `fit` | `semantic_fit.deterministic_unfit_reason` / `is_geographic_concept` / `apply_deterministic` |

## Canaries

1. **PLACE-REJECTED** — every claim-fitness row marked `expect_reject` is rejected (BUG-21: a claim
   may never map to a place, an agency, a placeholder, or an unfit branch), and no row marked fit
   starts being rejected.
2. **PLACES-RESOLVABLE** — the *general* resolver still resolves an explicitly named place
   (`"Macedonia"` → *Macedonia*). The place gate belongs to claim fitness, **not** to
   `resolve_concepts`, which legitimately resolves Location concepts (jurisdiction, venue). This is
   the mirror image of folio-mapper's PLACES-PRESERVED canary.
3. **EMPTY-STAYS-EMPTY** — stopword-only / empty / nonsense narratives keep resolving to nothing.
4. **EMBED-DEGRADE** — with the embedding backend raising, narratives still resolve through the
   label stage (BUG-9: deterministic-first, probabilistic assist).
5. **NO-RECALL-LOSS** — no recall-sensitive narrative (real legal content in the query) falls to
   zero concepts.

The baseline **fails** canary 1 on two rows by design: `fit-gov-body` / `fit-gov-body-2` show a
claim mapping to a Governmental Body, which the hand-curated gate accepted. The candidate must
pass them.

## Determinism

`harness.py` re-executes itself with `PYTHONHASHSEED=0`. folio-resolve's `generate_search_terms`
iterates a `set` of content words, so term order (and therefore tie-breaks among equally scored
candidates) varies between processes under PEP 456 hash randomization — a known, deliberately-open
upstream issue recorded in the library's `SCHEDULE.md`. Pinning the seed keeps real deltas from
drowning in reordering noise.

## Usage

```bash
.venv/bin/python migration/harness.py --out baseline     # BEFORE the swap (committed)
.venv/bin/python migration/harness.py --out candidate    # AFTER the swap
.venv/bin/python migration/compare.py --baseline baseline --candidate candidate
```

`compare.py` writes `DELTA-REPORT.md` and `captures/delta.json`, and exits non-zero on any canary
failure or regression.

## Corpus

`corpus.json` is entirely **synthetic** — invented consumer narratives and a 41-node hand-written
mini-ontology standing in for FOLIO (`r-*` stub IRIs). No customer intake data, no real matter
text, nothing that would be unsafe to commit.
