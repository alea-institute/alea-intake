"""Tests for ConversationService LLM wiring (BUG-2).

Verifies that generate_response() delegates to the configured LLM service's
acomplete() and returns its text, and that it falls back to a canned string
when no LLM is configured or the LLM raises.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from app.services.intake.conversation import ConversationService

_FALLBACK = (
    "Thank you for sharing that. Could you tell me more about when this "
    "happened and who was involved?"
)


async def test_generate_response_returns_llm_text():
    """generate_response returns the LLM's text when a service is present."""
    mock_llm = MagicMock()
    mock_llm.acomplete = AsyncMock(return_value="What date did you receive the notice?")

    svc = ConversationService(llm_service=mock_llm)
    result = await svc.generate_response(
        [{"role": "user", "content": "I got a notice from my landlord."}]
    )

    assert result == "What date did you receive the notice?"
    mock_llm.acomplete.assert_awaited_once()


async def test_generate_response_falls_back_when_llm_raises():
    """generate_response returns the canned fallback when acomplete raises."""
    mock_llm = MagicMock()
    mock_llm.acomplete = AsyncMock(side_effect=RuntimeError("provider down"))

    svc = ConversationService()
    svc._llm = mock_llm  # inject a failing LLM directly

    result = await svc.generate_response(
        [{"role": "user", "content": "Something happened."}]
    )

    assert result == _FALLBACK


async def test_generate_response_falls_back_when_no_llm():
    """generate_response returns the canned fallback when no LLM is configured."""
    svc = ConversationService()  # _llm is None
    assert svc._llm is None

    result = await svc.generate_response(
        [{"role": "user", "content": "Something happened."}]
    )

    assert result == _FALLBACK


async def test_generate_response_empty_llm_reply_uses_fallback():
    """An empty LLM reply falls back to the canned string."""
    mock_llm = MagicMock()
    mock_llm.acomplete = AsyncMock(return_value="")

    svc = ConversationService(llm_service=mock_llm)
    result = await svc.generate_response(
        [{"role": "user", "content": "Hello."}]
    )

    assert result == _FALLBACK
