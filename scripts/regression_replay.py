#!/usr/bin/env python3
"""Deterministic in-process persona replay; no unrecorded LLM calls in replay mode."""
from __future__ import annotations

import argparse
import asyncio
from contextlib import ExitStack, contextmanager
from datetime import date, datetime, timezone
import hashlib
import inspect
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
CATEGORIES = ("issues", "folio_iris", "deadlines", "citations")


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def prompt_identity(provider, model, messages, system_prompt=None):
    # Normalize transport representation, preserving meaningful prompt whitespace.
    messages = list(messages)
    if system_prompt:
        messages.insert(0, {"role": "system", "content": system_prompt})
    prompt = {"provider": provider, "model": model, "messages": messages}
    return hashlib.sha256(canonical(prompt).encode()).hexdigest(), prompt


class MissingRecording(RuntimeError):
    pass


class RecordingStore:
    def __init__(self, directory, *, record=False, operator_key=None):
        if record and not operator_key:
            raise ValueError("Recording requires an explicit operator key")
        self.directory = Path(directory)
        self.record = record
        self.operator_key = operator_key
        self.prompts = []
        self.errors = []

    def client(self, stage, provider, model, live=None):
        store = self

        class Client:
            async def _call(self, method, *, messages, system_prompt=None, **kwargs):
                digest, prompt = prompt_identity(provider, model, messages, system_prompt)
                store.prompts.append({"stage": stage, "hash": digest, "prompt": prompt})
                path = store.directory / f"{digest}.json"
                if store.record:
                    try:
                        response = await getattr(live, method)(messages=prompt["messages"], **kwargs)
                    except Exception as error:
                        store.errors.append(error)
                        raise
                    payload = {"data": getattr(response, "data", None), "text": getattr(response, "text", "")}
                    store.directory.mkdir(parents=True, exist_ok=True)
                    path.write_text(json.dumps({"prompt": prompt, "response": payload}, indent=2) + "\n")
                else:
                    try:
                        if not path.exists():
                            raise MissingRecording(f"Missing recording: stage {stage}, prompt hash {digest}")
                        recording = json.loads(path.read_text())
                        if recording["prompt"] != prompt:
                            raise ValueError(f"Recording identity mismatch: stage {stage}, prompt hash {digest}")
                        payload = recording["response"]
                        if not {"data", "text"} <= payload.keys():
                            raise ValueError(f"Incomplete recording: stage {stage}, prompt hash {digest}")
                    except (OSError, ValueError, KeyError, TypeError, MissingRecording) as error:
                        store.errors.append(error)
                        raise
                return SimpleNamespace(**payload)

            async def json_async(self, **kwargs):
                return await self._call("json_async", **kwargs)

            async def chat_async(self, **kwargs):
                return await self._call("chat_async", **kwargs)

        return Client()

    def check(self):
        # Production stages sometimes swallow provider exceptions. They must not
        # make a missing recording look like a successful, empty analysis.
        if self.errors:
            raise self.errors[0]


@contextmanager
def recorded_clients(store, service):
    """Replay service clients and exploration's remaining direct constructors."""
    import alea_llm_client
    from app.services.llm_service import LLMService, _PROVIDER_MODEL_MAP, replay_client_factory

    originals = dict(_PROVIDER_MODEL_MAP)

    def factory(provider, model, kwargs):
        stage = "llm_service"
        for frame in inspect.stack():
            module = frame.frame.f_globals.get("__name__", "")
            if module.startswith(("app.services.analysis.stages.", "app.services.extraction.")):
                stage = module.rsplit(".", 1)[-1]
                break
        live = None
        if store.record:
            live = originals[provider](**{**kwargs, "api_key": store.operator_key})
        return store.client(stage, provider, model, live)

    def constructor(provider):
        # Exploration still constructs providers directly, including its cheap model.
        return lambda **kwargs: LLMService(
            api_key=kwargs.get("api_key"), provider=provider, model=kwargs.get("model")
        ).create_client()

    with replay_client_factory(factory), ExitStack() as stack:
        for provider, name in (("openai", "OpenAIModel"), ("anthropic", "AnthropicModel"),
                               ("google", "GoogleModel"), ("vllm", "VLLMModel")):
            stack.enter_context(patch.object(alea_llm_client, name, constructor(provider)))
        yield
    store.check()


def compare(before, after):
    result = {"lost": {}, "added": {}}
    for category in CATEGORIES:
        old = {canonical(v): v for v in before[category]}
        new = {canonical(v): v for v in after[category]}
        result["lost"][category] = [old[k] for k in sorted(old.keys() - new.keys())]
        result["added"][category] = [new[k] for k in sorted(new.keys() - old.keys())]
    return result


def passes(diff):
    return not any(diff["lost"].values())


def accept(path, snapshot, prompts, reason):
    if not reason.strip():
        raise ValueError("Baseline acceptance requires a nonempty reason")
    previous = json.loads(path.read_text()) if path.exists() else {
        "snapshot": {key: [] for key in CATEGORIES}, "prompts": [], "history": []}
    history = previous["history"] + [{
        "accepted_at": datetime.now(timezone.utc).isoformat(), "reason": reason,
        "prompt_diff": {"before": previous["prompts"], "after": prompts},
        "issue_diff": compare(previous["snapshot"], snapshot),
    }]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"snapshot": snapshot, "prompts": prompts, "history": history}, indent=2) + "\n")


async def run_persona(persona, store, service, *, today=date(2026, 11, 8), folio=None):
    """Use a fresh SQLite database per narrative; persist the real stages' outputs."""
    import app.models  # Register the application's table metadata.
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from app.db.base import TenantBase, SharedBase
    from app.models.intake import IntakeSession, Message
    from app.services.extraction.backfill import backfill_intake_facts
    from app.models.analysis import AnalysisClaim, AnalysisStage
    from app.models.research import Authority
    from app.services.analysis.orchestrator import AnalysisOrchestrator
    from app.services.analysis.stages.deadline_detect import DeadlineDetectStage

    engine = create_async_engine("sqlite+aiosqlite://", execution_options={
        "schema_translate_map": {"tenant": None, "shared": None}})
    try:
        async with engine.begin() as connection:
            await connection.run_sync(SharedBase.metadata.create_all)
            await connection.run_sync(TenantBase.metadata.create_all)
        async with AsyncSession(engine, expire_on_commit=False) as session:
            session.add(IntakeSession(id=1, intake_id=1))
            sources = [persona / "narrative.txt", *sorted((persona / "src").glob("*.txt"))]
            for sequence, source in enumerate(sources):
                session.add(Message(session_id=1, sender_type="consumer", modality="text",
                    normalized_text=source.read_bytes(), sequence_number=sequence))
            await session.flush()
            with recorded_clients(store, service):
                await backfill_intake_facts(session, 1, service, folio=folio)
                orchestrator = AnalysisOrchestrator(session, service, folio=folio)
                run = await orchestrator.run(intake_id=1, session_id=1)
                deadlines = await DeadlineDetectStage(service, session).detect_and_persist(
                    intake_id=1, run_id=run.id, today=today)
            stages = (await session.execute(select(AnalysisStage))).scalars().all()
            errors = [s.stage_name for s in stages if (s.result_json or {}).get("error")]
            if errors:
                raise RuntimeError(f"Analysis stages failed: {', '.join(errors)}")
            claims = (await session.execute(select(AnalysisClaim))).scalars().all()
            authorities = (await session.execute(select(Authority))).scalars().all()
            return {
                "issues": sorted({c.claim_name for c in claims}),
                "folio_iris": sorted({c.folio_iri for c in claims if c.folio_iri}),
                "deadlines": sorted([{"date": d.computed_date.isoformat() if d.computed_date else None,
                    "trigger": d.trigger, "event": d.event_text, "rule": d.rule_id,
                    "jurisdiction": d.jurisdiction} for d in deadlines], key=canonical),
                "citations": sorted({a.citation for a in authorities if a.citation} |
                                    {d.citation for d in deadlines if d.citation}),
            }
    finally:
        await engine.dispose()


async def main_async(args):
    # Never construct a live provider unless --record supplied a dedicated key.
    store = RecordingStore(args.recordings, record=args.record,
                           operator_key=os.environ.get("REGRESSION_OPERATOR_KEY") if args.record else None)
    import logging
    with patch("logging.handlers.RotatingFileHandler", return_value=logging.NullHandler()):
        from app.services.llm_service import LLMService
    service = LLMService(api_key="replay-no-network", provider=args.provider, model=args.model)
    personas = sorted(args.personas.glob("*/narrative.txt"))
    if not personas:
        raise ValueError(f"No persona narratives in {args.personas}")
    failed = False
    for narrative in personas:
        store.prompts = []
        snapshot = await run_persona(narrative.parent, store, service)
        path = args.baseline / f"{narrative.parent.name}.json"
        if args.accept:
            accept(path, snapshot, store.prompts, args.reason)
            print(f"{narrative.parent.name}: baseline accepted")
            continue
        if not path.exists():
            raise ValueError(f"Missing accepted baseline for {narrative.parent.name}; use --accept --reason")
        baseline = json.loads(path.read_text())
        diff = compare(baseline["snapshot"], snapshot)
        prompt_changed = baseline["prompts"] != store.prompts
        print(json.dumps({"persona": narrative.parent.name, **diff, "prompt_changed": prompt_changed}))
        failed |= not passes(diff) or prompt_changed
    return int(failed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", action="store_true")
    parser.add_argument("--accept", action="store_true")
    parser.add_argument("--reason", default="")
    parser.add_argument("--personas", type=Path, default=ROOT / "docs/evidence/persona-campaign/personas")
    parser.add_argument("--recordings", type=Path, default=ROOT / "docs/evidence/regression/recordings")
    parser.add_argument("--baseline", type=Path, default=ROOT / "docs/evidence/regression/baseline")
    parser.add_argument("--provider", default="openai")
    parser.add_argument("--model", default="gpt-4")
    args = parser.parse_args()
    if args.accept and not args.reason.strip():
        parser.error("--accept requires --reason")
    try:
        return asyncio.run(main_async(args))
    except (MissingRecording, ValueError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
