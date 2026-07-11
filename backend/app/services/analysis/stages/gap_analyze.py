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
from app.services.analysis.schemas import GapAnalysisResult

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

        # D04 (one source of truth for element support status): an
        # "unsupported_element" gap raised in an EARLIER iteration ("Element X is
        # not yet supported by any facts") becomes STALE once fact-mapping marks
        # that element satisfied / attaches a mapping. Left open, it renders in
        # the memo alongside the same element shown "Supported (85%)" — the
        # self-contradiction Damien flagged. Close the stale gap here so the gap
        # list and the element status derive from the SAME predicate.
        for eg in existing_gaps:
            if eg.status != "open":
                continue
            if eg.gap_type == "unsupported_element" and eg.element_id is not None:
                elem = element_by_id.get(eg.element_id)
                now_supported = (elem is not None and elem.is_satisfied) or (
                    eg.element_id in mappings_by_element_id
                )
                if now_supported:
                    eg.status = "addressed"
                    self.db_session.add(eg)
            elif eg.gap_type == "unexplored_claim" and eg.claim_id is not None:
                if eg.claim_id in mappings_by_claim_id:
                    eg.status = "addressed"
                    self.db_session.add(eg)

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

        # 5. Deterministic doctrine-probe backstop (RUB-01, Damien r1
        # 2026-07-10: EVERY doctrine-level sub-issue fairly raised must be
        # surfaced). The LLM probe above is probabilistic; this cited,
        # human-reviewed table guarantees the enumerated non-obvious linkages
        # (VAWA, U status, § 245(c)(2)/VAWA exemption, Pereira NTA defect,
        # asylum one-year-bar exceptions, OFP grounds, § 518.17 DV custody
        # factor, flight risk, retaliatory eviction) whenever the gathered
        # narrative fairly raises them. Dedupe is by question text so probes
        # are emitted at most once per run.
        doctrine_gaps = await self._detect_deterministic_doctrine_gaps(
            iteration, run, existing_gaps, new_gaps
        )
        new_gaps.extend(doctrine_gaps)

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
            "relief, ELIGIBILITY criteria, statutory EXCEPTIONS, statutory BARS "
            "and their EXEMPTIONS, and procedural DEFECTS an attorney would "
            "investigate. Surface EVERY doctrine-level sub-issue the facts fairly "
            "raise, not just the obvious one (Damien r1 2026-07-10). Examples of "
            "the non-obvious linkages to probe when the facts support them:\n"
            "   - eligibility for a specific immigration relief such as a VAWA "
            "self-petition (battered spouse/child of a U.S. citizen or LPR) or a "
            "U/T visa (victim of a qualifying crime who cooperated with police);\n"
            "   - exceptions to a filing bar, e.g. the asylum one-year-bar "
            "'changed or extraordinary circumstances' exception (incl. notario/"
            "non-lawyer fraud as an extraordinary circumstance);\n"
            "   - a statutory BAR and whether an EXEMPTION applies — e.g. the "
            "INA § 245(c)(2) unauthorized-employment bar to adjustment of status "
            "when someone worked without authorization (e.g. on a borrowed SSN), "
            "AND the fact that VAWA self-petitioners are EXEMPT from that bar "
            "(a non-obvious linkage: ask whether unauthorized work occurred and, "
            "if so, whether a VAWA exemption applies);\n"
            "   - a possible NTA (Notice to Appear) DEFECT under Pereira v. "
            "Sessions / Niz-Chavez v. Garland — ask whether the NTA specified the "
            "TIME, DATE, and PLACE of the first hearing, since a defective NTA may "
            "affect jurisdiction or stop-time for cancellation of removal;\n"
            "   - the statutory best-interest and domestic-abuse factors that "
            "govern a custody decision (e.g. Minn. Stat. § 518.17), grounds for an "
            "Order for Protection (e.g. Minn. Stat. § 518B.01), and "
            "parental-abduction / flight-risk concerns bearing on interim "
            "parenting time.\n"
            "Phrase each as a concrete question a non-lawyer could be asked to "
            "determine whether the doctrine applies. Only surface doctrine the "
            "facts fairly raise; never invent facts.\n\n"
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

    async def _gather_narrative(self, intake_id: int, include_facts: bool = True) -> str:
        """Concatenate consumer/professional message text + document text +
        extracted fact assertions (mirrors DeadlineDetectStage._gather_text so
        the doctrine probes see the same narrative the pipeline analyzed).

        ``include_facts=False`` returns the client narrative + document text ONLY
        (no LLM-extracted fact assertions) — used for domain classification so a
        confabulated fact cannot mis-raise a foreign practice area (round 7)."""
        from sqlalchemy import select

        from app.models.fact import ExtractedFact
        from app.models.intake import IntakeSession, Message

        session_ids = (
            await self.db_session.execute(
                select(IntakeSession.id).where(IntakeSession.intake_id == intake_id)
            )
        ).scalars().all()

        parts: list[str] = []
        if session_ids:
            messages = (
                await self.db_session.execute(
                    select(Message)
                    .where(
                        Message.session_id.in_(session_ids),
                        Message.sender_type != "system",
                    )
                    .order_by(Message.sequence_number)
                )
            ).scalars().all()
            for msg in messages:
                raw = msg.normalized_text or msg.content_encrypted or b""
                text = raw.decode("utf-8", errors="replace").strip()
                if text:
                    parts.append(text)

        if not include_facts:
            return "\n".join(parts)

        facts = (
            await self.db_session.execute(
                select(ExtractedFact).where(
                    ExtractedFact.intake_id == intake_id,
                    ExtractedFact.is_active == True,  # noqa: E712
                )
            )
        ).scalars().all()
        for f in facts:
            if f.assertion_text:
                parts.append(f.assertion_text)

        return "\n".join(parts)

    async def _detect_deterministic_doctrine_gaps(
        self,
        iteration: AnalysisIteration,
        run: AnalysisRun,
        existing_gaps: list[AnalysisGap],
        pending_gaps: list[AnalysisGap],
    ) -> list[AnalysisGap]:
        """Emit the deterministic doctrine-probe backstop (RUB-01, r1).

        Runs the cited probe table over the gathered narrative and emits one
        `procedural_requirement` gap per matched probe. Dedupe is by the probe
        question text against BOTH previously persisted gaps and this batch's
        pending gaps (probes are stable strings, so text-dedupe is exact).
        """
        from app.services.analysis.doctrine_probes import run_probes
        from app.services.analysis.domain_classifier import classify_domains

        try:
            narrative = await self._gather_narrative(run.intake_id)
        except Exception:  # pragma: no cover — backstop must never kill the run
            return []
        if not narrative.strip():
            return []

        # Infer practice-area domain(s) so probes never bleed cross-domain
        # (round 7, BUG-33): an OFP/custody probe cannot fire in a wage-theft or
        # consumer-debt matter, an immigration probe cannot fire on a stray
        # acronym in an unrelated document. Classify from the narrative +
        # documents ONLY (exclude derivative/confabulated facts).
        try:
            classify_text = await self._gather_narrative(
                run.intake_id, include_facts=False
            )
        except Exception:  # pragma: no cover
            classify_text = narrative
        domains = classify_domains(classify_text)

        seen = {g.description for g in existing_gaps} | {
            g.description for g in pending_gaps
        }
        out: list[AnalysisGap] = []
        for probe in run_probes(narrative, domains=domains):
            description = f"{probe.question} [Authority: {probe.authority}]"
            if description in seen:
                continue
            out.append(
                AnalysisGap(
                    run_id=run.id,
                    gap_type="procedural_requirement",
                    claim_id=None,
                    element_id=None,
                    description=description,
                    priority=probe.priority,
                    status="open",
                    iteration_found=iteration.iteration_number,
                )
            )
            seen.add(description)
        return out
