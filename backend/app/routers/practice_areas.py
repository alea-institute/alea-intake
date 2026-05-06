"""Public read-only API for the practice-area registry.

The registry itself is loaded once at startup (see ``app.main.lifespan``) and
exposed on ``request.app.state.practice_areas``. This router surfaces a thin
JSON projection -- no authentication required, since practice areas are
public taxonomy used by the unauthenticated landing/intake UI to let the
visitor pick a starting point.

Frontend contract (locked for plan 13-03):

    GET /api/practice-areas
    -> {
         "practice_areas": [
           {"id": str, "display_name": str, "disclaimer": str | None},
           ...
         ]
       }

Sorted by ``display_name``.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.services.intake.practice_areas import PracticeAreaRegistry

router = APIRouter(prefix="/api/practice-areas", tags=["practice-areas"])


@router.get("")
async def list_practice_areas(request: Request) -> dict:
    """Return the public projection of the practice-area registry."""
    registry: PracticeAreaRegistry | None = getattr(
        request.app.state, "practice_areas", None
    )
    if registry is None:
        # Lifespan didn't run (e.g., narrow test apps). Treat as empty.
        return {"practice_areas": []}

    return {
        "practice_areas": [
            {
                "id": area.id,
                "display_name": area.display_name,
                "disclaimer": area.disclaimer,
            }
            for area in registry.list_all()
        ]
    }
