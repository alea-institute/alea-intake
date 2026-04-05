"""Gap report builder -- inline + appendix gap analysis (D-07).

Builds per-claim gap groupings and a consolidated gap appendix with
completeness scoring from convergence evaluator output.
"""

from __future__ import annotations

from typing import Any

from app.services.output.schemas import GapEntry, GapReport


class GapReportBuilder:
    """Builds inline + appendix gap analysis per D-07."""

    @staticmethod
    def build(
        gaps: list[Any],
        questions: list[Any],
        claims: dict[int, str],  # claim_id -> claim_name
        elements: dict[int, str],  # element_id -> element_name
        convergence_score: float | None,
    ) -> GapReport:
        """Build a GapReport from raw gap and question data.

        Args:
            gaps: AnalysisGap records (or SimpleNamespace with matching attrs).
            questions: FollowUpQuestion records.
            claims: Mapping from claim_id to claim_name.
            elements: Mapping from element_id to element_name.
            convergence_score: Overall convergence score from analysis run.

        Returns:
            GapReport with per_claim grouping, consolidated list, open questions.
        """
        # Build GapEntry list
        entries: list[GapEntry] = []
        for g in gaps:
            entry = GapEntry(
                gap_id=g.id,
                gap_type=g.gap_type,
                description=g.description,
                priority=g.priority,
                claim_id=g.claim_id,
                element_id=g.element_id,
                claim_name=claims.get(g.claim_id) if g.claim_id else None,
                element_name=elements.get(g.element_id) if g.element_id else None,
            )
            entries.append(entry)

        # Group by claim
        per_claim: dict[str, list[GapEntry]] = {}
        for entry in entries:
            key = entry.claim_name or "Uncategorized"
            per_claim.setdefault(key, []).append(entry)

        # Consolidated: sorted by priority desc
        consolidated = sorted(entries, key=lambda e: e.priority, reverse=True)

        # Open questions: only pending
        open_questions = [
            q.question_text for q in questions if q.status == "pending"
        ]

        return GapReport(
            per_claim=per_claim,
            consolidated_gaps=consolidated,
            open_questions=open_questions,
            completeness_score=convergence_score if convergence_score is not None else 0.0,
        )
