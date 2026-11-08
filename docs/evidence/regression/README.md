# Regression replay

Run with the backend virtualenv, from the repository root:

```sh
PYTHONHASHSEED=0 backend/.venv/bin/python scripts/regression_replay.py
```

The harness loads each `*/narrative.txt` under
`docs/evidence/persona-campaign/personas/`, plus its `src/*.txt` document
transcriptions. Each persona gets an isolated in-memory SQLite database.
Messages go through the existing fact backfill, analysis orchestrator, and
separate deadline detection stage. No server, external database, or provider
connection is needed for replay. The deadline reference date is fixed to
2026-11-08 so relative dates and prompt hashes stay reproducible.

Provider construction is redirected only inside this command's replay context,
through `LLMService.create_client`. The bridge covers the stages' legacy direct
provider imports without changing stage code. Missing responses fail closed,
including when a production stage catches the exception: the command exits
nonzero and names the stage and SHA-256 prompt hash. JSON recordings live in
`recordings/<hash>.json`. The hash covers the model, provider, and ordered
messages including system instructions. JSON key order and separate versus
inline system-message transport are normalized; meaningful text whitespace is
preserved. Replay never writes recordings.

A live recording requires an operator to provide `REGRESSION_OPERATOR_KEY` in
the environment explicitly, with an approved key and budget. There is no
fallback to a default or server key. The key is passed directly to clients and
is excluded from recording identities and artifacts. Do not put keys in command
arguments or shell history. Once the environment is provisioned:

```sh
PYTHONHASHSEED=0 backend/.venv/bin/python scripts/regression_replay.py --record --provider openai --model gpt-4
```

Recording mode refreshes every encountered response. A prompt change produces a
new hash and requires a recording for that prompt. Recording alone does not
accept changed outputs: the command still compares against the baseline and
returns nonzero on losses or changed prompts. To accept reviewed changes, replay
the completed recordings with an explicit explanation:

```sh
PYTHONHASHSEED=0 backend/.venv/bin/python scripts/regression_replay.py --accept --reason 'Reviewed the changed analysis and supporting evidence'
```

Use the same provider/model flags for record, replay, and acceptance. Acceptance
stores the reason, UTC timestamp, before/after prompt manifests (including full
prompt text), and additions/losses in every output category in that persona's
baseline history. Review this diff before integration. Loss of any issue, FOLIO
IRI, deadline, or citation fails ordinary replay; additions are reported and do
not fail. Prompt changes require explicit acceptance even when outputs match.
The comparison ignores database IDs and ordering. Deadlines retain the computed
date, trigger, event, rule, and jurisdiction; citations include both research
authorities and deadline citations.

`--personas`, `--recordings`, and `--baseline` select alternate corpus directories
for harness tests. Baselines live in `baseline/<persona>.json`. A missing
baseline fails; only `--accept` creates or updates one.

## Current evidence boundary

The committed `synthetic-worker` baseline and recording exercise only the real
issue-spotting stage's LLM boundary in offline harness tests. They are explicitly
synthetic, not accepted live persona results. They do not make the default
8-persona campaign pass: live recordings and accepted baselines still require
an operator key and review. Run the harness self-tests from `backend/`:

```sh
PYTHONPATH=. .venv/bin/python -m pytest tests/regression/ -q -p no:cacheprovider
```

The command currently runs without FOLIO/embedding singletons or external
research adapters, matching the backend's supported optional-dependency path.
It compares IRIs emitted by the pipeline and citations actually produced; it
does not establish ontology resolution quality or external research coverage.
Live deployment adjudication must additionally resolve IRIs and run the
existing FOLIO, memo, export-integrity, and answer-key deadline checks. Synthetic
self-tests are not substitutes for those checks or browser UAT.
