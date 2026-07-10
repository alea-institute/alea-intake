"""Gap analysis stage -- detects four gap types from analysis state.

Implements D-09 (four gap types): unsupported_element, unexplored_claim,
weak_mapping, procedural_requirement. Persists gaps as AnalysisGap records,
computes coverage percentage, and filters out already-resolved gaps.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis import (
    AnalysisClaim,
    AnalysisGap,
    AnalysisIteration,
    AnalysisRun,
    ClaimElement,
    FactClaimMapping,
)
from app.services.analysis.schemas import GapAnalysisResult, GapSchema

if TYPE_CHECKING:
    from app.services.llm_service import LLMService


class GapAnalyzeStage:
    """Detect gaps in the analysis and persist them for question generation.

    Four gap types:
      - unsupported_element: ClaimElement with is_satisfied=False and no mapping
      - unexplored_claim: AnalysisClaim with is_potential=True and no mappings
      - weak_mapping: FactClaimMapping with confidence below threshold
      - procedural_requirement: LLM-detected procedural gaps (deadlines, filings)
    """

    def __init__(
        self,
        llm_service: LLMService,
        db_session: AsyncSession,
        weak_mapping_threshold: float = 0.5,
    ) -> None:
        self.llm_service = llm_service
        self.db_session = db_session
        self.weak_mapping_threshold = weak_mapping_threshold

    async def execute(
        self,
        run: AnalysisRun,
        iteration: AnalysisIteration,
        claims: list[AnalysisClaim],
        elements: list[ClaimElement],
        mappings: list[FactClaimMapping],
        existing_gaps: list[AnalysisGap],
    ) -> dict[str, Any]:
        """Run gap analysis over current analysis state.

        Args:
            run: The current analysis run.
            iteration: The current iteration within the run.
            claims: All claims identified so far.
            elements: All claim elements across claims.
            mappings: All fact-to-claim mappings.
            existing_gaps: Previously detected gaps (to avoid duplicates).

        Returns:
            Dict with gaps_count, coverage_pct, gap_types (breakdown), summary.
        """
        new_gaps: list[AnalysisGap] = []

        # Build lookup structures
        claim_by_id = {c.id: c for c in claims}
        element_by_id = {e.id: e for e in elements}
        mappings_by_element_id: dict[int, list[FactClaimMapping]] = {}
        mappings_by_claim_id: dict[int, list[FactClaimMapping]] = {}
        for m in mappings:
            if m.element_id is not None:
                mappings_by_element_id.setdefault(m.element_id, []).append(m)
            mappings_by_claim_id.setdefault(m.claim_id, []).append(m)

        # Build set of existing gap signatures to avoid duplicates.
        # Include ALL existing gaps (open, addressed, etc.) -- addressed gaps
        # should not be re-detected, and open gaps should not be duplicated.
        existing_signatures = set()
        for eg in existing_gaps:
            existing_signatures.add(
                (eg.gap_type, eg.claim_id, eg.element_id)
            )

        # 1. Unsupported elements
        for elem in elements:
            if elem.is_satisfied:
                continue
            if elem.id in mappings_by_element_id:
                continue
            claim = claim_by_id.get(elem.claim_id)
            sig = ("unsupported_element", elem.claim_id, elem.id)
            if sig in existing_signatures:
                continue
            priority = int((claim.confidence if claim else 0.5) * 100)
            gap = AnalysisGap(
                run_id=run.id,
                gap_type="unsupported_element",
                claim_id=elem.claim_id,
                element_id=elem.id,
                description=f"Element '{elem.element_name}' is not yet supported by any facts",
                priority=priority,
                status="open",
                iteration_found=iteration.iteration_number,
            )
            new_gaps.append(gap)

        # 2. Unexplored claims
        for claim in claims:
            if not claim.is_potential:
                continue
            if claim.id in mappings_by_claim_id:
                continue
            sig = ("unexplored_claim", claim.id, None)
            if sig in existing_signatures:
                continue
            gap = AnalysisGap(
                run_id=run.id,
                gap_type="unexplored_claim",
                claim_id=claim.id,
                element_id=None,
                description=f"Potential claim '{claim.claim_name}' has not been explored with fact mappings",
                priority=50,
                status="open",
                iteration_found=iteration.iteration_number,
            )
            new_gaps.append(gap)

        # 3. Weak mappings
        for m in mappings:
            if m.confidence >= self.weak_mapping_threshold:
                continue
            sig = ("weak_mapping", m.claim_id, m.element_id)
            if sig in existing_signatures:
                continue
            priority = int((1 - m.confidence) * 100)
            elem = element_by_id.get(m.element_id) if m.element_id else None
            claim = claim_by_id.get(m.claim_id)
            desc_parts = []
            if claim:
                desc_parts.append(f"claim '{claim.claim_name}'")
            if elem:
                desc_parts.append(f"element '{elem.element_name}'")
            desc = f"Weak mapping (confidence={m.confidence:.2f}) for {' / '.join(desc_parts)}"
            gap = AnalysisGap(
                run_id=run.id,
                gap_type="weak_mapping",
                claim_id=m.claim_id,
                element_id=m.element_id,
                description=desc,
                priority=priority,
                status="open",
                iteration_found=iteration.iteration_number,
            )
            new_gaps.append(gap)

        # 4. Procedural requirements + unstated legal doctrine via LLM
        procedural_gaps = await self._detect_procedural_and_doctrine_gaps(
            claims, iteration, run, existing_signatures
        )
        new_gaps.extend(procedural_gaps)

        # Persist all new gaps
        for gap in new_gaps:
            self.db_session.add(gap)
        await self.db_session.flush()

        # Compute coverage
        total_elements = len(elements)
        satisfied_elements = sum(1 for e in elements if e.is_satisfied)
        coverage_pct = (
            satisfied_elements / total_elements if total_elements > 0 else 0.0
        )

        # Build gap type breakdown
        gap_types: dict[str, int] = {}
        for g in new_gaps:
            gap_types[g.gap_type] = gap_types.get(g.gap_type, 0) + 1

        return {
            "gaps_count": len(new_gaps),
            "coverage_pct": coverage_pct,
            "gap_types": gap_types,
            "summary": f"Found {len(new_gaps)} gaps across {len(gap_types)} types. Coverage: {coverage_pct:.1%}",
        }

    async def _detect_procedural_and_doctrine_gaps(
        self,
        claims: list[AnalysisClaim],
        iteration: AnalysisIteration,
        run: AnalysisRun,
        existing_signatures: set[tuple],
    ) -> list[AnalysisGap]:
        """Use LLM to detect procedural-requirement AND unstated-doctrine gaps.

        Two purposes, one call:
          1. Procedural requirements (deadlines, filings, SOL, jurisdiction).
          2. Q1 (RUB-01, Damien 2026-07-08): surface UNSTATED legal DOCTRINE
             that the facts imply but the client did not name — specific relief,
             eligibility criteria, and statutory exceptions a legal-aid attorney
             would investigate. Damien's ruling: surfacing the doctrine AS A
             QUESTION suffices. These gaps flow into question_gen and become
             consumer-facing follow-up questions, so a matter's latent doctrine
             (e.g. VAWA self-petition eligibility, asylum one-year-bar
             exceptions for changed/extraordinary circumstances, the
             best-interest / domestic-abuse custody factors under Minn. Stat.
             § 518.17) is probed even when no explicit claim was spotted for it.
        """
        if not claims:
            return []

        # Pass claim rationales too so the doctrine probe sees the fact context,
        # not just claim labels.
        claims_desc = "; ".join(
            f"{c.claim_name}" + (f" ({c.rationale})" if c.rationale else "")
            for c in claims
        )[:2000]
        prompt = (
            "You are assisting a legal-aid intake system. Two tasks over the "
            "identified legal claims below:\n"
            "1. PROCEDURAL: identify any filing deadlines, statute-of-limitations "
            "concerns, jurisdictional requirements, or other procedural gaps.\n"
            "2. UNSTATED DOCTRINE: identify specific legal doctrine the facts "
            "imply but the client likely did not name — particular forms of "
            "relief, ELIGIBILITY criteria, and statutory EXCEPTIONS an attorney "
            "would investigate (e.g. eligibility for a specific immigration "
            "relief such as VAWA self-petition or a U/T visa; exceptions to a "
            "filing bar such as the asylum one-year-bar 'changed or extraordinary "
            "circumstances' exception; the statutory best-interest and "
            "domestic-abuse factors that govern a custody decision). Phrase each "
            "as a concrete question a non-lawyer could be asked to determine "
            "whether the doctrine applies. Only surface doctrine the facts fairly "
            "raise; never invent facts.\n\n"
            f"Identified claims: {claims_desc}.\n\n"
            "Return EVERY gap with gap_type 'procedural_requirement'.\n"
            'Return ONLY a JSON object with EXACTLY this structure:\n'
            '{"gaps": [{"gap_type": "procedural_requirement", "claim_name": "name or null", '
            '"element_name": null, "description": "the question / what is missing", "priority": 50}], '
            '"coverage_pct": 0.0, "summary": "one-line overview"}'
        )

        try:
            result: GapAnalysisResult = await self.llm_service.json_async(
                prompt=prompt,
                schema=GapAnalysisResult,
            )
        except Exception:
            # If LLM fails, return empty -- procedural gaps are optional
            return []

        procedural_gaps: list[AnalysisGap] = []
        for gap_schema in result.gaps:
            if gap_schema.gap_type != "procedural_requirement":
                continue
            # Find matching claim for claim_id
            claim_id = None
            for c in claims:
                if c.claim_name == gap_schema.claim_name:
                    claim_id = c.id
                    break
            sig = ("procedural_requirement", claim_id, None)
            if sig in existing_signatures:
                continue
            gap = AnalysisGap(
                run_id=run.id,
                gap_type="procedural_requirement",
                claim_id=claim_id,
                element_id=None,
                description=gap_schema.description,
                priority=gap_schema.priority,
                status="open",
                iteration_found=iteration.iteration_number,
            )
            procedural_gaps.append(gap)

        return procedural_gaps
