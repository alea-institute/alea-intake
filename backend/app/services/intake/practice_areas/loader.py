"""YAML loader for practice-area configurations.

Globs ``*.yaml`` files in a directory, validates each against
:class:`PracticeArea`, and registers them in a fresh
:class:`PracticeAreaRegistry`. Fails fast on any error -- a bad config at
startup should crash the app rather than silently degrade.
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml
from pydantic import ValidationError

from app.services.intake.practice_areas.registry import PracticeAreaRegistry
from app.services.intake.practice_areas.schema import PracticeArea

logger = logging.getLogger(__name__)


class PracticeAreaConfigError(Exception):
    """Raised when a practice-area config file cannot be loaded or validated."""


def load_practice_areas(directory: Path) -> PracticeAreaRegistry:
    """Load all ``*.yaml`` practice-area configs from ``directory``.

    Args:
        directory: Directory to scan. May be empty (returns empty registry).
            A non-existent directory is also treated as empty (with a warning
            log) so dev environments without configs don't crash.

    Returns:
        A populated :class:`PracticeAreaRegistry`.

    Raises:
        PracticeAreaConfigError: If any file fails to parse, fails schema
            validation, or if two files declare the same ``id``. The error
            message includes the offending file path(s).
    """
    registry = PracticeAreaRegistry()

    if not directory.exists():
        logger.warning(
            "Practice-area config directory does not exist: %s", directory
        )
        return registry

    if not directory.is_dir():
        raise PracticeAreaConfigError(
            f"Practice-area config path is not a directory: {directory}"
        )

    # Track which file declared which id so duplicate errors can name both.
    id_to_path: dict[str, Path] = {}

    for path in sorted(directory.glob("*.yaml")):
        try:
            raw_text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise PracticeAreaConfigError(
                f"Failed to read practice-area config {path}: {exc}"
            ) from exc

        try:
            data = yaml.safe_load(raw_text)
        except yaml.YAMLError as exc:
            raise PracticeAreaConfigError(
                f"Invalid YAML in practice-area config {path}: {exc}"
            ) from exc

        if data is None:
            raise PracticeAreaConfigError(
                f"Practice-area config {path} is empty"
            )
        if not isinstance(data, dict):
            raise PracticeAreaConfigError(
                f"Practice-area config {path} must be a YAML mapping at the "
                f"top level (got {type(data).__name__})"
            )

        try:
            area = PracticeArea.model_validate(data)
        except ValidationError as exc:
            raise PracticeAreaConfigError(
                f"Practice-area config {path} failed validation:\n{exc}"
            ) from exc

        if area.id in id_to_path:
            other = id_to_path[area.id]
            raise PracticeAreaConfigError(
                f"Duplicate practice-area id={area.id!r} declared in both "
                f"{other} and {path}"
            )

        registry.register(area)
        id_to_path[area.id] = path

    return registry
