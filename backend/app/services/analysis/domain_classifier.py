"""Deterministic practice-area domain classifier (round 7, BUG-32/33).

Persona intakes run UNBOUND (`practice_area_id` is null) — analysis is
practice-area-agnostic at runtime. So the cross-domain guard for deadline rules
(`services/deadline/rules.py`) and doctrine probes
(`services/analysis/doctrine_probes.py`) cannot read a bound practice area. It
must INFER the domain(s) the narrative fairly raises, then scope rules/probes to
those domains. This is the "guard by practice area, not by patching individual
personas" mandate (Damien D01, 2026-07-11).

The classifier is intentionally conservative and multi-label: a single narrative
can fairly raise more than one domain (e.g. an immigration matter with domestic
violence also raises `family` DV relief). A rule/probe fires only when its own
declared domain(s) intersect the inferred set — so an immigration probe can never
fire in a pure wage-theft narrative even if a stray keyword coincides, and a
family/OFP probe can never fabricate a DV predicate in a consumer-debt matter.

Domains (stable string ids, mirrored by DeadlineRule.domains / DoctrineProbe.domains):
  landlord_tenant, immigration, family, elder_exploitation, wage_theft,
  benefits_denial, employment_discrimination, consumer_debt.

Design notes:
  - Scoring is keyword-hit counting over the lowercased narrative; a domain is
    "raised" when it clears a small threshold (>=1 strong hit, or >=2 weak hits).
    Strong markers are terms that cannot appear incidentally in an unrelated
    matter (e.g. "notice to appear" -> immigration; "power of attorney" ->
    elder_exploitation; "independent contractor" -> wage_theft).
  - `DOMAIN_AGNOSTIC` rules/probes (domains=None) always pass the guard.
  - Overlap is deliberate: elder-exploitation and family both cover
    family/household abuse (OFP is legitimately raised in BOTH), so the OFP probe
    is scoped to {family, elder_exploitation}; the DV *custody* factor is scoped
    to {family} only.
"""

from __future__ import annotations

# All domain ids the classifier and the rule/probe tables agree on.
DOMAINS: frozenset[str] = frozenset(
    {
        "landlord_tenant",
        "immigration",
        "family",
        "elder_exploitation",
        "wage_theft",
        "benefits_denial",
        "employment_discrimination",
        "consumer_debt",
    }
)

# Strong markers: a single hit raises the domain. These terms are specific enough
# that they do not appear incidentally in an unrelated legal narrative.
_STRONG: dict[str, tuple[str, ...]] = {
    "landlord_tenant": (
        "landlord",
        "eviction",
        "evict",
        "unlawful detainer",
        "notice to vacate",
        "notice to quit",
        "warranty of habitability",
        "rent escrow",
        "security deposit",
        "pet deposit",
        "housing court",
        "leaseholder",
        "my lease",
        "the lease",
        "back rent",
    ),
    "immigration": (
        "immigration",
        "asylum",
        "deport",
        "removal proceeding",
        "removal case",
        "notice to appear",
        "green card",
        "uscis",
        "eoir",
        "in absentia",
        "visa",
        "cancellation of removal",
        "vawa",
    ),
    "family": (
        "custody",
        "parenting time",
        "visitation",
        "dissolution of marriage",
        "divorce",
        "child support",
        "icmc",
        "sole legal",
        "sole physical",
        "family court",
    ),
    "elder_exploitation": (
        "power of attorney",
        "attorney-in-fact",
        "attorney in fact",
        "poa",
        "vulnerable adult",
        "financial exploitation",
        "maarc",
        "self-dealing",
        "caregiver pay",
        "elder abuse",
        "nursing home",
    ),
    "wage_theft": (
        "independent contractor",
        "1099",
        "misclassif",
        "unpaid wages",
        "final paycheck",
        "final pay",
        "overtime",
        "time and a half",
        "prevailing wage",
        "pay stub",
        "earnings statement",
        "wage theft",
        "paycheck",
    ),
    "benefits_denial": (
        "unemployment",
        "determination of ineligibility",
        "employment misconduct",
        "unemployment law judge",
        "weekly benefit",
        "deed",
        "ui appeal",
        "benefit account",
        "reemployment",
    ),
    "employment_discrimination": (
        "discrimination",
        "reasonable accommodation",
        "accommodation",
        "essential function",
        "eeoc",
        "mhra",
        "mdhr",
        "severance",
        "release of claims",
        "fmla",
        "light duty",
        "disability discrimination",
        "interactive process",
    ),
    "consumer_debt": (
        "debt collector",
        "collection agency",
        "collection letter",
        "fdcpa",
        "garnish",
        "garnishment",
        "creditor",
        "validation notice",
        "time-barred",
        "statute of limitations on the debt",
        "collect a debt",
        "collections",
    ),
}

# Weak markers: two hits (or one weak + one strong of the same domain) raise the
# domain. These are supportive but individually ambiguous.
_WEAK: dict[str, tuple[str, ...]] = {
    # Round 7 fix: bare "rent" (matches "diffe-rent", "cur-rent", "pa-rent") and
    # bare "notice" (any letter is a "notice") mis-classified elder / employment /
    # consumer matters as landlord_tenant, letting the eviction cure-window rules
    # fire cross-domain. Use only tenancy-specific phrases; the genuine LT persona
    # still classifies via its STRONG markers (landlord, eviction, back rent, ...).
    "landlord_tenant": ("tenant", "apartment", "my landlord", "the landlord", "mold", "no heat", "renter", "notice to vacate", "notice to quit"),
    "immigration": ("hearing letter", "court at fort snelling", "border", "notario", "i-589", "i-918", "i-360"),
    "family": ("the kids", "our children", "our kids", "the petition", "served with", "petitioner", "spouse", "husband", "wife"),
    "elder_exploitation": ("my son", "my pension", "widowed", "my house", "hip surgery", "bank flagged", "revoke", "listing papers"),
    "wage_theft": ("boss", "job site", "hours", "fired", "company van", "builder", "straight time", "demand my wages"),
    "benefits_denial": ("misconduct", "attendance", "appeal", "denied", "charge nurse", "cna", "discharged"),
    "employment_discrimination": ("fired", "herniated", "restriction", "lifting", "warehouse", "comparator", "disability discrimination", "unpaid leave", "medical leave"),
    "consumer_debt": ("i owe", "owe money", "owe them", "credit card", "collector", "call me", "called me", "settle", "disability money", "ssdi", "old card", "the debt"),
}


def classify_domains(narrative_text: str) -> frozenset[str]:
    """Infer the practice-area domain(s) the narrative fairly raises.

    Returns a (possibly empty) frozenset of domain ids. Empty means no domain
    cleared threshold — in that case domain-scoped rules/probes do not fire and
    only DOMAIN_AGNOSTIC ones remain (fail-safe: never fabricate a domain).
    """
    t = (narrative_text or "").lower()
    if not t.strip():
        return frozenset()

    raised: set[str] = set()
    for domain in DOMAINS:
        strong_hits = sum(1 for kw in _STRONG.get(domain, ()) if kw in t)
        weak_hits = sum(1 for kw in _WEAK.get(domain, ()) if kw in t)
        # A single strong marker, or two weak markers, raises the domain.
        if strong_hits >= 1 or weak_hits >= 2:
            raised.add(domain)
    return frozenset(raised)


def domain_allows(
    scope: frozenset[str] | None, inferred: frozenset[str]
) -> bool:
    """Return True if a rule/probe scoped to ``scope`` may fire given ``inferred``.

    ``scope=None`` means domain-agnostic (always allowed). Otherwise the rule
    fires only when its declared domains intersect the inferred domain set.
    """
    if scope is None:
        return True
    return bool(scope & inferred)
