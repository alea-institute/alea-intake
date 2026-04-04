"""Conversation service for LLM-guided intake questioning.

Wraps the LLM service to generate contextual follow-up questions
based on the consumer's intake messages.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.llm_service import LLMService

INTAKE_SYSTEM_PROMPT = (
    "You are a legal intake assistant. Your role is to help consumers describe "
    "their legal situation by asking clarifying follow-up questions. Ask one topic "
    "at a time, using plain language. Do not provide legal advice. Focus on "
    "understanding the facts, timeline, parties involved, and desired outcome."
)


class ConversationService:
    """Service for generating LLM-powered intake conversation responses."""

    def __init__(self, llm_service: LLMService) -> None:
        self.llm_service = llm_service

    async def generate_response(
        self,
        messages: list[dict],
        system_prompt: str | None = None,
    ) -> str:
        """Generate a conversational follow-up response.

        Args:
            messages: List of message dicts with role/content keys.
            system_prompt: Optional override for the system prompt.

        Returns:
            Generated response text.
        """
        prompt = system_prompt or INTAKE_SYSTEM_PROMPT
        # In production, this calls the LLM service
        # For now, return a default follow-up question
        return "Thank you for sharing that. Could you tell me more about when this happened and who was involved?"

    async def generate_welcome_message(
        self,
        session_mode: str = "multi_session",
        is_professional: bool = False,
    ) -> str:
        """Generate the appropriate welcome message.

        Args:
            session_mode: The session mode (multi_session, single_session).
            is_professional: Whether the user is a professional.

        Returns:
            Welcome message text.
        """
        if is_professional:
            return (
                "Professional intake mode. Enter case notes, upload documents, "
                "or start a consumer interview."
            )
        return (
            "Tell me about your legal situation in your own words. "
            "You can type, record your voice, or upload documents -- "
            "whatever is easiest for you."
        )
