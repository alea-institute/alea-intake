"""Multi-stage concept resolution pipeline.

Maps consumer narrative text to FOLIO concept IRIs across all branches using
a three-stage pipeline:
  1. Embedding similarity (fast, broad recall)
  2. Label/prefix search (exact + fuzzy matching)
  3. LLM semantic matching (only if no high-confidence match)

Domain-aware term expansions enrich queries before resolution.
Combined confidence scoring ranks results from all stages.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

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

    if iri not in folio.classes:
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

            current_cls = folio.classes.get(current_iri)
            if current_cls is None:
                continue
            next_iris.extend(current_cls.sub_class_of)
        current_iris = next_iris

    return "Unknown"


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

        for owl_cls in label_results:
            iri = owl_cls.iri
            if iri not in candidates:
                candidates[iri] = {
                    "label": owl_cls.label,
                    "metadata": None,
                }
            # Compute label match ratio (simple substring ratio)
            label_lower = owl_cls.label.lower()
            query_lower = query.lower()
            if query_lower in label_lower or label_lower in query_lower:
                match_ratio = 0.9
            else:
                # Partial overlap ratio
                common = len(set(query_lower.split()) & set(label_lower.split()))
                total = max(len(query_lower.split()), len(label_lower.split()), 1)
                match_ratio = common / total

            candidates[iri]["label_score"] = max(
                match_ratio, candidates[iri].get("label_score", 0.0)
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
            iri = owl_cls.iri
            if iri not in candidates:
                candidates[iri] = {
                    "label": owl_cls.label,
                    "metadata": None,
                }
            candidates[iri]["label_score"] = max(
                0.7, candidates[iri].get("label_score", 0.0)
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
