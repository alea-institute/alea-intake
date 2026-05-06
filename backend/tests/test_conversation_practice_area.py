"""Tests for ConversationService practice-area awareness (plan 13-02).

Covers:
  - ``generate_response`` resolves the system prompt from a registered
    practice area when ``practice_area_id`` is supplied.
  - ``generate_response`` falls back to ``INTAKE_SYSTEM_PROMPT`` when
    ``practice_area_id`` is None or unknown.
  - ``generate_welcome_message`` returns the practice's
    ``welcome_message_consumer`` / ``welcome_message_professional`` when
    bound, and the generic strings otherwise (regression guard).
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.services.intake.conversation import (
    ConversationService,
    INTAKE_SYSTEM_PROMPT,
)
from app.services.intake.practice_areas import (
    PracticeArea,
    PracticeAreaRegistry,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_pi() -> PracticeArea:
    return PracticeArea(
        id="personal_injury",
        display_name="Personal Injury",
        welcome_message_consumer="PI consumer welcome.",
        welcome_message_professional="PI professional welcome.",
        system_prompt="You are a PI specialist intake assistant.",
        key_topics=["Incident facts", "Injuries", "Treatment"],
        disclaimer=None,
    )


def _make_registry() -> PracticeAreaRegistry:
    reg = PracticeAreaRegistry()
    reg.register(_make_pi())
    return reg


# ---------------------------------------------------------------------------
# generate_response
# ---------------------------------------------------------------------------


class TestGenerateResponseSystemPromptResolution:
    @pytest.mark.asyncio
    async def test_uses_practice_area_system_prompt_when_bound(self):
        """When practice_area_id matches a registered area, that prompt is used."""
        reg = _make_registry()
        svc = ConversationService(llm_service=None, practice_areas=reg)

        # We can directly test the resolver since the LLM stub returns a
        # static string; the resolver is the single source of truth for the
        # prompt that *would* be sent to the LLM.
        resolved = svc._resolve_system_prompt(
            practice_area_id="personal_injury",
            explicit_system_prompt=None,
        )
        assert resolved == "You are a PI specialist intake assistant."
        assert resolved != INTAKE_SYSTEM_PROMPT

        # And generate_response runs successfully end-to-end with that id.
        result = await svc.generate_response(
            messages=[{"role": "user", "content": "I was rear-ended"}],
            practice_area_id="personal_injury",
        )
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_falls_back_to_generic_prompt_when_id_is_none(self):
        """No practice_area_id => INTAKE_SYSTEM_PROMPT."""
        reg = _make_registry()
        svc = ConversationService(llm_service=None, practice_areas=reg)

        resolved = svc._resolve_system_prompt(
            practice_area_id=None, explicit_system_prompt=None
        )
        assert resolved == INTAKE_SYSTEM_PROMPT

        # End-to-end regression guard
        result = await svc.generate_response(
            messages=[{"role": "user", "content": "Hello"}],
        )
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_falls_back_to_generic_prompt_when_id_unknown(self):
        """Unknown practice_area_id => INTAKE_SYSTEM_PROMPT (graceful)."""
        reg = _make_registry()
        svc = ConversationService(llm_service=None, practice_areas=reg)

        resolved = svc._resolve_system_prompt(
            practice_area_id="nonexistent_practice",
            explicit_system_prompt=None,
        )
        assert resolved == INTAKE_SYSTEM_PROMPT

    @pytest.mark.asyncio
    async def test_falls_back_when_no_registry_provided(self):
        """No registry => INTAKE_SYSTEM_PROMPT regardless of id."""
        svc = ConversationService(llm_service=None, practice_areas=None)
        resolved = svc._resolve_system_prompt(
            practice_area_id="personal_injury",
            explicit_system_prompt=None,
        )
        assert resolved == INTAKE_SYSTEM_PROMPT

    @pytest.mark.asyncio
    async def test_explicit_system_prompt_wins_over_practice_area(self):
        """Explicit system_prompt overrides any practice-area binding."""
        reg = _make_registry()
        svc = ConversationService(llm_service=None, practice_areas=reg)
        resolved = svc._resolve_system_prompt(
            practice_area_id="personal_injury",
            explicit_system_prompt="custom override prompt",
        )
        assert resolved == "custom override prompt"


# ---------------------------------------------------------------------------
# generate_welcome_message
# ---------------------------------------------------------------------------


class TestGenerateWelcomeMessagePracticeArea:
    @pytest.mark.asyncio
    async def test_consumer_welcome_for_bound_practice(self):
        reg = _make_registry()
        svc = ConversationService(llm_service=None, practice_areas=reg)
        msg = await svc.generate_welcome_message(
            session_mode="multi_session",
            is_professional=False,
            practice_area_id="personal_injury",
        )
        assert msg == "PI consumer welcome."

    @pytest.mark.asyncio
    async def test_professional_welcome_for_bound_practice(self):
        reg = _make_registry()
        svc = ConversationService(llm_service=None, practice_areas=reg)
        msg = await svc.generate_welcome_message(
            session_mode="multi_session",
            is_professional=True,
            practice_area_id="personal_injury",
        )
        assert msg == "PI professional welcome."

    @pytest.mark.asyncio
    async def test_consumer_welcome_falls_back_when_no_practice(self):
        """Regression guard: original consumer welcome string returned."""
        reg = _make_registry()
        svc = ConversationService(llm_service=None, practice_areas=reg)
        msg = await svc.generate_welcome_message(
            session_mode="multi_session", is_professional=False
        )
        assert "your own words" in msg.lower()

    @pytest.mark.asyncio
    async def test_professional_welcome_falls_back_when_no_practice(self):
        """Regression guard: original professional welcome string returned."""
        reg = _make_registry()
        svc = ConversationService(llm_service=None, practice_areas=reg)
        msg = await svc.generate_welcome_message(
            session_mode="multi_session", is_professional=True
        )
        # The original professional welcome talks about the client's information
        assert "client" in msg.lower() or "information" in msg.lower()

    @pytest.mark.asyncio
    async def test_unknown_practice_id_falls_back_gracefully(self):
        reg = _make_registry()
        svc = ConversationService(llm_service=None, practice_areas=reg)
        msg = await svc.generate_welcome_message(
            session_mode="multi_session",
            is_professional=False,
            practice_area_id="not_registered",
        )
        # Falls back to the generic consumer welcome
        assert "your own words" in msg.lower()

    @pytest.mark.asyncio
    async def test_no_registry_falls_back(self):
        svc = ConversationService(llm_service=AsyncMock(), practice_areas=None)
        msg = await svc.generate_welcome_message(
            session_mode="multi_session",
            is_professional=False,
            practice_area_id="personal_injury",
        )
        assert "your own words" in msg.lower()
