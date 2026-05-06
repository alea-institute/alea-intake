"""In-memory registry of loaded practice-area configurations."""

from __future__ import annotations

from app.services.intake.practice_areas.schema import PracticeArea


class PracticeAreaRegistry:
    """Wraps a ``dict[str, PracticeArea]`` keyed by ``PracticeArea.id``.

    The registry is built once at startup by :func:`load_practice_areas` and
    then read-only for the rest of the process lifetime. ``register`` exists
    primarily for the loader and tests.
    """

    def __init__(self) -> None:
        self._areas: dict[str, PracticeArea] = {}

    def register(self, area: PracticeArea) -> None:
        """Add a practice area to the registry.

        Raises:
            ValueError: If an area with the same ``id`` is already registered.
        """
        if area.id in self._areas:
            raise ValueError(
                f"Practice area with id={area.id!r} is already registered"
            )
        self._areas[area.id] = area

    def get(self, id: str) -> PracticeArea | None:
        """Return the practice area with the given id, or ``None``."""
        return self._areas.get(id)

    def list_all(self) -> list[PracticeArea]:
        """Return all registered practice areas, sorted by ``display_name``."""
        return sorted(self._areas.values(), key=lambda a: a.display_name)

    def __len__(self) -> int:
        return len(self._areas)

    def __contains__(self, id: object) -> bool:
        return isinstance(id, str) and id in self._areas
