"""Unmapped concept handling with local IRI generation and LLM branch suggestion.

When a legal concept cannot be mapped to FOLIO with sufficient confidence,
this module creates a structured unmapped record containing:
- A local IRI via folio-python's generate_iri() (WebProtege-aligned scheme)
- An unmapped_confidence score (how confident we are it's genuinely unmapped)
- Up to 3 nearest FOLIO concepts (sorted by descending match confidence)
- An optional LLM-suggested FOLIO branch for future curation

Unmapped concepts participate fully in the analysis pipeline at equal footing
with mapped concepts, using the local IRI as their identifier.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from folio import FOLIO
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Known FOLIO branches for LLM branch suggestion validation
KNOWN_BRANCHES = [
    "Objectives",
    "Area of Law",
    "Legal Authorities",
    "Legal Entity",
    "Actor-Player",
    "Event",
    "Document-Artifact",
    "Location",
    "Service",
    "Forums and Venues",
    "Communication Modality",
    "Language",
    "Currency",
    "Time Period",
    "Industry or Sector",
    "Dispute Resolution",
    "Governmental Body",
    "Standard or Guideline",
    "System",
]


@dataclass
class UnmappedConceptData:
    """Structured data for a concept not found in FOLIO.

    Attributes:
        local_iri: Locally generated IRI via folio-python's generate_iri().
        original_text: The raw text that could not be mapped.
        suggested_branch: Optional LLM-suggested FOLIO branch for curation.
        unmapped_confidence: How confident we are the concept is genuinely
            unmapped (1.0 = no match at all, lower = closer to threshold).
        nearest_concepts: Up to 3 closest FOLIO concepts with their
            confidence scores [{iri, label, confidence}, ...].
    """

    local_iri: str
    original_text: str
    suggested_branch: str | None
    unmapped_confidence: float
    nearest_concepts: list[dict] = field(default_factory=list)


async def handle_unmapped_concept(
    text: str,
    folio: FOLIO,
    low_confidence_matches: list,
    confidence_threshold: float = 0.5,
    llm_model=None,
) -> UnmappedConceptData:
    """Create a structured unmapped concept record with local IRI.

    Args:
        text: The original text that couldn't be mapped to FOLIO.
        folio: The FOLIO instance for IRI generation.
        low_confidence_matches: Objects with .iri, .label, .confidence attrs,
            representing candidate matches that fell below the threshold.
        confidence_threshold: The minimum confidence for a valid match.
        llm_model: Optional LLM model for branch suggestion.

    Returns:
        UnmappedConceptData with local IRI, nearest concepts, and confidence.
    """
    # Generate IRI using folio-python's WebProtege-aligned scheme
    local_iri = folio.generate_iri()

    # Nearest concepts: top 3 by confidence from low-confidence matches
    nearest = [
        {"iri": m.iri, "label": m.label, "confidence": m.confidence}
        for m in sorted(low_confidence_matches, key=lambda x: x.confidence, reverse=True)[:3]
    ]

    # Unmapped confidence: if best match is very low, high confidence it's unmapped
    # Formula: 1 - (best_score / threshold), clamped to [0.0, 1.0]
    best_score = nearest[0]["confidence"] if nearest else 0.0
    unmapped_confidence = max(0.0, min(1.0, 1.0 - (best_score / confidence_threshold)))

    # LLM-suggested branch (optional)
    suggested_branch = None
    if llm_model is not None:
        suggested_branch = await _llm_suggest_branch(text, llm_model)

    return UnmappedConceptData(
        local_iri=local_iri,
        original_text=text,
        suggested_branch=suggested_branch,
        unmapped_confidence=unmapped_confidence,
        nearest_concepts=nearest,
    )


async def _llm_suggest_branch(text: str, llm_model) -> str | None:
    """Use LLM to suggest which FOLIO branch a concept might belong to.

    Args:
        text: The unmapped concept text.
        llm_model: An LLM model object with a generate/complete method.

    Returns:
        Branch name string or None if suggestion fails or is invalid.
    """
    branch_list = ", ".join(KNOWN_BRANCHES)
    prompt = (
        f"Given the following legal concept text, which FOLIO ontology branch "
        f"would it most likely belong to? Options: {branch_list}. "
        f"Respond with just the branch name.\n\n"
        f"Text: {text}"
    )

    try:
        if hasattr(llm_model, "generate"):
            response = await llm_model.generate(prompt)
        elif hasattr(llm_model, "complete"):
            response = await llm_model.complete(prompt)
        else:
            return None

        # Parse and validate the response
        branch = str(response).strip()
        if branch in KNOWN_BRANCHES:
            return branch

        # Try case-insensitive match
        branch_lower = branch.lower()
        for known in KNOWN_BRANCHES:
            if known.lower() == branch_lower:
                return known

        logger.warning("LLM suggested unknown branch: %s", branch)
        return None

    except Exception:
        logger.debug("LLM branch suggestion failed", exc_info=True)
        return None


async def persist_unmapped(
    session: AsyncSession,
    intake_id: int,
    org_id: int,
    unmapped: UnmappedConceptData,
) -> "UnmappedConceptRecord":
    """Persist an unmapped concept record to the tenant database.

    Args:
        session: Async SQLAlchemy session (tenant-scoped).
        intake_id: The intake this concept belongs to.
        org_id: Organization ID for the tenant.
        unmapped: The structured unmapped concept data.

    Returns:
        The created UnmappedConceptRecord with assigned ID.
    """
    from app.models.folio_concepts import UnmappedConceptRecord

    record = UnmappedConceptRecord(
        intake_id=intake_id,
        local_iri=unmapped.local_iri,
        original_text=unmapped.original_text,
        suggested_branch=unmapped.suggested_branch,
        unmapped_confidence=unmapped.unmapped_confidence,
        nearest_iris=unmapped.nearest_concepts,
        org_id=org_id,
    )
    session.add(record)
    await session.flush()
    return record
