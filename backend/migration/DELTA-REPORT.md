# alea-intake -> folio-resolve migration — classified delta report

- baseline capture: `baseline` (folio-resolve consumed: `False`)
- candidate capture: `candidate` (folio-resolve consumed: `True`, version `0.1.0`)
- corpus hash: `d4f8b948a5244c8d…`

## Headline

- Intended fixes: **15**
- Regressions: **0**
- Neutral changes: **36**

## Buckets

- **fit_delta** — 3
- **rank_delta** — 27
- **score_delta** — 11
- **set_delta** — 10

## Canaries

- ✅ PLACE-REJECTED — every unfit claim mapping rejected; no good mapping over-rejected
- ✅ PLACES-RESOLVABLE — the general resolver still resolves explicitly named places
- ✅ EMPTY-STAYS-EMPTY — stopword-only / empty / nonsense narratives resolve to nothing
- ✅ EMBED-DEGRADE — the label stage still carries the cascade when embeddings fail (BUG-9)
- ✅ NO-RECALL-LOSS — no recall-sensitive narrative fell to zero concepts

## Watch list — non-marginal candidates lost

A concept that scored **≥ 0.6** in the baseline and is gone in the candidate is not a 0.5-boundary artifact. Listed here regardless of classification so a real recall loss cannot hide in a precision bucket.

| id | seam | lost concept | baseline conf | row classified |
|----|------|--------------|---------------|----------------|
| n-expansion-debt | resolve_no_embed | Fair Debt Collection Practices Act | 0.63 | neutral |
| n-homonym-habitability | resolve_no_embed | Breach of Warranty of Habitability | 0.63 | intended_fix |

## Deltas

| id | seam | bucket | class | why | baseline | candidate |
|----|------|--------|-------|-----|----------|-----------|
| fit-gov-body | fit | fit_delta | **intended_fix** | a claim mapping the corpus marks unfit is now rejected | rejected=False (None) | rejected=True (geographic_concept) |
| fit-gov-body-2 | fit | fit_delta | **intended_fix** | a claim mapping the corpus marks unfit is now rejected | rejected=False (None) | rejected=True (geographic_concept) |
| sp-exact | label_score | score_delta | **intended_fix** | an exact label match should score at the top of the scale, not the generic substring constant | 0.9 | 0.99 |
| sp-prefix-credit | label_score | score_delta | **intended_fix** | prefix-match credit: the hand-rolled set-intersection scorer was blind to morphology | 0.0 | 0.37 |
| sp-reverse-substring | label_score | score_delta | **intended_fix** | reverse (target->query) overlap lets a narrow label match a long narrative | 0.375 | 0.66 |
| sp-single-word | label_score | score_delta | **intended_fix** | specificity penalty on the broader label | 0.9 | 0.736 |
| sp-single-word-exact | label_score | score_delta | **intended_fix** | exact match must outrank the merely-broader 'Lease Agreement' | 0.9 | 0.99 |
| sp-specificity | label_score | score_delta | **intended_fix** | specificity penalty: the label is far more specific than the one-word query | 0.9 | 0.675 |
| sp-word-order | label_score | score_delta | **intended_fix** | word-order invariance: {rules, arbitration} == {arbitration, rules} | 0.666667 | 0.88 |
| n-exact-label | resolve | set_delta | **intended_fix** | recall gained on a legal-content narrative | 2 lost=[] | 4 gained=[('Premises Liability Claim', 0.5266), ('Wrongful Termination Claim', 0.5266)] |
| n-homonym-claim | resolve | set_delta | **intended_fix** | precision-sensitive narrative: dropping weak candidates is the goal | 3 lost=[('Lease Agreement', 0.5)] | 2 gained=[] |
| n-place-implicit | resolve | set_delta | **intended_fix** | precision-sensitive narrative: dropping weak candidates is the goal | 1 lost=[('Employment Law', 0.5)] | 0 gained=[] |
| n-short-token | resolve | set_delta | **intended_fix** | precision-sensitive narrative: dropping weak candidates is the goal | 3 lost=[('Lease Agreement', 0.5)] | 2 gained=[] |
| n-word-order-2 | resolve | set_delta | **intended_fix** | recall gained on a legal-content narrative | 3 lost=[] | 5 gained=[('Premises Liability Claim', 0.5266), ('Wrongful Termination Claim', 0.5266)] |
| n-homonym-habitability | resolve_no_embed | set_delta | **intended_fix** | precision-sensitive narrative: dropping weak candidates is the goal | 1 lost=[('Breach of Warranty of Habitability', 0.63)] | 0 gained=[] |
| fit-place-token | fit | fit_delta | **neutral** | rejection reason changed, verdict unchanged | rejected=True (unfit_branch) | rejected=True (geographic_concept) |
| sp-long-query | label_score | score_delta | **neutral** | long narrative against a short label | 0.111111 | 0.33 |
| sp-partial | label_score | score_delta | **neutral** | substring hit under both scorers | 0.9 | 0.88 |
| sp-stopword-heavy | label_score | score_delta | **neutral** | differing stopword vocabularies: alea keeps 'law' as content, the library does not | 0.2 | 0.0 |
| sp-substring | label_score | score_delta | **neutral** | substring hit under both scorers | 0.9 | 0.736 |
| n-compound | resolve | set_delta | **neutral** | candidate dropped below the 0.5 confidence bar | 2 lost=[('Employment Law', 0.5)] | 1 gained=[] |
| n-expansion-custody | resolve | rank_delta | **neutral** | candidate set changed on a recall-sensitive narrative | 1 | 1 |
| n-expansion-debt | resolve | rank_delta | **neutral** | candidate set changed on a recall-sensitive narrative | 2 | 2 |
| n-expansion-eviction | resolve | rank_delta | **neutral** | candidate set changed on a recall-sensitive narrative | 4 | 4 |
| n-expansion-fired | resolve | set_delta | **neutral** | candidate dropped below the 0.5 confidence bar | 2 lost=[('Employment Law', 0.5)] | 1 gained=[] |
| n-gov-body | resolve | rank_delta | **neutral** | no directional expectation for this category | 1 | 1 |
| n-homonym-habitability | resolve | rank_delta | **neutral** | precision-sensitive narrative: dropping weak candidates is the goal | 1 | 1 |
| n-homonym-lease | resolve | rank_delta | **neutral** | precision-sensitive narrative: dropping weak candidates is the goal | 1 | 1 |
| n-long | resolve | rank_delta | **neutral** | no directional expectation for this category | 4 | 4 |
| n-place-explicit | resolve | rank_delta | **neutral** | no directional expectation for this category | 1 | 1 |
| n-prefix | resolve | rank_delta | **neutral** | candidate set changed on a recall-sensitive narrative | 2 | 2 |
| n-prefix-2 | resolve | rank_delta | **neutral** | candidate set changed on a recall-sensitive narrative | 1 | 1 |
| n-subphrase | resolve | set_delta | **neutral** | candidate dropped below the 0.5 confidence bar | 3 lost=[('Retaliation Claim', 0.5)] | 2 gained=[] |
| n-word-order | resolve | rank_delta | **neutral** | candidate set changed on a recall-sensitive narrative | 1 | 1 |
| n-compound | resolve_no_embed | rank_delta | **neutral** | candidate set changed on a recall-sensitive narrative | 1 | 1 |
| n-exact-label | resolve_no_embed | rank_delta | **neutral** | candidate set changed on a recall-sensitive narrative | 2 | 2 |
| n-expansion-custody | resolve_no_embed | rank_delta | **neutral** | candidate set changed on a recall-sensitive narrative | 1 | 1 |
| n-expansion-debt | resolve_no_embed | set_delta | **neutral** | candidate dropped below the 0.5 confidence bar | 2 lost=[('Fair Debt Collection Practices Act', 0.63)] | 1 gained=[] |
| n-expansion-eviction | resolve_no_embed | rank_delta | **neutral** | candidate set changed on a recall-sensitive narrative | 4 | 4 |
| n-expansion-fired | resolve_no_embed | rank_delta | **neutral** | candidate set changed on a recall-sensitive narrative | 1 | 1 |
| n-gov-body | resolve_no_embed | rank_delta | **neutral** | no directional expectation for this category | 1 | 1 |
| n-homonym-claim | resolve_no_embed | rank_delta | **neutral** | precision-sensitive narrative: dropping weak candidates is the goal | 2 | 2 |
| n-homonym-lease | resolve_no_embed | rank_delta | **neutral** | precision-sensitive narrative: dropping weak candidates is the goal | 1 | 1 |
| n-long | resolve_no_embed | rank_delta | **neutral** | no directional expectation for this category | 4 | 4 |
| n-place-explicit | resolve_no_embed | rank_delta | **neutral** | no directional expectation for this category | 1 | 1 |
| n-prefix | resolve_no_embed | rank_delta | **neutral** | candidate set changed on a recall-sensitive narrative | 2 | 2 |
| n-prefix-2 | resolve_no_embed | rank_delta | **neutral** | candidate set changed on a recall-sensitive narrative | 1 | 1 |
| n-short-token | resolve_no_embed | rank_delta | **neutral** | precision-sensitive narrative: dropping weak candidates is the goal | 2 | 2 |
| n-subphrase | resolve_no_embed | rank_delta | **neutral** | candidate set changed on a recall-sensitive narrative | 2 | 2 |
| n-word-order | resolve_no_embed | rank_delta | **neutral** | candidate set changed on a recall-sensitive narrative | 1 | 1 |
| n-word-order-2 | resolve_no_embed | rank_delta | **neutral** | candidate set changed on a recall-sensitive narrative | 2 | 2 |
