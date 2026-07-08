"""Fast trigger matching engine for per-message safety screening.

Pre-compiles regex patterns and builds keyword sets at initialization for
<50ms matching against consumer message content. Used by the screening
middleware on every consumer message.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class TriggeredProtocol:
    """Result of a trigger match -- identifies which protocol was triggered and why."""

    protocol_id: int
    protocol_name: str
    severity_tier: str
    version_id: int
    trigger_type: str  # "keyword", "regex", or "folio_concept"
    matched_terms: list[str] = field(default_factory=list)


class TriggerMatcher:
    """Pre-compiled trigger matching engine for fast per-message screening.

    Initialization:
        Pre-compiles all regex patterns and builds lowercased keyword sets
        from each active protocol version's trigger_conditions_json.

    Matching (match_fast):
        1. Lowercase content once
        2. For each active protocol:
           a. Check keyword sets via substring matching in content words
           b. Check compiled regex patterns against content
           c. Check FOLIO concept IRIs (simple set membership -- actual matching deferred)
        3. Return list of TriggeredProtocol results

    Performance target: <50ms for 16 protocols against typical message length.
    """

    def __init__(self, protocols: list[tuple]) -> None:
        """Initialize with list of (OrgProtocolActivation, ProtocolVersion) tuples.

        Pre-compiles regex patterns and normalizes keyword sets for fast matching.
        """
        self._protocols: list[dict] = []
        self._compiled_patterns: dict[int, list[re.Pattern]] = {}

        for activation, version in protocols:
            trigger_cond = version.trigger_conditions_json or {}
            keywords_raw = trigger_cond.get("keywords", [])
            regex_patterns_raw = trigger_cond.get("regex_patterns", [])
            folio_iris = set(trigger_cond.get("folio_concept_iris", []))

            # Pre-compile regex patterns
            compiled = []
            for pattern_str in regex_patterns_raw:
                try:
                    compiled.append(re.compile(pattern_str, re.IGNORECASE))
                except re.error:
                    pass  # Skip invalid patterns

            # Build keyword matchers with WORD-BOUNDARY semantics (BUG-20).
            # Plain substring matching made short keywords catastrophic: the
            # immigration protocol's "ice" fired on "pol-ICE", "off-ICE",
            # "just-ICE", "not-ICE", "serv-ICE" — so a family-custody summons
            # (full of "Sheriff's Office" / "Justice Center" / "notice of
            # service") spuriously surfaced immigration resources in a DV memo.
            # We now require each keyword phrase to match on non-word boundaries
            # so "ice" only fires on the standalone word "ice", never inside
            # another word. Multi-word phrases ("domestic violence") are
            # unaffected. Keep keywords_lower for matched-term reporting.
            keywords_lower = [kw.lower() for kw in keywords_raw]
            keyword_patterns: list[tuple[str, re.Pattern]] = []
            for kw in keywords_lower:
                if not kw:
                    continue
                keyword_patterns.append(
                    (kw, re.compile(r"(?<!\w)" + re.escape(kw) + r"(?!\w)", re.IGNORECASE))
                )

            protocol_id = activation.protocol_id
            self._compiled_patterns[protocol_id] = compiled

            self._protocols.append({
                "protocol_id": protocol_id,
                "protocol_name": getattr(version, "_protocol_name", f"Protocol {protocol_id}"),
                "severity_tier": getattr(version, "_severity_tier", "advisory"),
                "version_id": version.id,
                "keywords_lower": keywords_lower,
                "keyword_patterns": keyword_patterns,
                "compiled_patterns": compiled,
                "folio_iris": folio_iris,
            })

    def match_fast(self, content: str) -> list[TriggeredProtocol]:
        """Match content against all active protocol triggers.

        Returns list of TriggeredProtocol for each protocol whose triggers fired.
        Designed for <50ms execution against 16 protocols.
        """
        content_lower = content.lower()
        results: list[TriggeredProtocol] = []

        for proto in self._protocols:
            matched_terms: list[str] = []
            trigger_type: str | None = None

            # 1. Keyword matching -- word-boundary match so short tokens ("ice",
            #    "dv") never fire inside larger words ("police", "advocate").
            for kw, pattern in proto["keyword_patterns"]:
                if pattern.search(content_lower):
                    matched_terms.append(kw)
                    trigger_type = "keyword"

            # 2. Regex matching -- check compiled patterns
            if not trigger_type:
                for pattern in proto["compiled_patterns"]:
                    match = pattern.search(content_lower)
                    if match:
                        matched_terms.append(match.group())
                        trigger_type = "regex"
                        break  # One regex match is sufficient

            # 3. FOLIO concept IRI matching (simple set membership)
            # Actual FOLIO concept matching is deferred to deep scan
            # This only checks if IRIs are explicitly mentioned in content
            if not trigger_type and proto["folio_iris"]:
                for iri in proto["folio_iris"]:
                    if iri in content:
                        matched_terms.append(iri)
                        trigger_type = "folio_concept"
                        break

            if trigger_type:
                results.append(TriggeredProtocol(
                    protocol_id=proto["protocol_id"],
                    protocol_name=proto["protocol_name"],
                    severity_tier=proto["severity_tier"],
                    version_id=proto["version_id"],
                    trigger_type=trigger_type,
                    matched_terms=matched_terms,
                ))

        return results
