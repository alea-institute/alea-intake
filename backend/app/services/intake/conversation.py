"""LLM-guided conversation service for intake sessions.

Generates follow-up questions and welcome messages using the configured
LLM service. Falls back to static responses when LLM is unavailable.

When a session is bound to a practice area (see
:mod:`app.services.intake.practice_areas`), the service swaps in the
practice's ``system_prompt`` and ``welcome_message_*`` strings. With no
practice area bound, the generic ``INTAKE_SYSTEM_PROMPT`` and the static
consumer/professional welcome strings remain in effect.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.services.intake.practice_areas import PracticeAreaRegistry

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

    def __init__(
        self,
        llm_service: LLMService | None = None,
        practice_areas: PracticeAreaRegistry | None = None,
    ) -> None:
        self._llm = llm_service
        self._practice_areas = practice_areas

    def _resolve_system_prompt(
        self,
        practice_area_id: str | None,
        explicit_system_prompt: str | None,
    ) -> str:
        """Pick the system prompt: explicit > practice-bound > generic."""
        if explicit_system_prompt is not None:
            return explicit_system_prompt
        if practice_area_id and self._practice_areas is not None:
            area = self._practice_areas.get(practice_area_id)
            if area is not None:
                return area.system_prompt
        return INTAKE_SYSTEM_PROMPT

    async def generate_response(
        self,
        messages: list[dict[str, str]],
        system_prompt: str | None = None,
        practice_area_id: str | None = None,
    ) -> str:
        """Generate a conversational follow-up question via LLM.

        Falls back to a static follow-up when LLM is not configured or fails.

        Args:
            messages: Chat history as list of {role, content} dicts.
            system_prompt: Custom system prompt. If provided, takes precedence
                over any practice-area binding.
            practice_area_id: Optional id used to look up a practice-bound
                ``system_prompt`` from the registry. Falls back to
                ``INTAKE_SYSTEM_PROMPT`` if not found or if no registry was
                supplied.

        Returns:
            LLM-generated response text or a static fallback.
        """
        prompt = self._resolve_system_prompt(practice_area_id, system_prompt)

        fallback = (
            "Thank you for sharing that. Could you tell me more about when this "
            "happened and who was involved?"
        )
        if self._llm is None:
            # No LLM configured -- return a sensible default follow-up
            return fallback

        try:
            reply = await self._llm.acomplete(messages, system_prompt=prompt)
            return reply or fallback
        except Exception as e:
            logger.warning("LLM response generation failed: %s", e)
            return fallback

    async def generate_welcome_message(
        self,
        session_mode: str,
        is_professional: bool = False,
        practice_area_id: str | None = None,
    ) -> str:
        """Return the appropriate welcome message for the session type.

        Args:
            session_mode: The intake session mode (e.g., "multi_session").
            is_professional: True if this is a professional-facing session.
            practice_area_id: Optional practice-area id; when set and the
                registry knows it, the practice's
                ``welcome_message_consumer`` / ``welcome_message_professional``
                is returned. Falls back to the generic strings otherwise.

        Returns:
            Welcome message string.
        """
        if practice_area_id and self._practice_areas is not None:
            area = self._practice_areas.get(practice_area_id)
            if area is not None:
                return (
                    area.welcome_message_professional
                    if is_professional
                    else area.welcome_message_consumer
                )

        if is_professional:
            return _PROFESSIONAL_WELCOME
        return _CONSUMER_WELCOME
