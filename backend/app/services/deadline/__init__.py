"""Deadline / SOL detection engine (v1 "detect + hedge").

Probabilistic detect (LLM event extraction) -> deterministic compute (cited rule
table + stdlib date math) -> deterministic surface (memo section + action items).

A computed date is ALWAYS presented as an estimate to verify; where no verified
rule applies the event is surfaced "detected + hedged only" (computed=False).
"""

from app.services.deadline.engine import GENERIC_HEDGE, compute_deadlines
from app.services.deadline.schemas import ComputedDeadline, DeadlineEvent

__all__ = [
    "ComputedDeadline",
    "DeadlineEvent",
    "GENERIC_HEDGE",
    "compute_deadlines",
]
