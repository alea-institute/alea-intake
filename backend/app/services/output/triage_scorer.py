"""Multi-factor triage scoring and routing recommendations per D-02.

Scores destinations by four factors:
  1. Practice area match from FOLIO taxonomy (0.35)
  2. Jurisdiction match (0.25)
  3. Complexity assessment (0.20)
  4. Org-specific routing rules (0.20)

Returns ranked TriageRecommendation list with primary practice area,
jurisdiction, complexity level, and urgency level.
"""

from __future__ import annotations

import re
from collections import Counter

from app.services.output.schemas import (
    CIRACSection,
    GapReport,
    OutputContext,
    TriageRecommendation,
    TriageResult,
)


class TriageScorer:
    """Multi-factor triage and routing scorer per D-02."""

    # Configurable default weights
    PRACTICE_AREA_WEIGHT = 0.35
    JURISDICTION_WEIGHT = 0.25
    COMPLEXITY_WEIGHT = 0.20
    ORG_RULES_WEIGHT = 0.20

    def score(
        self,
        context: OutputContext,
        org_routing_rules: dict | None = None,
    ) -> TriageResult:
        """Score and rank routing destinations for an OutputContext.

        Args:
            context: The unified output data structure.
            org_routing_rules: Optional org-specific routing rules
                (boost/penalize destinations by name).

        Returns:
            TriageResult with ranked recommendations.
        """
        all_claims = self._collect_claims(context)
        if not all_claims:
            return TriageResult()

        # 1. Extract distinct practice areas from claims
        practice_areas = self._extract_practice_areas(all_claims)

        # 2. Extract distinct jurisdictions
        jurisdictions = self._extract_jurisdictions(all_claims)

        # 3. Compute complexity level
        gap_count = len(context.gap_report.consolidated_gaps)
        complexity_level = self._compute_complexity(len(all_claims), gap_count)

        # 4. Compute urgency level from gap priorities
        urgency_level = self._compute_urgency(context.gap_report)

        # 5. Build recommendations for each practice area
        recommendations: list[TriageRecommendation] = []
        total_claims = len(all_claims)

        for area, count in practice_areas.items():
            practice_area_match = count / total_claims

            # Jurisdiction match: 1.0 if single jurisdiction, fraction otherwise
            jurisdiction_match = self._compute_jurisdiction_match(
                jurisdictions, area, all_claims
            )

            # Complexity score: inverse (simple cases are easier to route)
            complexity_score = {"low": 0.9, "medium": 0.5, "high": 0.2}[complexity_level]

            # Base score from weighted factors
            score = (
                self.PRACTICE_AREA_WEIGHT * practice_area_match
                + self.JURISDICTION_WEIGHT * jurisdiction_match
                + self.COMPLEXITY_WEIGHT * complexity_score
                + self.ORG_RULES_WEIGHT * self._org_rules_score(area, org_routing_rules)
            )
            score = min(1.0, max(0.0, score))

            rationale = self._build_rationale(
                area, practice_area_match, jurisdiction_match, complexity_level, urgency_level
            )

            recommendations.append(
                TriageRecommendation(
                    destination=area,
                    destination_type="practice_area",
                    score=score,
                    rationale=rationale,
                    practice_area_match=practice_area_match,
                    jurisdiction_match=jurisdiction_match,
                    complexity_score=complexity_score,
                )
            )

        # Apply org-specific adjustments
        if org_routing_rules:
            for rec in recommendations:
                adj = org_routing_rules.get(rec.destination, {})
                if isinstance(adj, dict):
                    boost = adj.get("boost", 0.0)
                    rec.score = min(1.0, max(0.0, rec.score + boost))

        # Sort by score descending
        recommendations.sort(key=lambda r: r.score, reverse=True)

        # Primary practice area and jurisdiction
        primary_practice_area = recommendations[0].destination if recommendations else None
        primary_jurisdiction = (
            jurisdictions.most_common(1)[0][0] if jurisdictions else None
        )

        return TriageResult(
            recommendations=recommendations,
            primary_practice_area=primary_practice_area,
            primary_jurisdiction=primary_jurisdiction,
            complexity_level=complexity_level,
            urgency_level=urgency_level,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _collect_claims(context: OutputContext) -> list[CIRACSection]:
        """Flatten all claims from claims_by_jurisdiction."""
        claims: list[CIRACSection] = []
        for sections in context.claims_by_jurisdiction.values():
            claims.extend(sections)
        return claims

    # BUG-25: keyword -> practice-area map. Each tuple is (area label, keywords).
    # Ordered most-specific first; the first matching area wins. Used only as a
    # human-readable classifier for the triage destination — NEVER claim_type
    # (which is the provenance enum "identified"/"discovered", not an area).
    _PRACTICE_AREA_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("Immigration", ("asylum", "removal", "deportation", "visa", "vawa",
                          "uscis", "immigration", "notario", "naturaliz", "green card")),
        ("Family Law", ("custody", "divorce", "dissolution", "child support",
                        "parenting", "paternity", "guardian", "adoption",
                        "order for protection", "domestic abuse", "alimony",
                        "spousal", "visitation", "family")),
        ("Landlord-Tenant / Housing", ("evict", "eviction", "habitability",
                                       "rent", "lease", "tenant", "landlord",
                                       "notice to vacate", "repair", "mold",
                                       "warranty of habitability", "escrow")),
        ("Employment", ("termination", "wrongful discharge", "wage", "overtime",
                        "harassment", "discrimination", "retaliation",
                        "unemployment", "flsa", "employer", "workplace",
                        "employment")),
        ("Consumer / Debt", ("debt", "collection", "fdcpa", "creditor", "loan",
                             "fraud", "deceptive", "warranty", "repossess")),
        ("Public Benefits", ("snap", "medicaid", "medicare", "benefits",
                             "disability", "ssi", "ssdi", "welfare")),
    )

    @classmethod
    def _classify_practice_area(cls, claim: CIRACSection) -> str:
        """Classify a claim into a human-readable practice area (BUG-25).

        Prefers an explicit AreaOfLaw IRI path when present, then a keyword
        match on the claim name. Falls back to "General Civil" — never the
        claim_type provenance enum.
        """
        if claim.folio_iri and "AreaOfLaw" in claim.folio_iri:
            match = re.search(r"AreaOfLaw[/.](\w+)", claim.folio_iri)
            if match:
                return match.group(1)
        name = (claim.claim_name or "").lower()
        for area, keywords in cls._PRACTICE_AREA_KEYWORDS:
            if any(kw in name for kw in keywords):
                return area
        return "General Civil"

    @classmethod
    def _extract_practice_areas(cls, claims: list[CIRACSection]) -> Counter[str]:
        """Extract human-readable practice areas from claims (BUG-25).

        Never emits the claim_type provenance enum. Derives area from the
        AreaOfLaw IRI path when available, else a keyword classifier over the
        claim name, else "General Civil".
        """
        areas: Counter[str] = Counter()
        for claim in claims:
            areas[cls._classify_practice_area(claim)] += 1
        return areas

    @staticmethod
    def _extract_jurisdictions(claims: list[CIRACSection]) -> Counter[str]:
        """Extract jurisdiction distribution from claims."""
        jurisdictions: Counter[str] = Counter()
        for claim in claims:
            jur = claim.jurisdiction or "General"
            jurisdictions[jur] += 1
        return jurisdictions

    @staticmethod
    def _compute_complexity(claim_count: int, gap_count: int) -> str:
        """Derive complexity level from claim and gap counts.

        - high: >5 claims OR >10 gaps
        - low: <=2 claims AND <=3 gaps
        - medium: everything else
        """
        if claim_count > 5 or gap_count > 10:
            return "high"
        if claim_count <= 2 and gap_count <= 3:
            return "low"
        return "medium"

    @staticmethod
    def _compute_urgency(gap_report: GapReport) -> str:
        """Derive urgency level from max gap priority.

        - emergency: any gap.priority >= 9
        - urgent: any gap.priority >= 7
        - routine: otherwise
        """
        max_priority = 0
        for gap in gap_report.consolidated_gaps:
            if gap.priority > max_priority:
                max_priority = gap.priority
        if max_priority >= 9:
            return "emergency"
        if max_priority >= 7:
            return "urgent"
        return "routine"

    @staticmethod
    def _compute_jurisdiction_match(
        jurisdictions: Counter[str],
        practice_area: str,
        all_claims: list[CIRACSection],
    ) -> float:
        """Compute jurisdiction match score.

        1.0 if all claims share one jurisdiction, lower when mixed.
        """
        distinct = len(jurisdictions)
        if distinct <= 1:
            return 1.0
        # Fraction: how concentrated are jurisdictions?
        # Most common jurisdiction count / total claims
        total = sum(jurisdictions.values())
        most_common_count = jurisdictions.most_common(1)[0][1]
        return most_common_count / total

    @staticmethod
    def _org_rules_score(area: str, org_rules: dict | None) -> float:
        """Compute org-specific routing score (default 0.5 neutral)."""
        if not org_rules:
            return 0.5
        rule = org_rules.get(area, {})
        if isinstance(rule, dict):
            return rule.get("preference", 0.5)
        return 0.5

    @staticmethod
    def _build_rationale(
        area: str,
        practice_area_match: float,
        jurisdiction_match: float,
        complexity_level: str,
        urgency_level: str,
    ) -> str:
        """Build human-readable rationale for recommendation."""
        parts = [
            f"{area} practice area ({practice_area_match:.0%} of claims)",
        ]
        if jurisdiction_match == 1.0:
            parts.append("single jurisdiction (strong match)")
        else:
            parts.append(f"mixed jurisdictions ({jurisdiction_match:.0%} concentration)")
        parts.append(f"{complexity_level} complexity")
        if urgency_level != "routine":
            parts.append(f"{urgency_level} urgency")
        return "; ".join(parts)
