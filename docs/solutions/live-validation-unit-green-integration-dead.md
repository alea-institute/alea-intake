# Unit-green, integration-dead: how a 1,085-test suite hid a fully inert LLM pipeline

**Date:** 2026-07-07 · **Campaign:** persona UAT (Lane 3) · **Severity of lesson:** portfolio-wide

## The problem

alea-intake had 1,045+ passing unit tests and a "code-complete" LLM analysis
pipeline — and on first live exercise, **zero facts were ever extracted, zero
FOLIO IRIs ever resolved, and every LLM request was rejected by the provider.**
Five deploy-diagnose-fix cycles surfaced an unbroken chain of contract bugs,
each invisible to the suite:

1. **BUG-4** — every call site passed message dicts positionally
   (`json_async(*messages)`); alea-llm-client wraps `args[0]` as a user
   message's *content*. Also `LLMService.json_async` **did not exist** though
   two stages called it — the AttributeError was swallowed by broad excepts.
2. **BUG-6** — OpenAI JSON mode requires the literal word "json" in messages.
3. **BUG-7** — the extraction prompt said "match the ExtractionResult schema"
   without naming any field; the model invented keys; pydantic rejected all of
   it, silently, forever.
4. **BUG-9** — `shared.folio_embeddings` was never provisioned: `ensure_table`
   existed but nothing called it; the lifespan's broad `except` downgraded a
   dead ontology stack to a log line.
5. **BUG-10/11** — code written against an imagined dict API of folio-python:
   `FOLIO.classes` is a `List[OWLClass]`; `search_by_label` returns
   `(OWLClass, score)` tuples. The resolver crashed and a debug-level catch in
   issue_spot zeroed every IRI in every run.

## Why the tests lied

Three fixtures **encoded the wrong external contract**, so the suite verified
the bug:

- `test_llm_service` asserted `chat_async.await_args.args` — the positional
  form that the real client rejects.
- `conftest.mock_folio` exposed `classes` as a **dict** and `search_by_label`
  returning **bare objects** — both wrong.
- Extraction/stage tests mocked `_call_llm_extraction`, so no prompt was ever
  validated against the real schema or a real provider.

## The fixes that generalize

- **Contract tripwire tests:** a source scan failing on `json_async(*` /
  `chat_async(*`; prompt tests asserting required field names appear verbatim
  in structured-output prompts; a real-list-shape test for folio-python.
- **Fixtures must be written FROM the dependency's source, not from memory.**
  When adding a mock for an external API, open the installed package and copy
  the actual return shape into the fixture docstring.
- **Graceful degradation with loud logs:** resolver stages now degrade
  per-stage (deterministic label search survives a dead embedding backend) —
  but at WARNING, not debug. Debug-level catches around integration seams are
  how BUG-11 stayed invisible.
- **One live smoke call beats a thousand mocks:** a 100-token real-provider
  call (`LLMService().acomplete("Reply OK")`) in a pre-deploy checklist would
  have caught BUG-4/6/7 in seconds. instant_on.sh's BUG-3 gate now plays this
  role end-to-end.
- **Startup work that scales with data (18K embeddings) cannot live on the
  boot critical path** — Railway's healthcheck killed the first honest boot.
  Background task + batched upserts (18,325 vectors in 48s).

## Reusable pattern for other repos

Before declaring any LLM-touching feature "code-complete": (1) run one real
call per provider seam on the cheapest model; (2) diff every mock fixture
against the installed dependency's actual signatures; (3) grep for
`except Exception` within two frames of an external call and check the log
level; (4) put a deterministic end-to-end gate (like instant_on's fact-count
check) in the repo so "deployed" and "works" can't diverge silently.
