# Expansion-vocabulary calibration study — 2026-11-08

**Recommendation: no change.** Keep the expansion vocabulary and its current weighting at penalty **0.85**, threshold **0.55**, with the **floor** combine rule. This is a study; no application configuration, vocabulary, scoring, or gold labels were changed.

The corpus supports targeted hypotheses about generic expansions, but does not establish that deleting them improves consumer intake generally. It has 26 synthetic narratives, 41 invented ontology nodes, and 33 positive concept labels per embedding mode. Only 11 of 34 vocabulary triggers affect emitted queries. There is no held-out evaluation, realistic embedding model, or positive insurance-claim example that could reveal the recall cost of deleting that expansion. The healthy and degraded results are paired measurements of the same stories, not independent samples. Do not adopt corpus-specific pruning on these results alone.

## Method and reproducibility

The new `migration/sweep.py --expansion-study` path evaluates 144 arms: the adopted baseline, an empty vocabulary retaining the filtered narrative query, no expanded queries at all, 34 leave-one-trigger-out arms, and 107 leave-one-phrase-out arms. Each arm uses the unchanged gold judgments and real resolver stage functions with the migration harness’s offline FOLIO and binary-cosine embedding stand-ins. The degraded mode raises on embedding lookup and uses the existing label cascade. LLM resolution is disabled. There are no network, database, model download, or LLM calls.

Vocabulary ablations preserve tokenization, stopwords, phrase ordering, deduplication, the filtered narrative query, stage weights (0.3 embedding / 0.3 label / 0.4 LLM), retrieval limits, and the production first-five-expanded-queries cap. Removing a phrase can expose a later phrase or filtered query; every affected narrative is retrieved again. Identical query lists reuse their baseline pools. Each JSON arm records before/after effective queries, detailed accepted/rejected concept flips, missed concepts, false positives, precision/recall/F1 and canaries. Ambiguous mappings count in accepted totals but in neither precision nor recall.

Baseline reconstruction was checked against the actual resolver for every narrative in both modes; **zero fidelity differences**. The independent claim-fitness canary also passed. Baseline precision/recall reproduce the November recheck on installed **folio-resolve 0.2.0**. The earlier sweep’s historical weighted-average arm is not used for this study.

Exact command, from `backend/`:

```bash
PYTHONHASHSEED=0 PYTHONPATH=.:/tmp/alea-expansion-study HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 "/home/damienriehl/Coding Projects/alea-intake/backend/.venv/bin/python" migration/sweep.py --expansion-study > /tmp/alea-expansion-study/results.json
```

The sandbox requires the temporary startup hook below at `/tmp/alea-expansion-study/sitecustomize.py` (create that directory first). It redirects only the imported library’s default log into `/tmp` and replaces the blocked asyncio wakeup socket with selector polling. Executor threads, retrieval, and scoring remain real. No credential files are read. Outside this restricted sandbox, omit the hook and its `PYTHONPATH` entry.

```python
import logging.handlers
from pathlib import Path
_original = logging.handlers.RotatingFileHandler.__init__
def _redirect(self, filename, *args, **kwargs):
    if str(filename).endswith('/.alea/logs/alea_llm_client.log'):
        filename = '/tmp/alea-expansion-study/alea_llm_client.log'
    _original(self, filename, *args, **kwargs)
logging.handlers.RotatingFileHandler.__init__ = _redirect

# This sandbox disallows the asyncio self-pipe. Executor work still uses real threads;
# a short selector poll delivers their completed callbacks without a wakeup socket.
import asyncio
import selectors
class _PollingSelector(selectors.DefaultSelector):
    def select(self, timeout=None):
        return super().select(0.01 if timeout is None else min(timeout, 0.01))
class _OfflineLoop(asyncio.SelectorEventLoop):
    def __init__(self):
        super().__init__(_PollingSelector())
    def _make_self_pipe(self):
        self._ssock = self._csock = None
    def _write_to_self(self):
        pass
    def _close_self_pipe(self):
        pass
class _Policy(asyncio.DefaultEventLoopPolicy):
    def new_event_loop(self):
        return _OfflineLoop()
asyncio.set_event_loop_policy(_Policy())
```

## Overall precision and recall

Both embedding modes produce the same counts in every arm. Tables therefore show one row per arm applying separately to **each** mode; do not double these counts when interpreting corpus size.

| Arm | TP | FP | FN | Ambiguous accepted | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| adopted | 20 | 6 | 13 | 6 | 0.7692 | 0.6061 | 0.6780 |
| filtered-query-only | 11 | 0 | 22 | 0 | 1.0000 | 0.3333 | 0.5000 |
| no-expanded-queries | 11 | 0 | 22 | 0 | 1.0000 | 0.3333 | 0.5000 |

Expansion adds **9 TP** and **6 FP** per mode, increasing recall by **0.2728** and reducing precision by **0.2308**. Disabling it loses all accepted concepts on the firing, eviction, custody, debt, and compound narratives (five recall canaries in each mode). That is not a suitable change. Keeping just the filtered query yields the same acceptance decisions as disabling all expanded queries on this corpus.

## Trigger ablations and coverage

The table reports the result **after removal**, not an additive contribution. “Emitted-query narratives” counts differences in the complete expansion output; “effective-query narratives” counts differences in the first five actually searched. A zero effect is absence of measured evidence, not proof of safety or uselessness.

| Trigger removed | Emitted-query narratives | Effective-query narratives | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| fired | 1 | 1 | 19 | 6 | 14 | 0.7600 | 0.5758 | 0.6552 |
| terminated | 0 | 0 | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 |
| laid off | 1 | 1 | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 |
| custody | 1 | 1 | 19 | 6 | 14 | 0.7600 | 0.5758 | 0.6552 |
| divorce | 0 | 0 | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 |
| alimony | 0 | 0 | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 |
| eviction | 2 | 2 | 18 | 6 | 15 | 0.7500 | 0.5455 | 0.6316 |
| landlord | 2 | 2 | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 |
| rent | 2 | 2 | 20 | 4 | 13 | 0.8333 | 0.6061 | 0.7018 |
| arrested | 0 | 0 | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 |
| charged | 0 | 0 | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 |
| stolen | 0 | 0 | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 |
| ticket | 0 | 0 | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 |
| accident | 0 | 0 | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 |
| injury | 0 | 0 | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 |
| slip | 0 | 0 | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 |
| debt | 1 | 1 | 18 | 6 | 15 | 0.7500 | 0.5455 | 0.6316 |
| bankruptcy | 0 | 0 | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 |
| foreclosure | 0 | 0 | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 |
| discrimination | 1 | 1 | 19 | 6 | 14 | 0.7600 | 0.5758 | 0.6552 |
| harassment | 0 | 0 | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 |
| abuse | 0 | 0 | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 |
| immigration | 0 | 0 | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 |
| deported | 0 | 0 | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 |
| will | 0 | 0 | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 |
| inheritance | 0 | 0 | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 |
| contract | 1 | 1 | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 |
| agreement | 0 | 0 | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 |
| insurance | 0 | 0 | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 |
| claim | 2 | 2 | 20 | 4 | 13 | 0.8333 | 0.6061 | 0.7018 |
| benefits | 0 | 0 | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 |
| disability | 0 | 0 | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 |
| scam | 0 | 0 | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 |
| warranty | 1 | 1 | 20 | 5 | 13 | 0.8000 | 0.6061 | 0.6897 |

The 23 triggers with zero emitted-query narratives are unexercised here. In particular, `will` is filtered as a stopword before single-token expansion; the presence of a mapping in the dictionary does not establish that it is reached. This study changes neither that contract nor the corpus.

## Phrase ablations

Every one of the 107 trigger/phrase pairs was removed individually. All results, including acceptance-neutral arms, follow. Healthy and degraded modes have identical metrics. An acceptance-neutral arm may still change confidences or rankings; those counts are retained in the command’s JSON output.

| Trigger | Phrase removed | TP | FP | FN | Precision | Recall | F1 | Accepts gained / lost |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| fired | wrongful termination | 19 | 6 | 14 | 0.7600 | 0.5758 | 0.6552 | 0 / 1 |
| fired | employment termination | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| fired | discharge | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| terminated | wrongful termination | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| terminated | employment termination | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| laid off | layoff | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| laid off | reduction in force | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| laid off | unemployment | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| custody | child custody | 19 | 6 | 14 | 0.7600 | 0.5758 | 0.6552 | 0 / 1 |
| custody | parental rights | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| custody | custodial arrangement | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| divorce | dissolution of marriage | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| divorce | marital dissolution | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| alimony | spousal support | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| alimony | spousal maintenance | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| eviction | unlawful detainer | 18 | 6 | 15 | 0.7500 | 0.5455 | 0.6316 | 0 / 2 |
| eviction | forcible entry | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| eviction | landlord tenant | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| landlord | landlord tenant | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| landlord | lease agreement | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 4 |
| landlord | rental dispute | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| rent | rental agreement | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| rent | lease dispute | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 2 |
| rent | housing | 20 | 4 | 13 | 0.8333 | 0.6061 | 0.7018 | 0 / 2 |
| arrested | criminal arrest | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| arrested | detention | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| arrested | law enforcement encounter | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| charged | criminal charge | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| charged | indictment | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| charged | arraignment | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| stolen | theft | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| stolen | larceny | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| stolen | property crime | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| stolen | stolen property | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| ticket | traffic violation | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| ticket | citation | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| ticket | infraction | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| accident | personal injury | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| accident | negligence | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| accident | tort | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| injury | personal injury | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| injury | bodily harm | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| injury | physical injury | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| injury | damages | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| slip | slip and fall | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| slip | premises liability | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| debt | debt collection | 18 | 6 | 15 | 0.7500 | 0.5455 | 0.6316 | 0 / 2 |
| debt | creditor | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| debt | consumer debt | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| debt | fair debt | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| bankruptcy | chapter 7 | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| bankruptcy | chapter 13 | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| bankruptcy | insolvency | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| bankruptcy | debt relief | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| foreclosure | mortgage foreclosure | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| foreclosure | property seizure | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| foreclosure | deed in lieu | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| discrimination | employment discrimination | 19 | 6 | 14 | 0.7600 | 0.5758 | 0.6552 | 0 / 1 |
| discrimination | civil rights violation | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| discrimination | protected class | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| harassment | workplace harassment | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| harassment | hostile work environment | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| harassment | sexual harassment | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| abuse | domestic violence | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| abuse | child abuse | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| abuse | elder abuse | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| abuse | physical abuse | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| immigration | immigration status | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| immigration | visa | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| immigration | deportation | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| immigration | asylum | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| deported | deportation | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| deported | removal proceedings | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| deported | immigration enforcement | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| will | estate planning | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| will | testamentary | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| will | probate | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| will | last will and testament | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| inheritance | estate | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| inheritance | probate | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| inheritance | succession | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| inheritance | heir | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| contract | breach of contract | 20 | 7 | 13 | 0.7407 | 0.6061 | 0.6667 | 1 / 0 |
| contract | contractual obligation | 20 | 7 | 13 | 0.7407 | 0.6061 | 0.6667 | 1 / 0 |
| contract | agreement | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| agreement | contract | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| agreement | settlement agreement | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| agreement | binding agreement | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| insurance | insurance claim | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| insurance | coverage denial | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| insurance | bad faith insurance | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| claim | insurance claim | 20 | 5 | 13 | 0.8000 | 0.6061 | 0.6897 | 1 / 2 |
| claim | legal claim | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 1 / 1 |
| claim | cause of action | 20 | 7 | 13 | 0.7407 | 0.6061 | 0.6667 | 1 / 0 |
| benefits | government benefits | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| benefits | social security | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| benefits | disability benefits | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| benefits | unemployment | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| disability | disability benefits | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| disability | ADA | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| disability | disability discrimination | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| scam | fraud | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| scam | consumer fraud | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| scam | deceptive practices | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| warranty | warranty claim | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| warranty | product liability | 20 | 6 | 13 | 0.7692 | 0.6061 | 0.6780 | 0 / 0 |
| warranty | consumer protection | 20 | 5 | 13 | 0.8000 | 0.6061 | 0.6897 | 0 / 1 |

## Which expansions help and hurt

Concept identifiers below belong to the synthetic ontology, not the public FOLIO ontology. Counts apply per mode. The table lists every acceptance-changing phrase arm, including ambiguous losses and newly exposed errors.

| Removed mapping | Accepted concepts lost | Accepted concepts gained |
|---|---|---|
| fired → wrongful termination | `n-expansion-fired` → `r-wrongful-termination` (good) | — |
| custody → child custody | `n-expansion-custody` → `r-child-custody` (good) | — |
| eviction → unlawful detainer | `n-expansion-eviction` → `r-unlawful-detainer` (good)<br>`n-long` → `r-unlawful-detainer` (good) | — |
| landlord → lease agreement | `n-expansion-eviction` → `r-lease` (ambiguous)<br>`n-expansion-eviction` → `r-lease-agreement` (ambiguous)<br>`n-long` → `r-lease` (ambiguous)<br>`n-long` → `r-lease-agreement` (ambiguous) | — |
| rent → lease dispute | `n-homonym-claim` → `r-lease` (ambiguous)<br>`n-short-token` → `r-lease` (ambiguous) | — |
| rent → housing | `n-homonym-claim` → `r-housing-authority` (false positive)<br>`n-short-token` → `r-housing-authority` (false positive) | — |
| debt → debt collection | `n-expansion-debt` → `r-debt-collection` (good)<br>`n-expansion-debt` → `r-fair-debt-act` (good) | — |
| discrimination → employment discrimination | `n-compound` → `r-employment-discrimination` (good) | — |
| contract → breach of contract | — | `n-word-order-2` → `r-lease-agreement` (false positive) |
| contract → contractual obligation | — | `n-word-order-2` → `r-lease-agreement` (false positive) |
| claim → insurance claim | `n-exact-label` → `r-insurance-claims` (false positive)<br>`n-word-order-2` → `r-insurance-claims` (false positive) | `n-word-order-2` → `r-lease-agreement` (false positive) |
| claim → legal claim | `n-word-order-2` → `r-retaliation` (false positive) | `n-word-order-2` → `r-lease-agreement` (false positive) |
| claim → cause of action | — | `n-word-order-2` → `r-lease-agreement` (false positive) |
| warranty → consumer protection | `n-subphrase` → `r-consumer-protection` (false positive) | — |

Useful measured mappings are `fired → wrongful termination`, `custody → child custody`, `eviction → unlawful detainer` (two narratives), `debt → debt collection` (two concepts), and `discrimination → employment discrimination`. Their removal loses true positives. `landlord → lease agreement` supplies four ambiguous matches; those are not evidence of either a precision gain or a recall loss.

The strongest precision-only deletion hypothesis here is `rent → housing`: removing it drops Housing Authority on two rent stories, improves precision to 0.8333, and retains all 20 TP and six ambiguous acceptances. That association is overbroad for these narratives, but the corpus has no positive housing-agency story to test its useful scope. Removing `warranty → consumer protection` drops one FP on a habitability story, but there is no consumer product warranty story testing its intended use.

`claim → insurance claim` creates Insurance Claims on two unrelated claim stories. Removing it eliminates both errors but admits Lease Agreement on the breach-of-contract story, for a net reduction of only one FP. Removing the entire `claim` trigger also eliminates Retaliation Claim on that story but still admits Lease Agreement: net two fewer FP, with all 20 TP retained. This is query-budget interaction, not independent evidence that the newly exposed query is sound. Removing `claim → legal claim` trades one FP for another; removing `claim → cause of action`, `contract → breach of contract`, or `contract → contractual obligation` actually adds one FP. No broad generic-word pruning rule is supported by these results.

## Decision and limits

**No change** is the sole adoption recommendation. Retain the vocabulary and weighting. The current expansion behavior has demonstrated recall value; the measured deletion gains come from a tiny synthetic set without counterexamples for the deleted phrases. A larger, held-out corpus covering both the intended sense and the homonyms would be needed to decide those deletions. This recommendation does not adopt or request adoption of any alternative operating point.

An expansion-score discount was considered and not built: the current pool stores per-stage maxima without query provenance, so discounting pooled scores would also discount original-query evidence and would not measure the proposed mechanism. Accurate weighting would require separate per-query provenance and a further study; the measured vocabulary ablations satisfy this study’s scope. No runtime guards, retries, new interfaces, dependency changes, or gold-label changes were added.

## Verification

Two new tests were written and observed failing before sweep implementation: `test_empty_vocabulary_keeps_filtered_narrative_query` raised `TypeError: build_pools() got an unexpected keyword argument 'vocabulary'`; `test_expansion_study_attributes_claim_false_positives` raised `AttributeError: module 'sweep' has no attribute 'expansion_study'`. The latter now drives the CLI and checks concrete baseline counts, both helpful and harmful phrase effects, newly exposed false positives, and restoration of the application vocabulary object. The existing fidelity, gold-integrity, production-configuration, and adopted-output tests remain unchanged.

Final test command from `backend/`:

```bash
PYTHONHASHSEED=0 PYTHONPATH=.:/tmp/alea-expansion-study HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 "/home/damienriehl/Coding Projects/alea-intake/backend/.venv/bin/python" -m pytest tests/test_migration_sweep.py -q -p no:cacheprovider
```

**19 passed**. The study command exited 0; all 144 arms completed, with zero baseline fidelity differences. A second study run produced byte-identical JSON. `git diff --check` passed. No app behavior changed, and no app files were edited. The initial unhooked test attempt stopped at collection because the library default log is outside the writable roots; no dependency was installed. The hook and raw JSON live only in `/tmp`; all measured metrics and acceptance-changing phrase details are preserved above.
