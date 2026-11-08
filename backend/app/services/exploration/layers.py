"""Four exploration layer implementations for the three-layer exploration engine.

Each layer is an async function returning list[ExplorationResult]:
  1. layer_folio_adjacency: FOLIO graph traversal for adjacent concepts
  2. layer_protocol_match: Curated screening protocol trigger matching
  3. layer_cheap_llm: Fast/cheap LLM reasoning scan
  4. layer_expensive_llm: Deep/expensive LLM reasoning with FOLIO + protocol context

Layers are composed by ExplorationEngine via asyncio.gather for hybrid parallel
execution per D-05.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from app.services.exploration.schemas import ExplorationConfig, ExplorationResult
from app.services.llm_bounds import TERSE_JSON_RULES

if TYPE_CHECKING:
    from folio import FOLIO

    from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)


# Output bounds (2026-11-08 live run): the model emitted a placeholder object,
# then "Correction: ..." and the real JSON, so the reply never parsed and the
# layer returned nothing. Forbid that shape, cap the list, retry once compactly.
MAX_EXPLORATION_ISSUES = 8
COMPACT_EXPLORATION_ISSUES = 4
ISSUES_REPLY_RULES = (
    f"Return at most {MAX_EXPLORATION_ISSUES} issues, the most important first. "
    "Each description and rationale is one sentence under 25 words. "
    + TERSE_JSON_RULES
)


async def _bounded_issues(model: Any, messages: list[dict], source_layer: str) -> list[ExplorationResult]:
    """Call the model at most twice and convert its issues to results."""
    from app.services.llm_bounds import (
        bounded_call,
        compact_instruction,
        limit_client_retries,
        list_field,
    )

    limit_client_retries(model)

    async def call(compact: bool) -> Any:
        sent = list(messages)
        if compact:
            sent.append({"role": "system", "content": compact_instruction(COMPACT_EXPLORATION_ISSUES)})
        response = await model.json_async(messages=sent)
        return response.data

    issues = await bounded_call(
        call, lambda raw: list_field(raw, "issues"), stage=source_layer, default=[]
    )
    results: list[ExplorationResult] = []
    for issue in issues[:MAX_EXPLORATION_ISSUES]:
        if not isinstance(issue, dict):
            continue
        try:
            confidence = min(1.0, max(0.0, float(issue.get("confidence", 0.5))))
        except (TypeError, ValueError):
            confidence = 0.5
        results.append(ExplorationResult(
            description=str(issue.get("description") or ""),
            folio_iri=None,
            source_layer=source_layer,
            confidence=confidence,
            is_new_issue=True,
            claim_name=str(issue.get("claim_name") or "Unknown"),
            rationale=str(issue.get("rationale") or ""),
        ))
    return results


def _create_llm_model(llm_service: LLMService, cheap: bool = False, org_config: dict | None = None) -> Any:
    """Create an alea-llm-client model instance from LLMService config.

    Args:
        llm_service: The LLM service with provider configuration.
        cheap: If True, use cheap/fast model from ExplorationConfig if available.
        org_config: Org config dict that may contain exploration.cheap_llm_provider/model.

    Returns:
        An alea-llm-client model instance ready for json_async calls.
    """
    from app.services.llm_service import LLMService

    config = llm_service.get_client_config()

    # Override with cheap model if requested and available
    if cheap and org_config:
        exploration_cfg = org_config.get("exploration", {})
        if exploration_cfg.get("cheap_llm_provider"):
            config["provider"] = exploration_cfg["cheap_llm_provider"]
        if exploration_cfg.get("cheap_llm_model"):
            config["model"] = exploration_cfg["cheap_llm_model"]

    return LLMService(api_key=config.get("api_key"), provider=config["provider"],
                      model=config["model"]).create_client()


async def layer_folio_adjacency(
    folio: FOLIO | None,
    existing_claims: list,
    config: ExplorationConfig,
) -> list[ExplorationResult]:
    """Layer 1: FOLIO ontology graph traversal for adjacent concepts.

    For each claim with a folio_iri, calls discover_adjacent_concepts to find
    related legal concepts. Confidence based on graph depth (depth 1 = 0.7,
    depth 2 = 0.5). Returns empty list if folio is None (graceful degradation).

    Args:
        folio: FOLIO instance (or None for graceful degradation).
        existing_claims: List of AnalysisClaim objects with folio_iri.
        config: ExplorationConfig for threshold settings.

    Returns:
        List of ExplorationResult from FOLIO graph traversal.
    """
    if folio is None:
        return []

    from app.services.folio.adjacency import (
        AdjacencyConfig,
        discover_adjacent_concepts,
        is_placeholder_concept,
    )
    from app.services.folio.concept_resolver import _determine_branch
    from app.services.analysis.semantic_fit import is_geographic_concept

    # BUG-13: cap adjacency claims per source-concept to curb ontology-traversal
    # noise volume. A single legal claim previously spawned ~30+ adjacency claims,
    # most of them irrelevant traversal noise. The exploration engine does not
    # currently expose a per-node relevance/similarity score, so we apply a
    # deterministic cap on the number of adjacency claims emitted per source claim
    # (shallower nodes preferred). If a per-node score is added later, prefer
    # dropping nodes below a relevance threshold here.
    _MAX_ADJACENCY_PER_SOURCE = 5

    results: list[ExplorationResult] = []
    seen_iris: set[str] = set()

    # Collect existing claim IRIs to avoid re-discovering
    existing_iris = {c.folio_iri for c in existing_claims if c.folio_iri}

    for claim in existing_claims:
        if not claim.folio_iri:
            continue

        try:
            adjacency = discover_adjacent_concepts(
                folio, claim.folio_iri, AdjacencyConfig(max_depth=2),
            )
        except Exception:
            logger.debug("FOLIO adjacency failed for %s", claim.folio_iri, exc_info=True)
            continue

        # BUG-13: emit shallowest (most relevant) nodes first so the per-source
        # cap keeps the closest concepts rather than arbitrary traversal order.
        nodes = sorted(
            adjacency.get("nodes", []),
            key=lambda n: n.get("depth", 1),
        )
        emitted_for_source = 0

        for node in nodes:
            iri = node.get("iri")
            if not iri or iri in seen_iris or iri in existing_iris:
                continue
            if iri == claim.folio_iri:
                continue  # Skip the source node itself

            # BUG-13: never let placeholder/sandbox/deprecated concepts become claims.
            if is_placeholder_concept(node.get("label")):
                continue

            # BUG-21: never let geographic concepts (a wrong seed mapping fanning
            # out into "Rize" / "Macedonia" / "Europe") surface as legal claims.
            branch = node.get("branch")
            if branch is None:
                try:
                    branch = _determine_branch(iri, folio)
                except Exception:
                    branch = None
            if is_geographic_concept(node.get("label"), branch):
                continue

            # BUG-13: cap adjacency claims per source-concept to curb traversal noise.
            if emitted_for_source >= _MAX_ADJACENCY_PER_SOURCE:
                break

            seen_iris.add(iri)
            emitted_for_source += 1

            depth = node.get("depth", 1)
            confidence = 0.7 if depth <= 1 else 0.5

            results.append(ExplorationResult(
                description=f"Adjacent concept: {node.get('label', iri)}",
                folio_iri=iri,
                source_layer="folio_adjacency",
                confidence=confidence,
                is_new_issue=True,
                claim_name=node.get("label", iri),
                rationale=f"Discovered via FOLIO ontology traversal from {claim.claim_name} (depth {depth})",
            ))

    return results


async def layer_protocol_match(
    active_protocols: list[tuple],
    facts_text: str,
    existing_results: list[ExplorationResult] | None = None,
) -> list[ExplorationResult]:
    """Layer 2: Curated screening protocol trigger matching.

    For each active protocol, checks if trigger_conditions match against the
    combined facts text using keyword/regex matching. Returns protocol questions
    and issue descriptions as ExplorationResult objects.

    Args:
        active_protocols: List of (OrgProtocolActivation, ProtocolVersion) tuples.
        facts_text: Combined text of all extracted facts.
        existing_results: Optional results from prior layers (for context).

    Returns:
        List of ExplorationResult from protocol matching.
    """
    results: list[ExplorationResult] = []
    facts_lower = facts_text.lower()

    for activation, version in active_protocols:
        trigger_cond = version.trigger_conditions_json or {}
        keywords = trigger_cond.get("keywords", [])
        regex_patterns = trigger_cond.get("regex_patterns", [])

        matched = False
        matched_terms: list[str] = []

        # Keyword matching
        for kw in keywords:
            if kw.lower() in facts_lower:
                matched = True
                matched_terms.append(kw)

        # Regex matching
        if not matched and regex_patterns:
            import re
            for pattern_str in regex_patterns:
                try:
                    pattern = re.compile(pattern_str, re.IGNORECASE)
                    if pattern.search(facts_text):
                        matched = True
                        matched_terms.append(pattern_str)
                        break
                except re.error:
                    continue

        if matched:
            # Extract protocol metadata
            protocol_name = getattr(version, "_protocol_name", f"Protocol {activation.protocol_id}")
            severity_tier = getattr(version, "_severity_tier", "advisory")

            # Create result from protocol questions
            questions = version.questions_json or []
            question_summary = "; ".join(q.get("text", "") for q in questions[:3])

            results.append(ExplorationResult(
                description=f"Screening protocol triggered: {protocol_name}",
                folio_iri=None,
                source_layer="protocol_match",
                confidence=0.8 if severity_tier == "critical" else 0.6,
                is_new_issue=True,
                protocol_id=activation.protocol_id,
                claim_name=protocol_name,
                rationale=f"Triggered by terms: {', '.join(matched_terms)}. Questions: {question_summary}",
            ))

    return results


async def layer_cheap_llm(
    llm_service: LLMService,
    facts_text: str,
    existing_claims: list,
    org_config: dict,
) -> list[ExplorationResult]:
    """Layer 3: Fast/cheap LLM reasoning scan for adjacent legal issues.

    Builds a prompt with all facts and existing claims asking for additional
    legal issues a consumer might not know to mention. Uses the cheap LLM
    (ExplorationConfig.cheap_llm_provider/model or org default).

    Args:
        llm_service: LLMService for LLM calls.
        facts_text: Combined text of all extracted facts.
        existing_claims: List of existing AnalysisClaim objects.
        org_config: Org configuration dict.

    Returns:
        List of ExplorationResult from cheap LLM scan.
        Empty list on LLM failure (graceful degradation).
    """
    try:
        model = _create_llm_model(llm_service, cheap=True, org_config=org_config)
    except Exception:
        logger.warning("Cheap LLM unavailable, skipping layer")
        return []

    existing_names = [c.claim_name for c in existing_claims]
    claims_str = ", ".join(existing_names) if existing_names else "None identified yet"

    messages = [
        {
            "role": "system",
            "content": (
                "You are a legal issue-spotting assistant. Given facts and already-identified claims, "
                "identify additional legal issues the consumer might not know to mention. "
                "Return a JSON object with an 'issues' array. Each issue has: "
                "claim_name (str), description (str), confidence (float 0-1), rationale (str). "
                + ISSUES_REPLY_RULES
            ),
        },
        {
            "role": "user",
            "content": f"Facts:\n{facts_text}\n\nExisting claims: {claims_str}\n\n"
            "What additional legal issues should be explored?",
        },
    ]

    return await _bounded_issues(model, messages, "cheap_llm")


async def layer_expensive_llm(
    llm_service: LLMService,
    facts_text: str,
    existing_claims: list,
    folio_context: list[ExplorationResult],
    protocol_context: list[ExplorationResult],
    org_config: dict,
) -> list[ExplorationResult]:
    """Layer 4: Deep/expensive LLM reasoning with FOLIO + protocol context.

    Builds a richer prompt incorporating FOLIO adjacency results and protocol
    match results from prior sequential layers. Asks the expensive LLM to reason
    about legal issue connections.

    Args:
        llm_service: LLMService for LLM calls.
        facts_text: Combined text of all extracted facts.
        existing_claims: List of existing AnalysisClaim objects.
        folio_context: Results from layer_folio_adjacency.
        protocol_context: Results from layer_protocol_match.
        org_config: Org configuration dict.

    Returns:
        List of ExplorationResult from expensive LLM reasoning.
        Empty list on LLM failure (graceful degradation).
    """
    try:
        model = _create_llm_model(llm_service, cheap=False, org_config=org_config)
    except Exception:
        logger.warning("Expensive LLM unavailable, skipping layer")
        return []

    existing_names = [c.claim_name for c in existing_claims]
    claims_str = ", ".join(existing_names) if existing_names else "None identified yet"

    # Build context from prior layers
    folio_str = "\n".join(
        f"- {r.claim_name}: {r.description} (confidence: {r.confidence})"
        for r in folio_context
    ) if folio_context else "No FOLIO adjacency results"

    protocol_str = "\n".join(
        f"- {r.claim_name}: {r.description}"
        for r in protocol_context
    ) if protocol_context else "No protocol matches"

    messages = [
        {
            "role": "system",
            "content": (
                "You are an expert legal analyst. Given facts, existing claims, FOLIO ontology "
                "adjacency results, and screening protocol matches, identify legal issues that "
                "the other layers might have missed. Focus on connections between issues, "
                "cross-practice implications, and issues that require legal expertise to spot. "
                "Return a JSON object with an 'issues' array. Each issue has: "
                "claim_name (str), description (str), confidence (float 0-1), rationale (str). "
                + ISSUES_REPLY_RULES
            ),
        },
        {
            "role": "user",
            "content": (
                f"Facts:\n{facts_text}\n\n"
                f"Existing claims: {claims_str}\n\n"
                f"FOLIO ontology adjacent concepts:\n{folio_str}\n\n"
                f"Screening protocol matches:\n{protocol_str}\n\n"
                "What additional legal issues should be explored?"
            ),
        },
    ]

    return await _bounded_issues(model, messages, "expensive_llm")
