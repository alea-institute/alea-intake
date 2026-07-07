"""FOLIO singleton loader with thread-safe hot-swap.

Provides a process-wide FOLIO instance that can be safely replaced
when an OWL update is detected, without interrupting in-flight analyses.
"""

from __future__ import annotations

import logging
import threading

from folio import FOLIO

from app.config import get_settings

logger = logging.getLogger(__name__)

# Module-level singleton with thread-safe locking
_folio_instance: FOLIO | None = None
_folio_lock = threading.Lock()


def get_folio(branch: str | None = None) -> FOLIO:
    """Return the shared FOLIO singleton, creating it on first call.

    Uses double-checked locking for thread safety. The FOLIO constructor
    is synchronous and does XML parsing, so this should be called via
    run_in_executor from async contexts.

    Args:
        branch: GitHub branch to use. Defaults to settings.folio_owl_branch.
    """
    global _folio_instance

    # Fast path: already initialized
    if _folio_instance is not None:
        return _folio_instance

    # Slow path: initialize under lock
    with _folio_lock:
        if _folio_instance is not None:
            return _folio_instance

        if branch is None:
            settings = get_settings()
            branch = settings.folio_owl_branch

        logger.info("Loading FOLIO ontology (branch=%s)...", branch)
        _folio_instance = FOLIO(github_repo_branch=branch)
        logger.info(
            "FOLIO ontology loaded: %d classes, %d object properties",
            len(_folio_instance.classes),
            len(_folio_instance.object_properties),
        )
        return _folio_instance


def reload_folio(new_instance: FOLIO) -> None:
    """Thread-safe replacement of the FOLIO singleton.

    Called by OWLUpdateManager after downloading a new OWL version and
    waiting for active analyses to complete.
    """
    global _folio_instance
    with _folio_lock:
        _folio_instance = new_instance
    logger.info("FOLIO singleton replaced with new instance")


def reset_folio() -> None:
    """Reset the FOLIO singleton to None (for testing)."""
    global _folio_instance
    with _folio_lock:
        _folio_instance = None


def get_owl_class(folio: FOLIO, iri: str):
    """Look up an OWLClass by IRI against the REAL folio-python contract.

    folio-python's ``FOLIO.classes`` is a ``List[OWLClass]`` — NOT a dict —
    so ``folio.classes.get(iri)`` / ``iri in folio.classes`` are always wrong
    against the real library (BUG-10). The supported API is ``iri in folio``
    and ``folio[iri]``. Test doubles that expose a dict ``classes`` are
    handled by the fallback.

    Returns the OWLClass or None.
    """
    try:
        if iri in folio:
            return folio[iri]
        # Real FOLIO, unknown IRI.
        if isinstance(getattr(folio, "classes", None), list):
            return None
    except TypeError:
        pass
    classes = getattr(folio, "classes", None)
    if hasattr(classes, "get"):
        return classes.get(iri)
    return None
