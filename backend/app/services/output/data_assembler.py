"""Data assembler -- queries all upstream analysis/research data into a unified OutputContext.

Pattern: single DB session loads claims, elements, mappings, gaps, questions,
authorities, and facts, then assembles them into the format-neutral OutputContext
for downstream rendering.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from datetime import datetime, timezone
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis import (
    AnalysisClaim,
    AnalysisGap,
    AnalysisRun,
    ClaimElement,
    Deadline,
    FactClaimMapping,
    FollowUpQuestion,
)
from app.models.fact import ExtractedFact
from app.models.intake import Intake, IntakeSession, Message
from app.models.research import Authority
from app.services.output.gap_report_builder import GapReportBuilder
from app.services.output.schemas import (
    AdditionalClaimRef,
    AuthorityRef,
    CIRACSection,
    DeadlineRef,
    ElementRef,
    FactMappingRef,
    GapEntry,
    GapReport,
    OutputContext,
    OutputProfile,
    SafetyAlertRef,
)

logger = logging.getLogger(__name__)

# Binding strength ordering: lower = higher priority
_BINDING_ORDER = {"binding": 0, "persuasive": 1, "secondary": 2}

# Urgency ordering for the top deadlines section: lower = more prominent.
_URGENCY_ORDER = {"lapsed": 0, "high": 1, "medium": 2, "low": 3, "unknown": 4}

# Safety severity ordering for the top safety section: lower = more prominent.
_SEVERITY_ORDER = {"critical": 0, "elevated": 1, "advisory": 2}

# q10: the memo renders FULL CIRAC sections for only the top N claims per
# jurisdiction (roots + nested children both count against the cap). The rest
# render as a compact "More possible issues" list and stay in the JSON export.
MEMO_CLAIM_CAP = 7

# Adjacency-discovered claims record their parent only in the rationale text
# (see app/services/exploration/layers.py): "... from <parent claim name> (depth N)".
_ADJACENCY_PARENT_RE = re.compile(r"\bfrom (.+?) \(depth \d+\)")


def _parent_claim_name(claim: AnalysisClaim) -> str | None:
    """Resolve the parent-claim linkage for exploration-discovered claims (q10).

    Prefers an explicit ``metadata_json["parent_claim_name"]`` when present;
    otherwise, for discovered/exploration claims only, parses the adjacency
    rationale's "from <parent claim name> (depth N)" suffix.
    """
    meta = claim.metadata_json if isinstance(claim.metadata_json, dict) else {}
    explicit = meta.get("parent_claim_name")
    if explicit:
        return str(explicit)
    if claim.claim_type != "discovered" and not meta.get("source_layer"):
        return None
    match = _ADJACENCY_PARENT_RE.search(claim.rationale or "")
    return match.group(1) if match else None


def group_and_cap_sections(
    sections: list[CIRACSection], cap: int = MEMO_CLAIM_CAP
) -> tuple[list[CIRACSection], list[AdditionalClaimRef]]:
    """Group claim sections by relation and cap full rendering at ``cap`` (q10).

    - Sections whose ``parent_claim_name`` matches another section in the same
      jurisdiction nest under that parent (grandchildren nest recursively);
      everything else is a root.
    - Roots are ordered by confidence desc; children by confidence desc within
      their parent (siblings stay together, never interleaved with other roots).
    - The cap counts roots and children alike, roots prioritized: roots fill
      the budget first, then children of displayed sections by confidence desc.
    - Overflow is returned as compact ``AdditionalClaimRef`` entries (nothing
      is dropped), each noting its parent when applicable.

    Deterministic: ties break on normalized claim name.
    """

    def sort_key(s: CIRACSection) -> tuple[float, str]:
        return (-s.confidence, _normalize(s.claim_name))

    by_name: dict[str, CIRACSection] = {}
    for s in sections:
        by_name.setdefault(_normalize(s.claim_name), s)

    roots: list[CIRACSection] = []
    parented: list[CIRACSection] = []
    for s in sections:
        parent = (
            by_name.get(_normalize(s.parent_claim_name))
            if s.parent_claim_name
            else None
        )
        if parent is not None and parent is not s:
            parented.append(s)
        else:
            # Parent unknown in this jurisdiction: render as a plain root.
            s.parent_claim_name = None
            roots.append(s)

    roots.sort(key=sort_key)
    parented.sort(key=sort_key)

    # Cycle guard (CE review): if every section resolves to a parent (a
    # parent_claim_name cycle), roots would be empty and the memo would render
    # ONLY the overflow list. Promote the highest-confidence section to root.
    if not roots and parented:
        promoted = parented.pop(0)
        promoted.parent_claim_name = None
        roots.append(promoted)

    displayed_roots = roots[:cap]
    budget = cap - len(displayed_roots)
    displayed_by_name = {_normalize(r.claim_name): r for r in displayed_roots}

    # Attach children (and grandchildren, once their parent is displayed) in
    # global confidence-desc order until the budget is exhausted.
    remaining = list(parented)
    progress = True
    while budget > 0 and progress:
        progress = False
        for s in list(remaining):
            parent = displayed_by_name.get(_normalize(s.parent_claim_name or ""))
            if parent is None:
                continue
            parent.children.append(s)
            displayed_by_name.setdefault(_normalize(s.claim_name), s)
            remaining.remove(s)
            budget -= 1
            progress = True
            if budget == 0:
                break

    overflow = sorted(roots[cap:] + remaining, key=sort_key)
    additional = [
        AdditionalClaimRef(
            claim_name=s.claim_name,
            claim_type=s.claim_type,
            confidence=s.confidence,
            jurisdiction=s.jurisdiction,
            folio_iri=s.folio_iri,
            parent_claim_name=s.parent_claim_name,
        )
        for s in overflow
    ]
    return displayed_roots, additional


def _normalize(text: str) -> str:
    """Shared dedup key: lowercase, collapse whitespace, strip trailing punctuation.

    Used to collapse duplicate questions and duplicate claim/memo sections that
    the convergence loop's per-iteration re-runs and per-jurisdiction fan-out
    would otherwise emit repeatedly (BUG-14).
    """
    if not text:
        return ""
    collapsed = re.sub(r"\s+", " ", text).strip().lower()
    return collapsed.rstrip(".?!:;,")


def build_executive_summary(
    claims_by_jurisdiction: dict[str, list[CIRACSection]],
    additional_by_jurisdiction: dict[str, list[AdditionalClaimRef]],
    deadlines: list[DeadlineRef],
    safety_alerts: list[SafetyAlertRef],
    gap_report: GapReport,
    completeness_score: float,
) -> str:
    """Synthesize a factual, professional-register executive summary (BUG-23).

    The assembler previously hardcoded ``executive_summary=""``, so every memo
    and export shipped with an empty summary — a GATE failure under RUB-15
    (Damien ruling Q6, 2026-07-08). This builds a grounded summary from data
    the pipeline already produced: no new facts are invented (RUB-04), and any
    primary-source citation carried on a deadline is preserved verbatim so the
    downstream language adapter's citation-restore pass keeps it intact.

    Deterministic and LLM-free: consumer profiles rewrite this to plain language
    via ``LanguageAdapter`` (which only runs when the field is non-empty).
    """
    all_sections: list[CIRACSection] = []
    for secs in claims_by_jurisdiction.values():
        all_sections.extend(secs)
    total_issues = sum(len(v) for v in claims_by_jurisdiction.values()) + sum(
        len(v) for v in additional_by_jurisdiction.values()
    )
    jurisdictions = sorted(
        j for j in claims_by_jurisdiction.keys() if j and j != "General"
    )

    parts: list[str] = []

    # 1. Issues found, naming the strongest by confidence.
    if total_issues:
        top = sorted(all_sections, key=lambda s: -s.confidence)[:3]
        top_names = [s.claim_name for s in top if s.claim_name]
        issue_word = "legal issue" if total_issues == 1 else "legal issues"
        lead = f"This intake surfaced {total_issues} potential {issue_word}"
        if jurisdictions:
            lead += f" across {', '.join(jurisdictions)}"
        if top_names:
            lead += ". The most strongly supported " + (
                "issue is " if len(top_names) == 1 else "issues are "
            ) + _oxford_join(top_names)
        parts.append(lead.rstrip(".") + ".")
    else:
        parts.append(
            "No legal issues were confidently identified from the information "
            "provided so far; the follow-up questions below are needed before "
            "the matter can be assessed."
        )

    # 2. Deadlines FIRST-CLASS — lapsed/urgent items are the highest-stakes
    #    content and must appear in the summary (RUB-08). Citation preserved.
    if deadlines:
        lapsed = [d for d in deadlines if d.urgency == "lapsed"]
        computed = [d for d in deadlines if d.computed and d.computed_date]
        if lapsed:
            d = lapsed[0]
            sent = (
                f"IMPORTANT: at least one deadline appears to have already "
                f"passed — {d.event_text}"
            )
            if d.computed_date:
                sent += f" (computed {d.computed_date})"
            if d.citation:
                sent += f" [{d.citation}]"
            parts.append(sent.rstrip(".") + ". Confirm this immediately, as "
                         "missed deadlines can end a case.")
        elif computed:
            d = sorted(
                computed, key=lambda x: _URGENCY_ORDER.get(x.urgency, 99)
            )[0]
            sent = f"A time-sensitive deadline was computed: {d.event_text}"
            if d.computed_date:
                sent += f" by {d.computed_date}"
            if d.citation:
                sent += f" [{d.citation}]"
            parts.append(sent.rstrip(".") + ".")
        else:
            parts.append(
                f"{len(deadlines)} time-sensitive item(s) were detected; confirm "
                "the exact dates with the court or a lawyer."
            )

    # 3. Safety — calm, actionable.
    if safety_alerts:
        parts.append(
            "Safety concerns were detected in this narrative; see the safety "
            "resources below."
        )

    # 4. Completeness + open questions.
    open_q = len(getattr(gap_report, "open_questions", []) or [])
    if open_q:
        q_word = "question" if open_q == 1 else "questions"
        parts.append(
            f"Analysis completeness is {completeness_score:.0%}; {open_q} "
            f"follow-up {q_word} below would strengthen the assessment."
        )
    elif completeness_score:
        parts.append(f"Analysis completeness is {completeness_score:.0%}.")

    return " ".join(parts).strip()


def _oxford_join(items: list[str]) -> str:
    """Join names as 'A', 'A and B', or 'A, B, and C'."""
    items = [i for i in items if i]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + ", and " + items[-1]


async def _gather_narrative_text(session: AsyncSession, intake_id: int) -> str:
    """Concatenate the intake's non-system message text + active fact assertions.

    Mirrors ``DeadlineDetectStage._gather_text`` so the safety pass sees the same
    narrative the pipeline extracted facts from.
    """
    session_ids = (
        await session.execute(
            select(IntakeSession.id).where(IntakeSession.intake_id == intake_id)
        )
    ).scalars().all()

    parts: list[str] = []
    if session_ids:
        messages = (
            await session.execute(
                select(Message)
                .where(
                    Message.session_id.in_(session_ids),
                    Message.sender_type != "system",
                )
                .order_by(Message.sequence_number)
            )
        ).scalars().all()
        for msg in messages:
            # BUG-27: prefer extracted document text (normalized_text) so the
            # safety pass sees upload content; content_encrypted is the filename
            # for uploads.
            raw = msg.normalized_text or msg.content_encrypted or b""
            text = raw.decode("utf-8", errors="replace").strip() if isinstance(raw, bytes) else str(raw).strip()
            if text:
                parts.append(text)

    facts = (
        await session.execute(
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


def _build_seed_matcher():
    """Build a TriggerMatcher from the built-in seed protocol definitions.

    Reuses the EXISTING screening ``TriggerMatcher`` (no new detector) but sources
    triggers directly from ``SEED_PROTOCOLS`` rather than DB activations. This makes
    the analysis-time safety pass work even when protocols were never activated in
    the tenant (the DV screening previously only ran on the live-message WebSocket
    path), satisfying "load the built-in seeds" for BUG-15.

    Returns ``(matcher, resources_by_name)`` where resources_by_name maps a
    protocol name to its ``safety_resources`` dict (hotlines / emergency / plan).
    """
    from app.services.screening.seed_protocols import SEED_PROTOCOLS
    from app.services.screening.trigger_matcher import TriggerMatcher

    protocol_tuples: list[tuple] = []
    resources_by_name: dict[str, dict] = {}
    for idx, proto in enumerate(SEED_PROTOCOLS, start=1):
        version = SimpleNamespace(
            id=idx,
            trigger_conditions_json=proto.get("trigger_conditions", {}),
            _protocol_name=proto["name"],
            _severity_tier=proto["severity_tier"],
        )
        activation = SimpleNamespace(protocol_id=idx)
        protocol_tuples.append((activation, version))
        resources_by_name[proto["name"]] = proto.get("safety_resources") or {}

    return TriggerMatcher(protocol_tuples), resources_by_name


# Protocol-name substrings that put an alert in the "DV advocate" domain --
# mirrors the memo template's DV-advocate block condition (safety_alerts.md.j2).
_DV_DOMAIN_MARKERS = ("violence", "abuse", "stalking")


def _ensure_dv_hotline_for_dv_domain(
    alerts: list[SafetyAlertRef], resources_by_name: dict[str, dict]
) -> None:
    """Guarantee the National DV Hotline is present when the DV-advocate domain
    is active (BUG-20). Mutates ``alerts`` in place.

    The memo tells DV/abuse/stalking clients to reach a domestic-violence
    advocate "through the hotline above". That guidance must be backed by an
    actual DV hotline. If the DV-domain is active but no fired alert carries a
    hotline named for domestic violence, attach the DV protocol's hotline to the
    most relevant DV-domain alert.
    """
    if not alerts:
        return

    dv_domain_alerts = [
        a
        for a in alerts
        if any(m in a.protocol_name.lower() for m in _DV_DOMAIN_MARKERS)
    ]
    if not dv_domain_alerts:
        return

    def _has_dv_hotline(alert: SafetyAlertRef) -> bool:
        return any(
            "domestic violence" in (h.get("name", "") or "").lower()
            or h.get("phone") == "1-800-799-7233"
            for h in alert.hotlines
        )

    if any(_has_dv_hotline(a) for a in dv_domain_alerts):
        return

    # Find the DV protocol's hotlines from the seed resources.
    dv_hotlines: list[dict] = []
    for name, resources in resources_by_name.items():
        if "domestic violence" in name.lower():
            dv_hotlines = resources.get("hotlines", []) or []
            break
    if not dv_hotlines:
        return

    # Prefer an actual DV/abuse alert; otherwise the first DV-domain alert
    # (e.g. Stalking) so the "hotline above" reference resolves.
    target = next(
        (
            a
            for a in dv_domain_alerts
            if "violence" in a.protocol_name.lower() or "abuse" in a.protocol_name.lower()
        ),
        dv_domain_alerts[0],
    )
    existing_names = {(h.get("name", "") or "").lower() for h in target.hotlines}
    for h in dv_hotlines:
        if (h.get("name", "") or "").lower() not in existing_names:
            target.hotlines.append(h)


async def gather_safety_alerts(
    session: AsyncSession, intake_id: int
) -> list[SafetyAlertRef]:
    """Run the existing screening matcher over the intake narrative (BUG-15).

    SAFETY CRITICAL: the analysis pipeline had NO safety detection, so a DV
    narrative produced ``safety_alerts=0``. This decoupled, deterministic pass
    (keyword/regex only, no LLM) surfaces DV / self-harm / trafficking concerns so
    the memo can render calm escalation guidance. Degrades gracefully: any failure
    yields an empty list and never breaks output generation.
    """
    try:
        text = await _gather_narrative_text(session, intake_id)
        if not text.strip():
            return []

        matcher, resources_by_name = _build_seed_matcher()
        triggered = matcher.match_fast(text)

        alerts: list[SafetyAlertRef] = []
        seen: set[str] = set()
        for tp in triggered:
            if tp.protocol_name in seen:
                continue
            seen.add(tp.protocol_name)
            resources = resources_by_name.get(tp.protocol_name, {})
            alerts.append(
                SafetyAlertRef(
                    protocol_name=tp.protocol_name,
                    severity_tier=tp.severity_tier,
                    matched_terms=tp.matched_terms,
                    hotlines=resources.get("hotlines", []) or [],
                    emergency=resources.get("emergency"),
                    safety_planning=resources.get("safety_planning"),
                )
            )

        # BUG-20: condition resources on the alert DOMAIN. The memo's
        # DV-advocate guidance ("reach a domestic violence advocate through the
        # hotline above") renders whenever a violence / abuse / IPV / stalking
        # alert fires. If the fired alerts happen NOT to carry a DV hotline
        # (e.g. only a Stalking alert fired, whose sole resource is SPARC), the
        # guidance would point at a non-DV hotline. Guarantee that when the
        # DV-advocate domain is active, the National Domestic Violence Hotline
        # is present so the guidance is never domain-mismatched.
        _ensure_dv_hotline_for_dv_domain(alerts, resources_by_name)

        alerts.sort(key=lambda a: _SEVERITY_ORDER.get(a.severity_tier, 99))
        return alerts
    except Exception:
        logger.warning(
            "Safety screening failed for intake %d; no safety alerts produced",
            intake_id,
            exc_info=True,
        )
        return []


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
        deadlines = await self._load_deadlines(run_id)
        safety_alerts = await gather_safety_alerts(self._session, intake_id)

        # Build CIRAC sections
        sections_by_jurisdiction: dict[str, list[CIRACSection]] = defaultdict(list)
        # Dedup claim sections across the per-jurisdiction fan-out: the same claim
        # (same normalized name + folio_iri) must render only once (BUG-14).
        seen_claim_keys: set[tuple[str, str]] = set()

        for claim in claims:
            jurisdiction = claim.jurisdiction or "General"

            claim_key = (_normalize(claim.claim_name), claim.folio_iri or "")
            if claim_key in seen_claim_keys:
                continue
            seen_claim_keys.add(claim_key)

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

            # D04 (one source of truth): defensively suppress any
            # "unsupported_element" gap whose element is actually satisfied /
            # mapped in this same assembly, so the memo can never show an element
            # as "Supported (85%)" while also listing it "not yet supported by
            # any facts". gap_analyze closes these at detection time; this is the
            # belt-and-suspenders at the rendering boundary.
            satisfied_element_ids = {
                e.element_id for e in element_refs if e.is_satisfied or e.fact_mappings
            }
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
                if not (
                    g.gap_type == "unsupported_element"
                    and g.element_id in satisfied_element_ids
                )
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
                parent_claim_name=_parent_claim_name(claim),
            )
            sections_by_jurisdiction[jurisdiction].append(section)

        # q10: exploration-discovered claims carry no jurisdiction of their own
        # (they land in "General"), so first move each child into its parent's
        # jurisdiction bucket (following the parent chain for grandchildren).
        name_to_section: dict[str, CIRACSection] = {}
        section_jur: dict[int, str] = {}
        for jur, secs in sections_by_jurisdiction.items():
            for s in secs:
                name_to_section.setdefault(_normalize(s.claim_name), s)
                section_jur[id(s)] = jur

        def _target_jurisdiction(section: CIRACSection) -> str:
            seen: set[int] = {id(section)}
            cur = section
            while cur.parent_claim_name:
                parent = name_to_section.get(_normalize(cur.parent_claim_name))
                if parent is None or id(parent) in seen:
                    break
                seen.add(id(parent))
                cur = parent
            return section_jur[id(cur)]

        regrouped: dict[str, list[CIRACSection]] = defaultdict(list)
        for secs in sections_by_jurisdiction.values():
            for s in secs:
                regrouped[_target_jurisdiction(s)].append(s)

        # Group related claims under their parent and cap full sections at
        # MEMO_CLAIM_CAP per jurisdiction; overflow becomes the compact list.
        claims_by_jurisdiction: dict[str, list[CIRACSection]] = {}
        additional_by_jurisdiction: dict[str, list[AdditionalClaimRef]] = {}
        for jur, secs in regrouped.items():
            displayed, additional = group_and_cap_sections(secs)
            claims_by_jurisdiction[jur] = displayed
            if additional:
                additional_by_jurisdiction[jur] = additional

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

        # BUG-23 (RUB-15 GATE, Damien Q6): synthesize a real executive summary
        # from the assembled data. An empty summary now fails the export gate.
        executive_summary = build_executive_summary(
            claims_by_jurisdiction=claims_by_jurisdiction,
            additional_by_jurisdiction=additional_by_jurisdiction,
            deadlines=deadlines,
            safety_alerts=safety_alerts,
            gap_report=gap_report,
            completeness_score=completeness,
        )

        return OutputContext(
            intake_id=intake_id,
            run_id=run_id,
            org_id=intake.org_id if intake else 0,
            matter_title=matter_title,
            generated_at=datetime.now(timezone.utc),
            claims_by_jurisdiction=claims_by_jurisdiction,
            additional_claims_by_jurisdiction=additional_by_jurisdiction,
            safety_alerts=safety_alerts,
            deadlines=deadlines,
            triage=None,
            action_items=[],
            gap_report=gap_report,
            completeness_score=completeness,
            executive_summary=executive_summary,
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

        # BUG-26: FactMapStage re-runs every convergence iteration and persists a
        # fresh mapping row each pass with no upsert, so the SAME (element, fact)
        # pair accumulated 11-20 duplicate rows -> the memo rendered the same
        # fact span a dozen times under one element. Collapse to one row per
        # (element_id, fact_id), keeping the highest-confidence representative.
        best_by_pair: dict[tuple[int, int], FactClaimMapping] = {}
        for m in mappings:
            if m.element_id is None:
                continue
            pair = (m.element_id, m.fact_id)
            existing = best_by_pair.get(pair)
            if existing is None or (m.confidence or 0.0) > (existing.confidence or 0.0):
                best_by_pair[pair] = m

        by_element: dict[int, list[FactClaimMapping]] = defaultdict(list)
        for (element_id, _fact_id), m in best_by_pair.items():
            by_element[element_id].append(m)
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
        questions = list(result.scalars().all())

        # Dedup by normalized text before questions reach the memo. The convergence
        # loop re-runs question_gen each iteration, so ~92% of gap questions were
        # duplicates (BUG-14). Keep first occurrence, preserving order.
        deduped: list[FollowUpQuestion] = []
        seen: set[str] = set()
        for q in questions:
            norm = _normalize(q.question_text)
            if not norm or norm in seen:
                continue
            seen.add(norm)
            deduped.append(q)
        return deduped

    async def _load_authorities(self, intake_id: int) -> list[Authority]:
        result = await self._session.execute(
            select(Authority).where(Authority.intake_id == intake_id)
        )
        return list(result.scalars().all())

    async def _load_deadlines(self, run_id: int) -> list[DeadlineRef]:
        """Load Deadline rows for the run as DeadlineRefs, sorted by urgency."""
        result = await self._session.execute(
            select(Deadline).where(Deadline.run_id == run_id)
        )
        rows = result.scalars().all()
        refs = [
            DeadlineRef(
                event_text=d.event_text,
                event_type=d.event_type,
                trigger=d.trigger,
                trigger_date=d.trigger_date.isoformat() if d.trigger_date else None,
                computed_date=d.computed_date.isoformat() if d.computed_date else None,
                rule_id=d.rule_id,
                citation=d.citation,
                computed=d.computed,
                urgency=d.urgency,
                hedge=d.hedge,
                jurisdiction=d.jurisdiction,
            )
            for d in rows
        ]
        refs.sort(key=lambda r: _URGENCY_ORDER.get(r.urgency, 99))
        return refs

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
