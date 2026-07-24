"""Semantic-fit validation for claim -> FOLIO concept mappings (BUG-21).

The concept resolver returns the best *label/embedding* match for a claim name,
but a good label match is not the same as a good *semantic* match in the matter's
context. Live runs produced resolvable-but-wrong mappings surfaced at 70-90%
confidence:

  - "Habitability"          -> "Living"           (a vital-status concept)
  - "Rent Withholding"      -> "Insurance Claims" (which then spawned SSA/motorist
                                                   junk via adjacency exploration)
  - "Retaliation"           -> "Lease"
  - "Unauthorized Employment" -> "Rize"           (a city in Turkey -- geographic!)
  - patent "Markman Hearing", "Macedonia", "Europe" surfaced as URGENT claims in a
    custody matter.

Damien added the semantic-fit sub-criterion to rubric v1.2 (RUB-05), so the intent
is explicit: a mapping must actually *fit* the concept it names, in context.

This module provides a two-tier fitness check:

  1. **Deterministic rejection** (free, no LLM) -- rejects mappings whose resolved
     concept is geographic or place-like (a place name, a jurisdiction, or a
     governmental body / agency -- detected by the shared `folio-resolve`
     ``PlaceNameGate``), a placeholder, or an unmapped/"Unknown" branch. These are
     never valid legal-claim concepts.

  2. **LLM semantic-fit** (one cheap call per analysis on gpt-4o-mini) -- for the
     mappings that survive tier 1, a single batched call judges context-vs-concept
     fitness and recalibrates confidence. Degrades gracefully: if no LLM is
     available or the call fails, the deterministic result stands.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from folio_resolve import PlaceNameGate
from pydantic import BaseModel, Field

from app.services.folio.adjacency import is_placeholder_concept

if TYPE_CHECKING:  # pragma: no cover
    from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)


# FOLIO branches that a substantive legal claim must never resolve into. A claim
# resolving to a geographic place ("Location") or an unmapped/"Unknown" node is a
# false-confidence mapping by construction.
_UNFIT_CLAIM_BRANCHES: frozenset[str] = frozenset({"Location", "Unknown", ""})

# Primary place detector: the shared library's gate. It knows the whole class of concepts
# whose short proper-noun labels pathologically over-score -- geographic branches
# (location / geograph / country / jurisdiction / place) AND governmental bodies and
# agencies -- plus a curated set of notoriously over-scoring place tokens. Adopting it
# widens alea-intake's guard from the single exact branch string "Location" to that whole
# class, which is what BUG-21 actually needs: a legal CLAIM is never an agency either
# ("Retaliation" -> Department of Labor is the same false-confidence failure as
# "Unauthorized Employment" -> Rize).
#
# The gate is deliberately scoped to CLAIM FITNESS and is NOT applied in
# ``concept_resolver.resolve_concepts``, which resolves Location concepts on purpose
# (jurisdiction, venue). The migration harness canaries both halves: PLACE-REJECTED and
# PLACES-RESOLVABLE (see backend/migration/README.md).
_PLACE_GATE = PlaceNameGate(min_signals=2)

# Local backstop for place phrasings the library's token set does not carry: continents and
# regions, and "City of X" / "Republic of X" style labels that arrive with no branch metadata
# (embedding backends do not always populate branch). Kept deliberately small -- the
# authoritative signals are the FOLIO branch and the library gate above.
_GEOGRAPHIC_LABEL_MARKERS: tuple[str, ...] = (
    "continent",
    "republic of",
    "city of",
    "province of",
    "state of ",
    "district of",
    "kingdom of",
)
_GEOGRAPHIC_LABEL_EXACT: frozenset[str] = frozenset(
    {
        "europe",
        "asia",
        "africa",
        "north america",
        "south america",
        "antarctica",
        "oceania",
        "macedonia",
        "rize",
    }
)


def is_geographic_concept(label: str | None, branch: str | None) -> bool:
    """Return True if the resolved concept is a place or a place-like body (an agency).

    Tier 1 is the shared ``folio_resolve.PlaceNameGate``. It is called with no
    corroborating signals and an empty query so that it answers the pure question "is this
    concept in the place/agency class?": with ``signals = 0 < min_signals``, any concept the
    gate recognizes is demoted, and the gate's "the query IS the place name" escape hatch
    cannot fire -- correct here, because a legal claim named exactly "Macedonia" is still not
    a legal claim.

    Tier 2 is the local marker backstop for continents and "City of X" phrasings.
    """
    # Preserved fast path: the authoritative branch signal, checked before the gate so an
    # empty label on a Location-branch concept still reads as geographic.
    if branch and branch.strip() == "Location":
        return True
    if _PLACE_GATE.evaluate(
        query="",
        label=label or "",
        branch=(branch or "").strip(),
        score=100.0,
        corroborating_signals=0,
    ).demoted:
        return True
    if not label:
        return False
    norm = label.strip().lower()
    if norm in _GEOGRAPHIC_LABEL_EXACT:
        return True
    return any(marker in norm for marker in _GEOGRAPHIC_LABEL_MARKERS)


def deterministic_unfit_reason(label: str | None, branch: str | None) -> str | None:
    """Return a rejection reason if the mapping is deterministically unfit, else None.

    A mapping is unfit when the resolved concept is a placeholder, geographic, or
    lives in a branch a legal claim can never legitimately occupy.
    """
    if is_placeholder_concept(label):
        return "placeholder_concept"
    if is_geographic_concept(label, branch):
        return "geographic_concept"
    if (branch or "").strip() in _UNFIT_CLAIM_BRANCHES:
        return "unfit_branch"
    return None


@dataclass
class FitItem:
    """One claim -> concept mapping submitted for fitness validation."""

    key: str  # stable identifier (e.g. claim name key)
    claim_name: str
    concept_label: str
    branch: str
    confidence: float


@dataclass
class FitVerdict:
    """Result of validating a single mapping."""

    fits: bool
    adjusted_confidence: float
    reason: str
    drop_iri: bool  # True -> clear the folio_iri (mapping is wrong)


# Confidence ceiling applied to a claim whose concept mapping was rejected: the
# claim may still be real, but we must not present a wrong/absent mapping at high
# confidence (RUB-05 false-confidence).
_REJECTED_CONFIDENCE_CEILING: float = 0.4


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


class _FitDecision(BaseModel):
    """One claim's fitness decision from the LLM."""

    claim_name: str = Field(description="The claim name being judged")
    fits: bool = Field(description="Whether the concept fits the claim in context")
    adjusted_confidence: float = Field(
        default=0.0, description="Recalibrated 0-1 confidence for the mapping"
    )
    reason: str = Field(default="", description="Short justification")


class _FitResponse(BaseModel):
    """Batched semantic-fit response."""

    decisions: list[_FitDecision] = Field(default_factory=list)


class SemanticFitValidator:
    """Validates a batch of claim->concept mappings for semantic fitness."""

    def __init__(self, llm_service: LLMService | None = None) -> None:
        self._llm = llm_service

    def apply_deterministic(self, items: list[FitItem]) -> dict[str, FitVerdict]:
        """Tier 1: deterministic geographic/placeholder/branch rejection.

        Returns a verdict for every item that is deterministically unfit. Items
        not present in the result survived tier 1 and may go to the LLM.
        """
        verdicts: dict[str, FitVerdict] = {}
        for item in items:
            reason = deterministic_unfit_reason(item.concept_label, item.branch)
            if reason is not None:
                verdicts[item.key] = FitVerdict(
                    fits=False,
                    adjusted_confidence=_clamp(
                        min(item.confidence, _REJECTED_CONFIDENCE_CEILING)
                    ),
                    reason=reason,
                    drop_iri=True,
                )
                logger.info(
                    "semantic-fit: rejected mapping %r -> %r (%s)",
                    item.claim_name,
                    item.concept_label,
                    reason,
                )
        return verdicts

    async def validate(
        self, matter_context: str, items: list[FitItem]
    ) -> dict[str, FitVerdict]:
        """Validate all mappings. One LLM call for the survivors of tier 1.

        Args:
            matter_context: A short description of the matter (facts summary) so
                the fitness judgment is context-aware.
            items: Claim->concept mappings to validate.

        Returns:
            A verdict keyed by ``FitItem.key`` for every item that needs action
            (rejected or confidence-recalibrated). Items judged a good fit at
            their original confidence are omitted.
        """
        if not items:
            return {}

        verdicts = self.apply_deterministic(items)
        survivors = [i for i in items if i.key not in verdicts]
        if not survivors or self._llm is None:
            return verdicts

        try:
            llm_verdicts = await self._llm_validate(matter_context, survivors)
        except Exception:
            logger.warning(
                "semantic-fit LLM validation failed; keeping deterministic result",
                exc_info=True,
            )
            return verdicts

        verdicts.update(llm_verdicts)
        return verdicts

    async def _llm_validate(
        self, matter_context: str, items: list[FitItem]
    ) -> dict[str, FitVerdict]:
        """One batched LLM call judging fitness of the survivor mappings."""
        listing = "\n".join(
            f'{idx + 1}. claim "{i.claim_name}" was mapped to FOLIO concept '
            f'"{i.concept_label}" (branch: {i.branch or "unknown"}), '
            f"stated confidence {i.confidence:.2f}"
            for idx, i in enumerate(items)
        )
        prompt = (
            "You validate whether each legal claim was mapped to a FOLIO ontology "
            "concept that actually fits it, given the matter context. A mapping "
            "does NOT fit when the concept is about a different subject than the "
            "claim (e.g. a rent-withholding claim mapped to 'Insurance Claims', a "
            "retaliation claim mapped to 'Lease', or any geographic place). When a "
            "mapping does not fit, set fits=false and a low adjusted_confidence. "
            "When it fits, set fits=true and an honest adjusted_confidence.\n\n"
            f"Matter context:\n{matter_context}\n\n"
            f"Mappings to judge:\n{listing}\n\n"
            "Return ONLY a JSON object with EXACTLY this structure:\n"
            '{"decisions": [{"claim_name": "<exact claim name>", "fits": true, '
            '"adjusted_confidence": 0.0, "reason": "<short>"}]}'
        )

        result: _FitResponse = await self._llm.json_async(
            prompt=prompt, schema=_FitResponse
        )

        by_name: dict[str, FitItem] = {i.claim_name.strip().lower(): i for i in items}
        out: dict[str, FitVerdict] = {}
        for decision in result.decisions:
            item = by_name.get(decision.claim_name.strip().lower())
            if item is None:
                continue
            if decision.fits:
                # Only record when the model materially lowers confidence.
                adjusted = _clamp(decision.adjusted_confidence or item.confidence)
                if adjusted < item.confidence - 0.05:
                    out[item.key] = FitVerdict(
                        fits=True,
                        adjusted_confidence=adjusted,
                        reason=decision.reason or "recalibrated",
                        drop_iri=False,
                    )
            else:
                out[item.key] = FitVerdict(
                    fits=False,
                    adjusted_confidence=_clamp(
                        min(
                            decision.adjusted_confidence or item.confidence,
                            _REJECTED_CONFIDENCE_CEILING,
                        )
                    ),
                    reason=decision.reason or "semantic_mismatch",
                    drop_iri=True,
                )
        return out
