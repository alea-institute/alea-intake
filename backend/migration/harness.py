#!/usr/bin/env python3
"""Golden-baseline harness for the alea-intake -> folio-resolve migration.

Runs the committed synthetic corpus (``migration/corpus.json``) through alea-intake's
DETERMINISTIC concept-matching seams and writes a capture file. Rerun before and after the
internals swap; ``migration/compare.py`` buckets and classifies the delta.

Seams exercised (all deterministic — $0 LLM spend, no ontology download, no network, no DB):

  1. ``expansion``   -> ``term_expansions.expand_legal_terms`` / ``get_branch_signals``
  2. ``stopword``    -> ``concept_resolver._is_stopword_only``
  3. ``combine``     -> ``concept_resolver._combine_score`` (fixed stage-score tuples)
  4. ``label_score`` -> the Stage-2 label scorer, driven through ``_stage_label_prefix``
                        against a fixed one-candidate stub so the scorer is isolated
  5. ``resolve``     -> ``concept_resolver.resolve_concepts`` end to end (fake FOLIO +
                        fake embedding backend, LLM stage disabled)
  6. ``resolve_no_embed`` -> the same, with the embedding backend raising (BUG-9 cascade)
  7. ``fit``         -> ``semantic_fit.deterministic_unfit_reason`` / ``is_geographic_concept``

Usage::

    .venv/bin/python migration/harness.py --out baseline
    .venv/bin/python migration/harness.py --out candidate

Writes ``migration/captures/<out>.json`` and pins the corpus content hash into it so
``compare.py`` can refuse to diff captures taken from different corpora.
"""

from __future__ import annotations

import argparse
import asyncio
import difflib
import hashlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

# folio-resolve's ``generate_search_terms`` iterates a ``set`` of content words, so term ORDER
# varies between processes under PEP 456 hash randomization (folio-resolve
# docs/migration/SCHEDULE.md, "Findings from the folio-mapper migration"). alea-intake's own
# ``expand_legal_terms`` iterates lists, but Python set iteration also reaches this harness
# through ``_content_words`` ordering in the library scorer, so captures are always taken with a
# pinned hash seed — otherwise real deltas drown in reordering noise.
if os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execv(sys.executable, [sys.executable, *sys.argv])

# Run from anywhere: make ``app`` importable.
BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

# The BUG-9 cascade seam deliberately raises inside the embedding stage; the app logs that at
# WARNING with a traceback. Silence it so a capture run's stdout is just the capture summary.
logging.disable(logging.CRITICAL)

MIGRATION = Path(__file__).resolve().parent
CORPUS_PATH = MIGRATION / "corpus.json"
CAPTURES_DIR = MIGRATION / "captures"

# Fixed knobs so captures are comparable run to run.
TOP_N = 10
MAX_EMBEDDING_CANDIDATES = 20
MAX_LABEL_RESULTS = 10


# ---------------------------------------------------------------------------
# Deterministic offline test doubles (harness-owned; identical before/after the swap)
# ---------------------------------------------------------------------------


class _OWLClass:
    """Minimal stand-in for folio-python's OWLClass."""

    __slots__ = ("iri", "label", "sub_class_of", "definition", "alternative_labels")

    def __init__(self, iri: str, label: str, parent: str | None, definition: str) -> None:
        self.iri = iri
        self.label = label
        self.sub_class_of = [parent] if parent else []
        self.definition = definition
        self.alternative_labels: list[str] = []


class _FakeFOLIO:
    """Offline FOLIO stand-in over the corpus mini-ontology.

    ``search_by_label`` mimics folio-python's fuzzy label search using ``difflib`` (stdlib,
    deterministic) rather than rapidfuzz: the harness only needs a STABLE candidate generator,
    since the seam under test is what alea-intake does with the candidates, not how
    folio-python ranks them.
    """

    def __init__(self, rows: list[dict]) -> None:
        self._by_iri = {
            r["iri"]: _OWLClass(r["iri"], r["label"], r.get("parent"), r.get("definition", ""))
            for r in rows
        }
        self._branch_of = {r["iri"]: r["branch"] for r in rows}
        self._roots: dict[str, list[str]] = {}
        for r in rows:
            if r.get("parent") is None:
                self._roots.setdefault(r["branch"], []).append(r["iri"])

    # -- folio-python container protocol (BUG-10) --------------------------
    def __contains__(self, iri: str) -> bool:
        return iri in self._by_iri

    def __getitem__(self, iri: str) -> _OWLClass:
        return self._by_iri[iri]

    @property
    def classes(self) -> list[_OWLClass]:
        return list(self._by_iri.values())

    # -- branch accessors used by _determine_branch ------------------------
    def _roots_for(self, branch: str) -> list[_OWLClass]:
        return [self._by_iri[i] for i in self._roots.get(branch, [])]

    def get_objectives(self) -> list[_OWLClass]:
        return self._roots_for("Objectives")

    def get_areas_of_law(self) -> list[_OWLClass]:
        return self._roots_for("Area of Law")

    def get_legal_authorities(self) -> list[_OWLClass]:
        return self._roots_for("Legal Authorities")

    def get_locations(self) -> list[_OWLClass]:
        return self._roots_for("Location")

    # -- search seams ------------------------------------------------------
    def search_by_label(self, query: str, limit: int = 10) -> list[tuple[_OWLClass, float]]:
        q = query.lower().strip()
        scored: list[tuple[float, str]] = []
        for iri, cls in self._by_iri.items():
            ratio = difflib.SequenceMatcher(None, q, cls.label.lower()).ratio()
            if ratio >= 0.45:
                scored.append((round(ratio, 6), iri))
        scored.sort(key=lambda t: (-t[0], t[1]))
        return [(self._by_iri[iri], score) for score, iri in scored[:limit]]

    def search_by_prefix(self, text: str) -> list[_OWLClass]:
        t = text.lower().strip()
        return [
            self._by_iri[iri]
            for iri in sorted(self._by_iri)
            if self._by_iri[iri].label.lower().startswith(t)
        ]

    async def parallel_search_by_llm(self, *args: Any, **kwargs: Any) -> list[_OWLClass]:
        raise AssertionError("LLM stage must never run in the migration harness")


class _FakeEmbeddingService:
    """Deterministic stand-in for the pgvector/FAISS embedding backend.

    Scores a query against the mini-ontology with a stdlib token-overlap so the harness never
    downloads a sentence-transformers model. Stable across runs, hence comparable.
    """

    def __init__(self, rows: list[dict], *, fail: bool = False) -> None:
        self._rows = rows
        self._fail = fail

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return {w for w in "".join(c if c.isalnum() else " " for c in text.lower()).split() if w}

    async def search(self, text: str, top_k: int = 10):
        from app.services.embedding.backends import SearchResult

        if self._fail:
            raise RuntimeError("embedding backend unavailable (BUG-9 simulation)")
        q = self._tokens(text)
        out: list[SearchResult] = []
        for r in self._rows:
            if r.get("parent") is None:
                continue  # branch roots are not embedded
            t = self._tokens(r["label"] + " " + r.get("definition", ""))
            if not q or not t:
                continue
            score = len(q & t) / max(len(q | t), 1)
            if score > 0.0:
                out.append(
                    SearchResult(
                        iri=r["iri"],
                        label=r["label"],
                        score=round(score, 6),
                        metadata={"branch": r["branch"]},
                    )
                )
        out.sort(key=lambda r: (-r.score, r.iri))
        return out[:top_k]


# ---------------------------------------------------------------------------
# Environment fingerprint
# ---------------------------------------------------------------------------


def _env() -> dict[str, Any]:
    from app.services.analysis import semantic_fit
    from app.services.folio import concept_resolver

    try:
        import folio_resolve

        present = True
        version = folio_resolve.__version__
        # Is the library merely installed, or actually CONSUMED? Identity of the objects the
        # app binds is the honest test: after the swap the Stage-2 label scorer IS the
        # library's function and the geographic test IS backed by the library's gate.
        consumed = (
            getattr(concept_resolver, "compute_relevance_score", None)
            is folio_resolve.compute_relevance_score
            and isinstance(getattr(semantic_fit, "_PLACE_GATE", None), folio_resolve.PlaceNameGate)
        )
    except ImportError:
        present, version, consumed = False, None, False

    try:
        from importlib.metadata import version as _pkg_version

        folio_python_version = _pkg_version("folio-python")
    except Exception:  # pragma: no cover - metadata is best effort
        folio_python_version = None

    return {
        "folio_resolve_present": present,
        "folio_resolve_consumed": consumed,
        "folio_resolve_version": version,
        "folio_python_version": folio_python_version,
        "top_n": TOP_N,
        "max_embedding_candidates": MAX_EMBEDDING_CANDIDATES,
        "max_label_results": MAX_LABEL_RESULTS,
    }


# ---------------------------------------------------------------------------
# Seams
# ---------------------------------------------------------------------------


def run_expansion(corpus: dict) -> list[dict]:
    from app.services.folio.term_expansions import expand_legal_terms, get_branch_signals

    return [
        {
            "id": item["id"],
            "text": item["text"],
            "category": item["category"],
            "expansions": expand_legal_terms(item["text"]),
            "branch_signals": get_branch_signals(item["text"]),
        }
        for item in corpus["narratives"]
    ]


def run_stopword(corpus: dict) -> list[dict]:
    from app.services.folio.concept_resolver import _is_stopword_only

    return [
        {
            "id": item["id"],
            "text": item["text"],
            "category": item["category"],
            "stopword_only": _is_stopword_only(item["text"]),
        }
        for item in corpus["narratives"]
    ]


def run_combine(corpus: dict) -> list[dict]:
    from app.services.folio.concept_resolver import _combine_score

    return [
        {
            "id": row["id"],
            "embedding": row["embedding"],
            "label": row["label"],
            "llm": row["llm"],
            "combined": round(
                _combine_score(
                    embedding_score=row["embedding"],
                    label_score=row["label"],
                    llm_score=row["llm"],
                ),
                6,
            ),
        }
        for row in corpus["combine"]
    ]


def run_label_score(corpus: dict) -> list[dict]:
    """Isolate the Stage-2 label scorer by feeding it one fixed candidate at a time.

    ``_stage_label_prefix`` is private and takes its candidates from folio-python, so the
    harness stubs a FOLIO that returns exactly the corpus pair — whatever score lands in
    ``candidates[iri]["label_score"]`` is the scorer's output for that (query, label).
    """
    from app.services.folio.concept_resolver import ConceptResolutionConfig, _stage_label_prefix

    class _OnePairFOLIO:
        def __init__(self, label: str) -> None:
            self._cls = _OWLClass("r-pair", label, None, "")

        def search_by_label(self, query: str, limit: int = 10):
            return [(self._cls, 1.0)] if self._cls.label else []

        def search_by_prefix(self, text: str):
            return []

    config = ConceptResolutionConfig(max_label_results=MAX_LABEL_RESULTS)
    out: list[dict] = []
    for pair in corpus["score_pairs"]:
        candidates: dict[str, dict] = {}
        asyncio.run(
            _stage_label_prefix(
                pair["query"],
                [],  # no expansions: the scorer, not the expansion policy, is under test
                _OnePairFOLIO(pair["label"]),
                config,
                candidates,
            )
        )
        score = candidates.get("r-pair", {}).get("label_score")
        out.append(
            {
                "id": pair["id"],
                "query": pair["query"],
                "label": pair["label"],
                "label_score": None if score is None else round(float(score), 6),
            }
        )
    return out


def _resolve_rows(corpus: dict, *, embedding_fails: bool) -> list[dict]:
    from app.services.folio.concept_resolver import ConceptResolutionConfig, resolve_concepts

    folio = _FakeFOLIO(corpus["ontology"])
    embedding = _FakeEmbeddingService(corpus["ontology"], fail=embedding_fails)
    config = ConceptResolutionConfig(
        max_embedding_candidates=MAX_EMBEDDING_CANDIDATES,
        max_label_results=MAX_LABEL_RESULTS,
        enable_llm_stage=False,
    )

    out: list[dict] = []
    for item in corpus["narratives"]:
        results = asyncio.run(
            resolve_concepts(
                text=item["text"],
                folio=folio,
                embedding_service=embedding,
                config=config,
                llm_model=None,
            )
        )
        rows = [
            {
                "iri": r.iri,
                "label": r.label,
                "branch": r.branch,
                "confidence": r.confidence,
                "source": r.source,
            }
            for r in results
        ]
        rows.sort(key=lambda r: (-r["confidence"], r["iri"]))
        out.append(
            {
                "id": item["id"],
                "text": item["text"],
                "category": item["category"],
                "total": len(rows),
                "top": rows[:TOP_N],
            }
        )
    return out


def run_resolve(corpus: dict) -> list[dict]:
    return _resolve_rows(corpus, embedding_fails=False)


def run_resolve_no_embed(corpus: dict) -> list[dict]:
    return _resolve_rows(corpus, embedding_fails=True)


def run_fit(corpus: dict) -> list[dict]:
    from app.services.analysis.semantic_fit import (
        FitItem,
        SemanticFitValidator,
        deterministic_unfit_reason,
        is_geographic_concept,
    )

    validator = SemanticFitValidator(llm_service=None)
    items = [
        FitItem(
            key=row["id"],
            claim_name=row["claim_name"],
            concept_label=row["label"],
            branch=row["branch"] or "",
            confidence=row["confidence"],
        )
        for row in corpus["fit"]
    ]
    verdicts = validator.apply_deterministic(items)

    out: list[dict] = []
    for row in corpus["fit"]:
        verdict = verdicts.get(row["id"])
        out.append(
            {
                "id": row["id"],
                "claim_name": row["claim_name"],
                "label": row["label"],
                "branch": row["branch"],
                "category": row["category"],
                "geographic": is_geographic_concept(row["label"], row["branch"]),
                "unfit_reason": deterministic_unfit_reason(row["label"], row["branch"]),
                "rejected": verdict is not None,
                "adjusted_confidence": (
                    None if verdict is None else round(verdict.adjusted_confidence, 6)
                ),
            }
        )
    return out


# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, help="capture name, e.g. baseline / candidate")
    args = parser.parse_args()

    raw = CORPUS_PATH.read_bytes()
    corpus = json.loads(raw)

    capture = {
        "corpus_hash": hashlib.sha256(raw).hexdigest(),
        "corpus_version": corpus.get("version"),
        "env": _env(),
        "expansion": run_expansion(corpus),
        "stopword": run_stopword(corpus),
        "combine": run_combine(corpus),
        "label_score": run_label_score(corpus),
        "resolve": run_resolve(corpus),
        "resolve_no_embed": run_resolve_no_embed(corpus),
        "fit": run_fit(corpus),
    }

    CAPTURES_DIR.mkdir(parents=True, exist_ok=True)
    out_path = CAPTURES_DIR / f"{args.out}.json"
    out_path.write_text(json.dumps(capture, indent=2, sort_keys=True) + "\n")
    print(f"wrote {out_path}")
    print(f"  corpus_hash    {capture['corpus_hash'][:16]}…")
    print(f"  folio_resolve  {capture['env']['folio_resolve_version'] or 'absent'} "
          f"(consumed={capture['env']['folio_resolve_consumed']})")
    print(f"  resolve rows   {sum(r['total'] for r in capture['resolve'])}")
    print(f"  rejected fits  {sum(1 for r in capture['fit'] if r['rejected'])}/{len(capture['fit'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
