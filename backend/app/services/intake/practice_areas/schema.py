"""Pydantic schema for practice-area configuration files."""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

# slug: lowercase letter first, then lowercase letters, digits, or underscores
# total length 2-41 (1 leading char + 1..40 trailing chars)
_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,40}$")


class PracticeArea(BaseModel):
    """A single practice-area configuration loaded from a YAML file.

    Attributes:
        id: Slug identifier (e.g. ``personal_injury``). Must match
            ``^[a-z][a-z0-9_]{1,40}$``.
        display_name: Human-readable label shown in selectors and headers.
        welcome_message_consumer: Opening message for self-represented users.
        welcome_message_professional: Opening message for legal professionals
            performing intake on behalf of a client.
        system_prompt: System prompt used to seed the LLM conversation when a
            session is bound to this practice area.
        key_topics: Ordered checklist of subjects the conversation should
            cover.
        disclaimer: Optional sensitive-practice disclaimer surfaced to the
            user before intake begins (used in plan 13-03 if set).
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    id: str = Field(..., description="Slug identifier; must match ^[a-z][a-z0-9_]{1,40}$")
    display_name: str = Field(..., min_length=1)
    welcome_message_consumer: str = Field(..., min_length=1)
    welcome_message_professional: str = Field(..., min_length=1)
    system_prompt: str = Field(..., min_length=1)
    key_topics: list[str] = Field(..., min_length=1)
    disclaimer: str | None = None

    @field_validator("id")
    @classmethod
    def _validate_id_slug(cls, v: str) -> str:
        if not _ID_PATTERN.match(v):
            raise ValueError(
                "id must be a slug matching ^[a-z][a-z0-9_]{1,40}$ "
                f"(got {v!r})"
            )
        return v

    @field_validator("key_topics")
    @classmethod
    def _validate_key_topics_nonempty(cls, v: list[str]) -> list[str]:
        cleaned: list[str] = []
        for i, topic in enumerate(v):
            if not isinstance(topic, str) or not topic.strip():
                raise ValueError(f"key_topics[{i}] must be a non-empty string")
            cleaned.append(topic)
        return cleaned
