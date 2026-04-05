"""Data assembler -- queries all upstream analysis/research data into a unified OutputContext.

Pattern: single DB session loads claims, elements, mappings, gaps, questions,
authorities, and facts, then assembles them into the format-neutral OutputContext
for downstream rendering.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis import (
    AnalysisClaim,
    AnalysisGap,
    AnalysisRun,
    ClaimElement,
    FactClaimMapping,
    FollowUpQuestion,
)
from app.models.fact import ExtractedFact
from app.models.intake import Intake
from app.models.research import Authority
from app.services.output.gap_report_builder import GapReportBuilder
from app.services.output.schemas import (
    AuthorityRef,
    CIRACSection,
    ElementRef,
    FactMappingRef,
    GapEntry,
    GapReport,
    OutputContext,
    OutputProfile,
)

# Binding strength ordering: lower = higher priority
_BINDING_ORDER = {"binding": 0, "persuasive": 1, "secondary": 2}


class DataAssembler:
    """Queries all analysis/research data into a unified OutputContext."""

    def __init__(self, db_session: AsyncSession):
        self._session = db_session

    async def assemble(
        self, run_id: int, intake_id: int, profile: OutputProfile
    ) -> OutputContext:
        """Load all upstream data and build OutputContext.

        Args:
            run_id: Analysis run ID.
            intake_id: Intake ID.
            profile: Output profile controlling content.

        Returns:
            OutputContext with claims grouped by jurisdiction.
        """
        # Load all data
        run = await self._load_run(run_id)
        intake = await self._load_intake(intake_id)
        claims = await self._load_claims(run_id)
        claim_ids = [c.id for c in claims]

        elements_by_claim = await self._load_elements(claim_ids)
        mappings_by_element = await self._load_mappings(claim_ids)
        facts_by_id = await self._load_facts(intake_id)
        gaps_by_claim = await self._load_gaps(run_id)
        all_gaps = await self._load_all_open_gaps(run_id)
        questions = await self._load_questions(run_id)
        authorities = await self._load_authorities(intake_id)

        # Build CIRAC sections
        sections_by_jurisdiction: dict[str, list[CIRACSection]] = defaultdict(list)

        for claim in claims:
            jurisdiction = claim.jurisdiction or "General"

            # Elements for this claim
            claim_elements = elements_by_claim.get(claim.id, [])
            element_refs = []
            for elem in claim_elements:
                # Fact mappings for this element
                elem_mappings = mappings_by_element.get(elem.id, [])
                fact_mapping_refs = []
                for m in elem_mappings:
                    fact = facts_by_id.get(m.fact_id)
                    fact_mapping_refs.append(
                        FactMappingRef(
                            fact_id=m.fact_id,
                            fact_text=fact.assertion_text if fact else f"Fact #{m.fact_id}",
                            confidence=m.confidence,
                            mapping_rationale=m.mapping_rationale,
                        )
                    )
                element_refs.append(
                    ElementRef(
                        element_id=elem.id,
                        element_name=elem.element_name,
                        element_description=elem.element_description,
                        is_satisfied=elem.is_satisfied,
                        satisfaction_confidence=elem.satisfaction_confidence,
                        fact_mappings=fact_mapping_refs,
                    )
                )

            # Authorities for this claim (matched by claim_iri == claim.folio_iri)
            claim_authorities = self._match_authorities(authorities, claim)
            authority_refs = self._build_authority_refs(claim_authorities)

            # Inline gaps for this claim
            claim_gaps = gaps_by_claim.get(claim.id, [])
            claim_id_to_name = {c.id: c.claim_name for c in claims}
            element_id_to_name = {}
            for elems in elements_by_claim.values():
                for e in elems:
                    element_id_to_name[e.id] = e.element_name

            gap_entries = [
                GapEntry(
                    gap_id=g.id,
                    gap_type=g.gap_type,
                    description=g.description,
                    priority=g.priority,
                    claim_id=g.claim_id,
                    element_id=g.element_id,
                    claim_name=claim_id_to_name.get(g.claim_id) if g.claim_id else None,
                    element_name=element_id_to_name.get(g.element_id) if g.element_id else None,
                )
                for g in claim_gaps
            ]

            # Issue statement
            issue_statement = (
                claim.rationale
                or f"Whether {claim.claim_name} applies based on the presented facts"
            )

            # Conclusion
            satisfied = sum(1 for e in element_refs if e.is_satisfied)
            total = len(element_refs)
            avg_conf = (
                sum(e.satisfaction_confidence or 0.0 for e in element_refs) / total
                if total > 0
                else 0.0
            )
            conclusion = (
                f"{satisfied} of {total} elements supported ({avg_conf:.0%} confidence)"
                if total > 0
                else "No elements defined"
            )

            section = CIRACSection(
                claim_id=claim.id,
                claim_name=claim.claim_name,
                claim_type=claim.claim_type,
                confidence=claim.confidence,
                jurisdiction=claim.jurisdiction,
                folio_iri=claim.folio_iri,
                issue_statement=issue_statement,
                authorities=authority_refs,
                elements=element_refs,
                gaps=gap_entries,
                conclusion=conclusion,
            )
            sections_by_jurisdiction[jurisdiction].append(section)

        # Build gap report
        claim_id_to_name = {c.id: c.claim_name for c in claims}
        element_id_to_name = {}
        for elems in elements_by_claim.values():
            for e in elems:
                element_id_to_name[e.id] = e.element_name

        gap_report = GapReportBuilder.build(
            gaps=all_gaps,
            questions=questions,
            claims=claim_id_to_name,
            elements=element_id_to_name,
            convergence_score=run.convergence_score if run else None,
        )

        # Matter title
        matter_title = "Untitled Intake"
        if intake and intake.metadata_json and isinstance(intake.metadata_json, dict):
            matter_title = intake.metadata_json.get("title", f"Intake #{intake_id}")

        # Completeness score
        completeness = run.convergence_score if run and run.convergence_score else 0.0

        return OutputContext(
            intake_id=intake_id,
            run_id=run_id,
            org_id=intake.org_id if intake else 0,
            matter_title=matter_title,
            generated_at=datetime.now(timezone.utc),
            claims_by_jurisdiction=dict(sections_by_jurisdiction),
            triage=None,
            action_items=[],
            gap_report=gap_report,
            completeness_score=completeness,
            executive_summary="",
            profile=profile,
        )

    # ------------------------------------------------------------------
    # Private data loading methods
    # ------------------------------------------------------------------

    async def _load_run(self, run_id: int) -> AnalysisRun | None:
        result = await self._session.execute(
            select(AnalysisRun).where(AnalysisRun.id == run_id)
        )
        return result.scalars().first()

    async def _load_intake(self, intake_id: int) -> Intake | None:
        result = await self._session.execute(
            select(Intake).where(Intake.id == intake_id)
        )
        return result.scalars().first()

    async def _load_claims(self, run_id: int) -> list[AnalysisClaim]:
        result = await self._session.execute(
            select(AnalysisClaim)
            .where(AnalysisClaim.run_id == run_id)
            .order_by(AnalysisClaim.jurisdiction, AnalysisClaim.claim_name)
        )
        return list(result.scalars().all())

    async def _load_elements(self, claim_ids: list[int]) -> dict[int, list[ClaimElement]]:
        """Load elements grouped by claim_id."""
        if not claim_ids:
            return {}
        result = await self._session.execute(
            select(ClaimElement).where(ClaimElement.claim_id.in_(claim_ids))
        )
        elements = result.scalars().all()
        by_claim: dict[int, list[ClaimElement]] = defaultdict(list)
        for e in elements:
            by_claim[e.claim_id].append(e)
        return dict(by_claim)

    async def _load_mappings(self, claim_ids: list[int]) -> dict[int, list[FactClaimMapping]]:
        """Load fact-claim mappings grouped by element_id."""
        if not claim_ids:
            return {}
        result = await self._session.execute(
            select(FactClaimMapping).where(FactClaimMapping.claim_id.in_(claim_ids))
        )
        mappings = result.scalars().all()
        by_element: dict[int, list[FactClaimMapping]] = defaultdict(list)
        for m in mappings:
            if m.element_id is not None:
                by_element[m.element_id].append(m)
        return dict(by_element)

    async def _load_facts(self, intake_id: int) -> dict[int, ExtractedFact]:
        """Load active facts indexed by id."""
        result = await self._session.execute(
            select(ExtractedFact).where(
                ExtractedFact.intake_id == intake_id,
                ExtractedFact.is_active == True,  # noqa: E712
            )
        )
        facts = result.scalars().all()
        return {f.id: f for f in facts}

    async def _load_gaps(self, run_id: int) -> dict[int, list[AnalysisGap]]:
        """Load open gaps grouped by claim_id."""
        result = await self._session.execute(
            select(AnalysisGap).where(
                AnalysisGap.run_id == run_id,
                AnalysisGap.status == "open",
            )
        )
        gaps = result.scalars().all()
        by_claim: dict[int, list[AnalysisGap]] = defaultdict(list)
        for g in gaps:
            if g.claim_id is not None:
                by_claim[g.claim_id].append(g)
        return dict(by_claim)

    async def _load_all_open_gaps(self, run_id: int) -> list[AnalysisGap]:
        """Load all open gaps for the run (for consolidated report)."""
        result = await self._session.execute(
            select(AnalysisGap).where(
                AnalysisGap.run_id == run_id,
                AnalysisGap.status == "open",
            )
        )
        return list(result.scalars().all())

    async def _load_questions(self, run_id: int) -> list[FollowUpQuestion]:
        result = await self._session.execute(
            select(FollowUpQuestion).where(FollowUpQuestion.run_id == run_id)
        )
        return list(result.scalars().all())

    async def _load_authorities(self, intake_id: int) -> list[Authority]:
        result = await self._session.execute(
            select(Authority).where(Authority.intake_id == intake_id)
        )
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _match_authorities(
        authorities: list[Authority], claim: AnalysisClaim
    ) -> list[Authority]:
        """Filter authorities relevant to a claim by matching claim_iri to folio_iri."""
        if not claim.folio_iri:
            return []
        return [a for a in authorities if a.claim_iri == claim.folio_iri]

    @staticmethod
    def _classify_binding_strength(authority: Authority) -> str:
        """Classify authority binding strength based on type."""
        if authority.authority_type == "secondary":
            return "secondary"
        # For non-secondary types, use a heuristic: same jurisdiction as claim = binding, else persuasive
        # This is a simplification; real implementation would check court hierarchy
        return "persuasive"

    @staticmethod
    def _build_authority_refs(authorities: list[Authority]) -> list[AuthorityRef]:
        """Build sorted AuthorityRef list from Authority records.

        Sort by binding_strength priority (binding first) then relevance_score desc.
        """
        refs = []
        for a in authorities:
            # Classify binding strength
            if a.authority_type == "secondary":
                strength = "secondary"
            elif a.authority_type in ("statute", "regulation", "constitutional", "rule"):
                strength = "binding"
            else:
                # case_law and other -- default to persuasive
                strength = "persuasive"

            refs.append(
                AuthorityRef(
                    citation=a.citation,
                    title=a.title,
                    authority_type=a.authority_type,
                    jurisdiction=a.jurisdiction,
                    binding_strength=strength,
                    verified=a.verified,
                    verification_source=a.verification_source,
                    excerpt=a.excerpt,
                    relevance_score=a.relevance_score,
                    source_url=a.source_url,
                )
            )

        # Sort: binding first, then persuasive, then secondary; within same strength by relevance desc
        refs.sort(
            key=lambda r: (
                _BINDING_ORDER.get(r.binding_strength, 99),
                -(r.relevance_score or 0.0),
            )
        )
        return refs
