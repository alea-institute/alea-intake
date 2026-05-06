"""Practice-area configuration package.

Provides typed practice-area configs loaded from YAML at startup. Each practice
area carries its own welcome messages, system prompt, and key-topic checklist
so the intake conversation can adapt to a specific area of law.
"""

from app.services.intake.practice_areas.loader import (
    PracticeAreaConfigError,
    load_practice_areas,
)
from app.services.intake.practice_areas.registry import PracticeAreaRegistry
from app.services.intake.practice_areas.schema import PracticeArea

__all__ = [
    "PracticeArea",
    "PracticeAreaRegistry",
    "PracticeAreaConfigError",
    "load_practice_areas",
]
