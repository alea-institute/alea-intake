"""LLM-guided conversation service for intake sessions.

Generates follow-up questions and welcome messages using the configured
LLM service. Falls back to static responses when LLM is unavailable.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

# System prompt for LLM-guided intake conversations
INTAKE_SYSTEM_PROMPT = (
    "You are a legal intake assistant helping to understand a person's legal situation. "
    "Ask clarifying follow-up questions about the person's legal situation, one topic at a "
    "time, using plain language that anyone can understand. Do not use legal jargon. "
    "Be empathetic and patient. Focus on gathering facts: who, what, when, where, "
    "and what happened. Do not provide legal advice."
)

# Welcome messages from UI-SPEC
_CONSUMER_WELCOME = (
    "Tell me about your legal situation in your own words. You can type, "
    "record your voice, or upload documents -- whatever is easiest for you."
)

_PROFESSIONAL_WELCOME = (
    "Enter the client's information. You can use the conversational interface "
    "or switch to structured form."
)


class ConversationService:
    """Generates LLM-guided conversational responses for intake sessions."""

    def __init__(self, llm_service: LLMService | None = None) -> None:
        self._llm = llm_service

    async def generate_response(
        self,
        messages: list[dict[str, str]],
        system_prompt: str | None = None,
    ) -> str:
        """Generate a conversational follow-up question via LLM.

        Falls back to a static follow-up when LLM is not configured or fails.

        Args:
            messages: Chat history as list of {role, content} dicts.
            system_prompt: Custom system prompt (defaults to INTAKE_SYSTEM_PROMPT).

        Returns:
            LLM-generated response text or a static fallback.
        """
        prompt = system_prompt or INTAKE_SYSTEM_PROMPT

        if self._llm is None:
            # No LLM configured -- return a sensible default follow-up
            return "Thank you for sharing that. Could you tell me more about when this happened and who was involved?"

        try:
            # Build prompt for alea-llm-client
            config = self._llm.get_client_config()
            # For now, return a default until full LLM integration in a later phase
            # The LLM call would be: client.generate(messages, system=prompt)
            return "Thank you for sharing that. Could you tell me more about when this happened and who was involved?"
        except Exception as e:
            logger.warning("LLM response generation failed: %s", e)
            return "Thank you for sharing that. Could you tell me more about when this happened and who was involved?"

    async def generate_welcome_message(
        self,
        session_mode: str,
        is_professional: bool = False,
    ) -> str:
        """Return the appropriate welcome message for the session type.

        Args:
            session_mode: The intake session mode (e.g., "multi_session").
            is_professional: True if this is a professional-facing session.

        Returns:
            Welcome message string.
        """
        if is_professional:
            return _PROFESSIONAL_WELCOME
        return _CONSUMER_WELCOME
