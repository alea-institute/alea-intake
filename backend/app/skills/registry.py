"""Skills registry for bundled and community-contributed skills.

Loads skill Markdown files from the bundled directory and supports
runtime registration of org-private skills. Each skill is a Markdown
file with YAML frontmatter containing metadata (name, description, type, author).
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# Path to bundled skills directory
_BUNDLED_DIR = Path(__file__).parent / "bundled"


@dataclass
class Skill:
    """A skill definition loaded from Markdown with YAML frontmatter.

    Attributes:
        name: Human-readable skill name.
        description: Short description of the skill.
        skill_type: Category -- screening, intake_template, or workflow.
        content: Full Markdown content (body after frontmatter).
        bundled: Whether this skill ships with ALEA (vs. org-private or community).
        author: Optional author name or organization.
    """

    name: str
    description: str
    skill_type: str
    content: str
    bundled: bool = True
    author: str | None = None


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Parse YAML frontmatter from Markdown text.

    Expects frontmatter delimited by --- on its own line.

    Returns:
        Tuple of (frontmatter dict, body text).
    """
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", text, re.DOTALL)
    if not match:
        return {}, text
    try:
        meta = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        meta = {}
    return meta, match.group(2)


class SkillsRegistry:
    """Registry for bundled and org-private skills.

    Usage:
        registry = SkillsRegistry()
        registry.load_bundled()
        skills = registry.list_skills(skill_type="screening")
        skill = registry.get_skill("DV Screening Protocol")
    """

    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}

    def load_bundled(self) -> None:
        """Scan the bundled skills directory and load all .md files.

        Each file must have YAML frontmatter with name, description, and type.
        """
        if not _BUNDLED_DIR.is_dir():
            logger.warning("Bundled skills directory not found: %s", _BUNDLED_DIR)
            return

        for md_file in sorted(_BUNDLED_DIR.glob("*.md")):
            try:
                text = md_file.read_text(encoding="utf-8")
                meta, body = _parse_frontmatter(text)

                name = meta.get("name", md_file.stem)
                description = meta.get("description", "")
                skill_type = meta.get("type", "unknown")
                author = meta.get("author")

                skill = Skill(
                    name=name,
                    description=description,
                    skill_type=skill_type,
                    content=body.strip(),
                    bundled=True,
                    author=author,
                )
                self._skills[name] = skill
                logger.debug("Loaded bundled skill: %s (%s)", name, skill_type)
            except Exception:
                logger.error(
                    "Failed to load bundled skill: %s", md_file, exc_info=True
                )

        logger.info("Loaded %d bundled skills", len(self._skills))

    def list_skills(self, skill_type: str | None = None) -> list[Skill]:
        """Return all registered skills, optionally filtered by type.

        Args:
            skill_type: Filter by skill type (screening, intake_template, workflow).

        Returns:
            List of Skill objects.
        """
        skills = list(self._skills.values())
        if skill_type:
            skills = [s for s in skills if s.skill_type == skill_type]
        return skills

    def get_skill(self, name: str) -> Skill | None:
        """Return a specific skill by name, or None if not found."""
        return self._skills.get(name)

    def register_skill(self, skill: Skill) -> None:
        """Register an org-private or community skill at runtime.

        Args:
            skill: Skill object to register.
        """
        self._skills[skill.name] = skill
        logger.info("Registered skill: %s (bundled=%s)", skill.name, skill.bundled)
