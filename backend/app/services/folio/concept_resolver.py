"""Multi-stage concept resolution pipeline.

Maps consumer narrative text to FOLIO concept IRIs across all branches using
a three-stage pipeline:
  1. Embedding similarity (fast, broad recall)
  2. Label/prefix search (exact + fuzzy matching)
  3. LLM semantic matching (only if no high-confidence match)

Domain-aware term expansions enrich queries before resolution.
Combined confidence scoring ranks results from all stages.

**Stage 2 scoring comes from the shared `folio-resolve` library.** It used to be a
hand-rolled set-intersection ratio local to this module
(``common / max(len(query_words), len(label_words))`` with a flat ``0.9`` substring
constant and a flat ``0.7`` prefix constant), which was blind to word order
("rules of arbitration" != "Arbitration Rules"), blind to morphology
("arbitrating" scored 0 against "Arbitration Rules"), and had no specificity
penalty (one-word "custody" scored 0.9 against "Child Custody Determination").
``folio_resolve.compute_relevance_score`` is the canonical word-order-invariant
scorer those three defects are fixed in; see ``backend/migration/`` for the
golden-baseline harness and the classified delta that guard the swap.

Two stopword vocabularies coexist on purpose, because they do different jobs:

* ``term_expansions.SEARCH_STOPWORDS`` — consumer-narrative *query construction*
  (drops first/second-person pronouns and auxiliaries so "I was fired from my job"
  becomes a usable query, and short-circuits stopword-only input). Local seam.
* ``folio_resolve.SEARCH_STOPWORDS`` — *scoring* (drops legal filler like "law",
  "legal", "type" that would otherwise inflate overlap against FOLIO labels).
  Owned by the library, applied inside ``compute_relevance_score``.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from folio_resolve import compute_relevance_score, content_words

from app.services.embedding.backends import SearchResult
from app.services.folio.term_expansions import (
    SEARCH_STOPWORDS,
    expand_legal_terms,
    get_branch_signals,
)

if TYPE_CHECKING:
    from folio import FOLIO
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.services.embedding.service import EmbeddingService

logger = logging.getLogger(__name__)

# Score combination weights
EMBEDDING_WEIGHT: float = 0.3
LABEL_WEIGHT: float = 0.3
LLM_WEIGHT: float = 0.4

# Penalty multiplier for concepts appearing in only one stage
SINGLE_STAGE_PENALTY: float = 0.7


@dataclass
class ResolvedConcept:
    """A resolved FOLIO concept with confidence metadata."""

    iri: str
    label: str
    branch: str
    confidence: float
    source: str  # "embedding", "label_match", "llm", "combined"
    matched_text: str
    is_unmapped: bool = False
    reason: str = ""  # LLM's explanation (from search_by_llm include_reason=True)


@dataclass
class ConceptResolutionConfig:
    """Configuration for the concept resolution pipeline."""

    confidence_threshold: float = 0.5
    high_confidence_threshold: float = 0.85
    max_embedding_candidates: int = 20
    max_label_results: int = 10
    max_llm_results: int = 10
    enable_llm_stage: bool = True


def _combine_score(
    embedding_score: float | None = None,
    label_score: float | None = None,
    llm_score: float | None = None,
) -> float:
    """Combine scores from multiple stages with weights.

    Each score should be normalized to 0.0-1.0 range.
    Concepts appearing in multiple stages get weighted average.
    Concepts in only one stage get a penalty.
    """
    stages: list[tuple[float, float]] = []
    if embedding_score is not None:
        stages.append((embedding_score, EMBEDDING_WEIGHT))
    if label_score is not None:
        stages.append((label_score, LABEL_WEIGHT))
    if llm_score is not None:
        stages.append((llm_score, LLM_WEIGHT))

    if not stages:
        return 0.0

    # Weighted average
    total_weight = sum(w for _, w in stages)
    weighted_sum = sum(s * w for s, w in stages)
    combined = weighted_sum / total_weight

    # Apply penalty if concept appeared in only one stage
    if len(stages) == 1:
        combined *= SINGLE_STAGE_PENALTY

    return combined


def _determine_branch(iri: str, folio: FOLIO, metadata: dict | None = None) -> str:
    """Determine which top-level FOLIO branch a concept belongs to.

    Checks metadata first (from embedding backend), then walks the
    sub_class_of hierarchy to find a known branch root.
    """
    # Fast path: metadata from embedding backend
    if metadata and metadata.get("branch"):
        return metadata["branch"]

    from app.services.folio.folio_service import get_owl_class

    if get_owl_class(folio, iri) is None:
        return "Unknown"

    # Build branch root IRI set lazily
    branch_methods = {
        "Objectives": "get_objectives",
        "Area of Law": "get_areas_of_law",
        "Legal Authorities": "get_legal_authorities",
        "Location": "get_locations",
    }

    branch_root_iris: dict[str, str] = {}
    for branch_name, method_name in branch_methods.items():
        method = getattr(folio, method_name, None)
        if method:
            for cls in method():
                branch_root_iris[cls.iri] = branch_name

    # Walk up the hierarchy
    visited: set[str] = set()
    current_iris = [iri]
    while current_iris:
        next_iris: list[str] = []
        for current_iri in current_iris:
            if current_iri in visited:
                continue
            visited.add(current_iri)

            if current_iri in branch_root_iris:
                return branch_root_iris[current_iri]

            current_cls = get_owl_class(folio, current_iri)
            if current_cls is None:
                continue
            next_iris.extend(current_cls.sub_class_of)
        current_iris = next_iris

    return "Unknown"


def _as_text(value) -> str:
    """Return ``value`` if it is a non-empty string, else ""."""
    return value if isinstance(value, str) else ""


def _label_match_score(query: str, owl_cls) -> float:
    """Score a label-search candidate 0.0-1.0 with the shared library scorer.

    Delegates to ``folio_resolve.compute_relevance_score`` (0-100, word-order-invariant,
    prefix-match credit, specificity penalty) and normalizes to this module's 0.0-1.0 stage
    scale. Alternative labels are passed as synonyms — they are label evidence, and Stage 2
    is the label stage.

    The concept *definition* is deliberately NOT passed: definitional/semantic similarity is
    Stage 1's job (embeddings), and letting a definition alone produce a Stage-2 hit would
    manufacture label matches that share no label token at all.
    """
    # Type guards, not paranoia: folio-python may hand back ``None`` for an absent
    # preferred label, and test doubles hand back MagicMocks for any attribute that is
    # merely *touched*. The library scorer feeds these straight into ``re.findall`` and
    # raises TypeError on anything that is not a str, so coerce at this boundary.
    label = _as_text(getattr(owl_cls, "label", None))
    preferred = _as_text(getattr(owl_cls, "preferred_label", None)) or None
    raw_synonyms = getattr(owl_cls, "alternative_labels", None)
    synonyms = [s for s in raw_synonyms if isinstance(s, str) and s] if isinstance(raw_synonyms, (list, tuple)) else []
    score = compute_relevance_score(
        content_words(query),
        query,
        label,
        None,
        synonyms,
        preferred_label=preferred,
    )
    return score / 100.0


def _is_stopword_only(text: str) -> bool:
    """Check if text contains only stopwords."""
    words = text.lower().split()
    clean_words = [
        w.strip(".,!?;:'\"()[]{}").lower()
        for w in words
        if w.strip(".,!?;:'\"()[]{}").lower() not in SEARCH_STOPWORDS
        and w.strip(".,!?;:'\"()[]{}") != ""
    ]
    return len(clean_words) == 0


async def resolve_concepts(
    text: str,
    folio: FOLIO,
    embedding_service: EmbeddingService,
    config: ConceptResolutionConfig | None = None,
    llm_model=None,
) -> list[ResolvedConcept]:
    """Resolve consumer text to FOLIO concepts via multi-stage pipeline.

    Stage 1: Embedding similarity (fast, broad recall)
    Stage 2: Label/prefix search (exact + fuzzy matching)
    Stage 3: LLM semantic matching (only if no high-confidence match)

    Args:
        text: Consumer narrative text to resolve.
        folio: FOLIO instance with loaded ontology.
        embedding_service: EmbeddingService for vector search.
        config: Resolution configuration. Uses defaults if None.
        llm_model: Optional alea_llm_client BaseAIModel for LLM stage.

    Returns:
        List of ResolvedConcept sorted by confidence descending.
    """
    if config is None:
        config = ConceptResolutionConfig()

    # Pre-processing: filter empty / stopword-only text
    if not text or not text.strip():
        return []
    if _is_stopword_only(text):
        return []

    # Expand legal terms for enriched search
    expanded_queries = expand_legal_terms(text)
    branch_signals = get_branch_signals(text)

    # Candidate accumulator: iri -> {embedding_score, label_score, llm_score, label, metadata, reason}
    candidates: dict[str, dict] = {}

    # Stage 1: Embedding similarity. Degrade gracefully: an unavailable
    # embedding backend (e.g. missing pgvector table, BUG-9) must not take
    # down the deterministic label/prefix stage below — the cascade is the
    # point (deterministic-first, probabilistic assist).
    try:
        await _stage_embedding(text, expanded_queries, embedding_service, config, candidates)
    except Exception:
        logger.warning("Embedding stage failed; continuing with label/LLM stages", exc_info=True)

    # Stage 2: Label/prefix search
    await _stage_label_prefix(text, expanded_queries, folio, config, candidates)

    # Stage 3: LLM semantic matching (conditional)
    has_high_confidence = any(
        _combine_score(
            embedding_score=c.get("embedding_score"),
            label_score=c.get("label_score"),
        )
        > config.high_confidence_threshold
        for c in candidates.values()
    )

    if (
        not has_high_confidence
        and config.enable_llm_stage
        and llm_model is not None
    ):
        try:
            await _stage_llm(text, folio, config, candidates)
        except Exception:
            logger.warning("LLM stage failed; ranking existing candidates", exc_info=True)

    # Scoring and ranking
    results = _combine_and_rank(candidates, folio, text, config)

    return results


async def _stage_embedding(
    text: str,
    expanded_queries: list[str],
    embedding_service: EmbeddingService,
    config: ConceptResolutionConfig,
    candidates: dict[str, dict],
) -> None:
    """Stage 1: Embedding similarity search."""
    # Search with original text
    results = await embedding_service.search(text, top_k=config.max_embedding_candidates)
    for r in results:
        if r.iri not in candidates:
            candidates[r.iri] = {
                "label": r.label,
                "metadata": r.metadata,
            }
        candidates[r.iri]["embedding_score"] = max(
            r.score, candidates[r.iri].get("embedding_score", 0.0)
        )

    # Also search expanded queries and merge (take highest score)
    for query in expanded_queries[:5]:  # Limit to avoid too many searches
        exp_results = await embedding_service.search(
            query, top_k=config.max_embedding_candidates // 2
        )
        for r in exp_results:
            if r.iri not in candidates:
                candidates[r.iri] = {
                    "label": r.label,
                    "metadata": r.metadata,
                }
            candidates[r.iri]["embedding_score"] = max(
                r.score, candidates[r.iri].get("embedding_score", 0.0)
            )


async def _stage_label_prefix(
    text: str,
    expanded_queries: list[str],
    folio: FOLIO,
    config: ConceptResolutionConfig,
    candidates: dict[str, dict],
) -> None:
    """Stage 2: Label and prefix search using folio-python."""
    loop = asyncio.get_event_loop()

    # Search with original text and expanded queries
    queries = [text] + expanded_queries[:5]
    for query in queries:
        try:
            label_results = await loop.run_in_executor(
                None,
                lambda q=query: folio.search_by_label(q, limit=config.max_label_results),
            )
        except Exception:
            label_results = []

        for item in label_results:
            # Real folio-python returns List[Tuple[OWLClass, score]] (BUG-11);
            # accept bare OWLClass for test doubles.
            owl_cls = item[0] if isinstance(item, tuple) else item
            if owl_cls is None or not getattr(owl_cls, "label", None):
                continue
            iri = owl_cls.iri
            if iri not in candidates:
                candidates[iri] = {
                    "label": owl_cls.label,
                    "metadata": None,
                }
            candidates[iri]["label_score"] = max(
                _label_match_score(query, owl_cls),
                candidates[iri].get("label_score", 0.0),
            )

    # Prefix search if text is long enough
    if len(text.strip()) >= 3:
        try:
            prefix_results = await loop.run_in_executor(
                None, lambda: folio.search_by_prefix(text.strip())
            )
        except Exception:
            prefix_results = []

        for owl_cls in prefix_results:
            owl_cls = owl_cls[0] if isinstance(owl_cls, tuple) else owl_cls
            if owl_cls is None or not getattr(owl_cls, "label", None):
                continue
            iri = owl_cls.iri
            if iri not in candidates:
                candidates[iri] = {
                    "label": owl_cls.label,
                    "metadata": None,
                }
            # Prefix hits are scored on their evidence like every other label candidate.
            # They used to get a flat 0.7 constant, which was simultaneously too generous
            # (a 40-character label that merely starts with the query) and too stingy (an
            # exact-label prefix hit could never clear the 0.5 bar on its own, because
            # 0.7 * SINGLE_STAGE_PENALTY = 0.49).
            candidates[iri]["label_score"] = max(
                _label_match_score(text.strip(), owl_cls),
                candidates[iri].get("label_score", 0.0),
            )


async def _stage_llm(
    text: str,
    folio: FOLIO,
    config: ConceptResolutionConfig,
    candidates: dict[str, dict],
) -> None:
    """Stage 3: LLM semantic matching (only when no high-confidence match)."""
    try:
        llm_results = await folio.parallel_search_by_llm(
            text,
            limit=config.max_llm_results,
            include_reason=True,
        )
    except Exception as e:
        logger.warning("LLM search failed: %s", e)
        return

    for owl_cls in llm_results:
        iri = owl_cls.iri
        if iri not in candidates:
            candidates[iri] = {
                "label": owl_cls.label,
                "metadata": None,
            }

        # Normalize LLM relevance score (1-10 scale) to 0-1
        relevance = getattr(owl_cls, "relevance", 5)
        if isinstance(relevance, (int, float)):
            normalized_score = max(0.0, min(1.0, relevance / 10.0))
        else:
            normalized_score = 0.5

        candidates[iri]["llm_score"] = max(
            normalized_score, candidates[iri].get("llm_score", 0.0)
        )

        reason = getattr(owl_cls, "reason", "")
        if reason:
            candidates[iri]["reason"] = reason


def _combine_and_rank(
    candidates: dict[str, dict],
    folio: FOLIO,
    original_text: str,
    config: ConceptResolutionConfig,
) -> list[ResolvedConcept]:
    """Combine scores from all stages and rank results."""
    results: list[ResolvedConcept] = []

    for iri, data in candidates.items():
        combined = _combine_score(
            embedding_score=data.get("embedding_score"),
            label_score=data.get("label_score"),
            llm_score=data.get("llm_score"),
        )

        # Filter below threshold
        if combined < config.confidence_threshold:
            continue

        # Determine source
        sources = []
        if data.get("embedding_score") is not None:
            sources.append("embedding")
        if data.get("label_score") is not None:
            sources.append("label_match")
        if data.get("llm_score") is not None:
            sources.append("llm")
        source = "combined" if len(sources) > 1 else (sources[0] if sources else "unknown")

        # Determine branch
        branch = _determine_branch(iri, folio, data.get("metadata"))

        results.append(
            ResolvedConcept(
                iri=iri,
                label=data.get("label", ""),
                branch=branch,
                confidence=round(combined, 4),
                source=source,
                matched_text=original_text,
                reason=data.get("reason", ""),
            )
        )

    # Sort by confidence descending
    results.sort(key=lambda r: r.confidence, reverse=True)

    return results


async def persist_resolutions(
    session: AsyncSession,
    intake_id: int,
    resolutions: list[ResolvedConcept],
) -> list:
    """Persist resolved concepts as ConceptMapping records.

    Args:
        session: Async database session.
        intake_id: ID of the intake these concepts relate to.
        resolutions: List of resolved concepts to persist.

    Returns:
        List of created ConceptMapping objects.
    """
    from app.models.folio_concepts import ConceptMapping

    mappings = []
    for r in resolutions:
        mapping = ConceptMapping(
            intake_id=intake_id,
            iri=r.iri,
            label=r.label,
            branch=r.branch,
            confidence=r.confidence,
            matched_text=r.matched_text,
            source=r.source,
            is_unmapped=r.is_unmapped,
            metadata_json={"reason": r.reason} if r.reason else None,
        )
        session.add(mapping)
        mappings.append(mapping)
    await session.flush()
    return mappings
