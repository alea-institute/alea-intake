"""Question generation stage -- LLM-driven consumer-friendly follow-up questions.

Implements D-10 (topic grouping), D-11 (all gaps produce questions),
D-12 (configurable rationale transparency). Generates questions from
gap analysis results and persists them as FollowUpQuestion records.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis import (
    AnalysisGap,
    AnalysisIteration,
    AnalysisRun,
    FollowUpQuestion,
)
from app.services.analysis.schemas import QuestionGenResult

if TYPE_CHECKING:
    from app.services.llm_service import LLMService


class QuestionGenStage:
    """Generate consumer-friendly follow-up questions from analysis gaps.

    Questions are:
      - Grouped by topic area (D-10)
      - Ranked by priority (highest-impact gaps first)
      - Optionally include rationale (D-12, controlled by question_transparency)
      - Linked to source gaps via gap_id
      - Deduplicated against previously answered questions
    """

    def __init__(
        self,
        llm_service: LLMService,
        db_session: AsyncSession,
        question_transparency: bool = True,
    ) -> None:
        self.llm_service = llm_service
        self.db_session = db_session
        self.question_transparency = question_transparency

    async def execute(
        self,
        run: AnalysisRun,
        iteration: AnalysisIteration,
        gaps: list[AnalysisGap],
        consumer_context: str = "",
        existing_questions: list[FollowUpQuestion] | None = None,
    ) -> dict[str, Any]:
        """Generate follow-up questions from gap analysis results.

        Args:
            run: The current analysis run.
            iteration: The current iteration within the run.
            gaps: Gaps to generate questions for.
            consumer_context: Consumer narrative for LLM context.
            existing_questions: Previously generated questions to avoid duplicates.

        Returns:
            Dict with questions_generated, topic_groups, total_questions.
        """
        # Filter to open gaps only
        open_gaps = [g for g in gaps if g.status == "open"]

        if not open_gaps:
            return {
                "questions_generated": 0,
                "topic_groups": [],
                "total_questions": 0,
            }

        # Build set of already-answered question texts
        answered_texts: set[str] = set()
        if existing_questions:
            for eq in existing_questions:
                if eq.status == "answered":
                    answered_texts.add(eq.question_text)

        # Build gap lookup by description for matching LLM output to gaps
        gap_by_description: dict[str, AnalysisGap] = {}
        for g in open_gaps:
            gap_by_description[g.description] = g

        # Build LLM prompt
        gap_descriptions = "\n".join(
            f"- [{g.gap_type}] (priority={g.priority}): {g.description}"
            for g in open_gaps
        )

        prompt = (
            f"Generate consumer-friendly follow-up questions based on the following gaps in the legal analysis. "
            f"Do NOT use legal jargon. Group questions by topic area. "
            f"Rank questions by priority (highest-impact gaps first). "
            f"Include a rationale for each question explaining why we are asking.\n\n"
            f"Gaps:\n{gap_descriptions}\n\n"
        )
        if consumer_context:
            prompt += f"Consumer's story so far: {consumer_context}\n\n"
        prompt += (
            f"Return questions grouped by topic. Each question must reference the gap it addresses "
            f"by including the gap description in gap_description.\n\n"
            'Return ONLY a JSON object with EXACTLY this structure:\n'
            '{"groups": [{"topic": "topic name", "questions": [{"question_text": "the question", '
            '"rationale": "why we ask", "priority": 1, "gap_description": "the gap addressed"}]}], '
            '"total_questions": 0}'
        )

        # Call LLM
        try:
            result: QuestionGenResult = await self.llm_service.json_async(
                prompt=prompt,
                schema=QuestionGenResult,
            )
        except Exception:
            return {
                "questions_generated": 0,
                "topic_groups": [],
                "total_questions": 0,
            }

        # Persist questions
        questions_generated = 0
        topic_groups: list[str] = []

        for group in result.groups:
            topic_groups.append(group.topic)
            for q_schema in group.questions:
                # Skip already-answered questions
                if q_schema.question_text in answered_texts:
                    continue

                # Match gap by description
                matched_gap = None
                if q_schema.gap_description:
                    matched_gap = gap_by_description.get(q_schema.gap_description)
                    if matched_gap is None:
                        # Fuzzy match: find first gap whose description is a substring
                        for desc, gap in gap_by_description.items():
                            if q_schema.gap_description in desc or desc in q_schema.gap_description:
                                matched_gap = gap
                                break

                # Determine rationale based on transparency setting
                rationale = q_schema.rationale if self.question_transparency else None

                question = FollowUpQuestion(
                    run_id=run.id,
                    gap_id=matched_gap.id if matched_gap else None,
                    question_text=q_schema.question_text,
                    topic_group=group.topic,
                    priority=q_schema.priority,
                    rationale=rationale,
                    status="pending",
                    iteration_asked=iteration.iteration_number,
                )
                self.db_session.add(question)
                questions_generated += 1

        await self.db_session.flush()

        return {
            "questions_generated": questions_generated,
            "topic_groups": topic_groups,
            "total_questions": questions_generated,
        }
