"""Gap-to-action-item transformation with prioritization and categorization per D-03.

Transforms AnalysisGap entries into prioritized, categorized ActionItems:
- Documents to gather (unsupported elements, weak mappings)
- Follow-up steps (unexplored claims, procedural requirements)
- Referrals (practice areas with severe gaps / low completeness)

Items are sorted by priority (urgent > important > helpful) and category,
numbered sequentially, and cross-linked back to their source GapEntry.
"""

from __future__ import annotations

from app.services.output.schemas import (
    ActionItem,
    CIRACSection,
    GapReport,
)


# Gap type -> action item category mapping
_GAP_TYPE_TO_CATEGORY: dict[str, str] = {
    "unsupported_element": "documents_to_gather",
    "weak_mapping": "documents_to_gather",
    "unexplored_claim": "follow_up_steps",
    "procedural_requirement": "follow_up_steps",
}

# Category sort order: documents_to_gather < follow_up_steps < referrals
_CATEGORY_ORDER: dict[str, int] = {
    "documents_to_gather": 0,
    "follow_up_steps": 1,
    "referrals": 2,
}

# Priority sort order: urgent < important < helpful
_PRIORITY_ORDER: dict[str, int] = {
    "urgent": 0,
    "important": 1,
    "helpful": 2,
}

# Completeness threshold below which a practice area triggers a referral item
_REFERRAL_COMPLETENESS_THRESHOLD = 0.3


class ActionItemGenerator:
    """Transforms gaps into prioritized, categorized action items per D-03."""

    def generate(
        self,
        gap_report: GapReport,
        claims_by_jurisdiction: dict[str, list[CIRACSection]],
    ) -> list[ActionItem]:
        """Generate action items from a gap report.

        Args:
            gap_report: Consolidated gap report with per-claim and global gaps.
            claims_by_jurisdiction: Claims grouped by jurisdiction (for referral detection).

        Returns:
            Sorted list of ActionItem, numbered starting at 1.
        """
        items: list[ActionItem] = []

        # 1. Generate items from consolidated gaps
        for gap in gap_report.consolidated_gaps:
            category = _GAP_TYPE_TO_CATEGORY.get(gap.gap_type, "follow_up_steps")
            priority = self._map_priority(gap.priority)

            # Deadline from metadata for procedural requirements
            deadline = None
            if gap.gap_type == "procedural_requirement" and gap.open_questions:
                # Use first open question as a hint for deadline context
                deadline = None  # No structured deadline data in GapEntry currently

            item = ActionItem(
                item_number=0,  # Placeholder; renumbered after sort
                category=category,
                description=gap.description,
                priority=priority,
                deadline=deadline,
                claim_ref=gap.claim_name,
                element_ref=gap.element_name,
            )
            items.append(item)

        # 2. Referral items for practice areas with low completeness
        referral_items = self._generate_referrals(gap_report, claims_by_jurisdiction)
        items.extend(referral_items)

        # 3. Sort: priority first (urgent > important > helpful),
        #    then category (documents > follow_up > referrals)
        items.sort(
            key=lambda i: (
                _PRIORITY_ORDER.get(i.priority, 99),
                _CATEGORY_ORDER.get(i.category, 99),
            )
        )

        # 4. Number sequentially starting at 1
        for idx, item in enumerate(items, start=1):
            item.item_number = idx

        # 5. Cross-link: set gap's action_item_ref for each matched gap
        self._cross_link(gap_report, items)

        return items

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _map_priority(gap_priority: int) -> str:
        """Map numeric gap priority to action item priority label.

        - >= 8 -> urgent
        - >= 5 -> important
        - < 5  -> helpful
        """
        if gap_priority >= 8:
            return "urgent"
        if gap_priority >= 5:
            return "important"
        return "helpful"

    @staticmethod
    def _generate_referrals(
        gap_report: GapReport,
        claims_by_jurisdiction: dict[str, list[CIRACSection]],
    ) -> list[ActionItem]:
        """Generate referral items for practice areas with severe gaps.

        A practice area triggers a referral if:
        - It has many gaps (per_claim count > threshold)
        - Overall completeness < _REFERRAL_COMPLETENESS_THRESHOLD
        """
        referrals: list[ActionItem] = []

        if gap_report.completeness_score >= _REFERRAL_COMPLETENESS_THRESHOLD:
            return referrals

        # Find practice areas (claim types) with many gaps
        area_gap_count: dict[str, int] = {}
        for claim_name, gaps in gap_report.per_claim.items():
            # Derive practice area from the claim's type in claims_by_jurisdiction
            area = None
            for sections in claims_by_jurisdiction.values():
                for section in sections:
                    if section.claim_name == claim_name:
                        area = section.claim_type
                        break
                if area:
                    break
            if area:
                area_gap_count[area] = area_gap_count.get(area, 0) + len(gaps)

        for area, count in area_gap_count.items():
            if count >= 3:  # Threshold for suggesting referral
                referrals.append(
                    ActionItem(
                        item_number=0,
                        category="referrals",
                        description=(
                            f"Consider referral to {area} specialist -- "
                            f"significant gaps identified ({count} gaps, "
                            f"{gap_report.completeness_score:.0%} completeness)"
                        ),
                        priority="important",
                        claim_ref=None,
                        element_ref=None,
                    )
                )

        return referrals

    @staticmethod
    def _cross_link(gap_report: GapReport, items: list[ActionItem]) -> None:
        """Cross-link action_item_ref on GapEntry to the generated ActionItem number.

        Matches by description equality between the gap's description and the action item.
        """
        item_by_desc: dict[str, int] = {
            item.description: item.item_number for item in items
        }
        for gap in gap_report.consolidated_gaps:
            ref = item_by_desc.get(gap.description)
            if ref is not None:
                gap.action_item_ref = ref
