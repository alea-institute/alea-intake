"""Deterministic grounding guard for LLM-generated claim-rationale prose (BUG-28).

Fabrication is the worst failure class in this product. A rationale that asserts
corroborating *evidence the record does not contain* — e.g. "the doctor's
documentation of asthma" when the client only *reports* asthma and explicitly
lacks a doctor's note — can mislead a lawyer or client into believing a case is
stronger than it is. This is a RUB-04 GATE failure (Damien, 2026-07-10, strict).

This guard runs AFTER the issue-spot / explore LLM returns and BEFORE the
rationale is persisted. It is a deterministic backstop (the LLM prompt is the
primary defense): it scans generated prose for *evidence-existence assertions*
— clauses that claim documentation / records / testimony exist — and, when the
fact record contains no supporting token for that evidence class, rewrites the
clause to a hedged, client-reported form.

It NEVER adds facts. It only *weakens* over-strong claims: prefer duller,
provably-grounded prose. When the record DOES contain the evidence token (e.g.
a fact actually mentions a doctor's diagnosis), the assertion is left intact so
genuinely-documented matters are not needlessly hedged.

The rule table is intentionally small and extensible: each rule pairs a prose
pattern that asserts evidence with the fact-record tokens that would justify it.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class _HedgeRule:
    """One evidence-assertion pattern and the fact tokens that would support it.

    ``pattern`` matches an over-strong evidentiary clause; ``replacement`` is the
    hedged form (may use ``\\1`` backrefs to preserve the underlying subject).
    The rule fires only when NONE of ``support_tokens`` appears in the fact
    record — i.e. the asserted evidence is nowhere in the intake.
    """

    pattern: re.Pattern[str]
    replacement: str
    support_tokens: tuple[str, ...]


# Tokens whose presence anywhere in the fact record means a medical-evidence
# assertion is at least plausibly grounded, so we leave it alone.
_MEDICAL_TOKENS: tuple[str, ...] = (
    "doctor",
    "physician",
    "diagnos",  # diagnosis / diagnosed
    "prescription",
    "prescribed",
    "hospital",
    "clinic",
    "medical record",
    "medical documentation",
    "pediatrician",
)

# Tokens for police / official-report assertions.
_POLICE_TOKENS: tuple[str, ...] = (
    "police report",
    "police",
    "officer",
    "incident report",
    "911",
    "citation",
)


_HEDGE_RULES: tuple[_HedgeRule, ...] = (
    # "the doctor's documentation/notes/records/report/findings of X" -> "the reported X"
    _HedgeRule(
        pattern=re.compile(
            r"\bthe\s+doctor'?s?\s+"
            r"(?:documentation|notes?|records?|report|reports|findings?|diagnosis)\s+of\s+",
            re.IGNORECASE,
        ),
        replacement="the reported ",
        support_tokens=_MEDICAL_TOKENS,
    ),
    # "the doctor has noted/documented/confirmed/... that X" -> "the client reports that X"
    _HedgeRule(
        pattern=re.compile(
            r"\bthe\s+doctor\s+has\s+"
            r"(?:noted|documented|confirmed|found|reported|stated|diagnosed|indicated)\s+that\s+",
            re.IGNORECASE,
        ),
        replacement="the client reports that ",
        support_tokens=_MEDICAL_TOKENS,
    ),
    # "as documented/noted/confirmed by (the/a) doctor" -> "as reported by the client"
    _HedgeRule(
        pattern=re.compile(
            r"\b(?:as\s+)?(?:documented|noted|confirmed|diagnosed)\s+by\s+"
            r"(?:the\s+|a\s+)?doctor\b",
            re.IGNORECASE,
        ),
        replacement="as reported by the client",
        support_tokens=_MEDICAL_TOKENS,
    ),
    # "medical records/documentation show/confirm/indicate that X" -> "the client reports that X"
    _HedgeRule(
        pattern=re.compile(
            r"\bmedical\s+(?:records?|documentation)\s+"
            r"(?:show|shows|confirm|confirms|indicate|indicates|establish|establishes)\s+"
            r"(?:that\s+)?",
            re.IGNORECASE,
        ),
        replacement="the client reports that ",
        support_tokens=_MEDICAL_TOKENS,
    ),
    # "the police report confirms/shows/documents/states (that) X" -> "the client reports (that) X"
    _HedgeRule(
        pattern=re.compile(
            r"\bthe\s+police\s+report\s+"
            r"(?:confirms?|shows?|documents?|states?|establishes?)\s+"
            r"(?:that\s+)?",
            re.IGNORECASE,
        ),
        replacement="the client reports that ",
        support_tokens=_POLICE_TOKENS,
    ),
)


def _fact_corpus(fact_texts: Iterable[str]) -> str:
    """Lowercased concatenation of the fact record for token support checks."""
    return " ".join(t for t in fact_texts if t).lower()


def ground_rationale(
    rationale: str | None,
    fact_texts: Iterable[str],
) -> tuple[str, list[str]]:
    """Hedge unsupported evidence-existence assertions in a claim rationale.

    Args:
        rationale: The LLM-generated rationale prose (may be None/empty).
        fact_texts: Assertion texts from the fact record. If a rule's evidence
            token appears here, that rule is skipped (the assertion is plausibly
            grounded and left intact).

    Returns:
        ``(hedged_rationale, interventions)`` where ``interventions`` is a list
        of human-readable notes describing each hedge applied (for logging).
        ``hedged_rationale`` equals the input when nothing fired.
    """
    if not rationale or not rationale.strip():
        return rationale or "", []

    corpus = _fact_corpus(fact_texts)
    text = rationale
    interventions: list[str] = []

    for rule in _HEDGE_RULES:
        if any(tok in corpus for tok in rule.support_tokens):
            # The asserted evidence class is present somewhere in the record;
            # do not hedge a possibly-grounded assertion.
            continue
        new_text, n = rule.pattern.subn(rule.replacement, text)
        if n:
            interventions.append(
                f"hedged {n} unsupported evidence assertion(s) "
                f"matching /{rule.pattern.pattern[:48]}.../"
            )
            text = new_text

    return text, interventions
