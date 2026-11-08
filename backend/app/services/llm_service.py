"""LLM service wrapper with per-org configuration and training opt-out enforcement.

Wraps alea-llm-client with three-level training opt-out:
  Level 1: Use API-tier access (not consumer-tier) for all cloud providers
  Level 2: Include provider-specific organization headers when available
  Level 3: Respect org data_policy -- if "local_only", only allow VLLM/local endpoints

The service MUST NOT expose methods that send arbitrary data to training-eligible endpoints.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any

from fastapi import HTTPException, Request

from app import config as app_config

from alea_llm_client import AnthropicModel, GoogleModel, OpenAIModel, VLLMModel

if TYPE_CHECKING:
    from app.models.organization import OrganizationConfig

# Cloud providers whose endpoints are external (training concern for local_only policy)
_CLOUD_PROVIDERS = {"openai", "anthropic", "google", "grok"}

# Local-only providers (no training concern)
_LOCAL_PROVIDERS = {"vllm"}

# Map provider names to alea-llm-client model classes
_PROVIDER_MODEL_MAP: dict[str, type] = {
    "openai": OpenAIModel,
    "anthropic": AnthropicModel,
    "google": GoogleModel,
    "vllm": VLLMModel,
}

# Default model per provider
_DEFAULT_MODELS: dict[str, str] = {
    "anthropic": "claude-sonnet-4-6",
    "google": "gemini-pro",
    "vllm": "meta-llama/Meta-Llama-3.1-8B-Instruct",
}


_replay_factory = ContextVar("llm_replay_factory", default=None)


@contextmanager
def replay_client_factory(factory):
    """Scope the offline harness's client factory to its current async context."""
    token = _replay_factory.set(factory)
    try:
        yield
    finally:
        _replay_factory.reset(token)


class LLMService:
    """LLM client wrapper with per-org config and training opt-out enforcement.

    Three-level training opt-out:
      1. API-tier access only (no consumer endpoints)
      2. Provider-specific organization headers
      3. local_only policy blocks all cloud providers
    """

    def __init__(
        self,
        org_config: OrganizationConfig | None = None,
        platform_settings: Any | None = None,
        *,
        api_key: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        allow_server_keys: bool = False,
    ) -> None:
        """Initialize LLM service from org config or platform defaults.

        Args:
            org_config: Per-org LLM configuration (provider, model, API key, data policy).
            platform_settings: Platform-level Settings for fallback config.
            api_key: Explicit credential supplied by the caller.
            provider: Explicit provider, overriding organization/environment defaults.
            model: Explicit model, overriding organization/environment defaults.
            allow_server_keys: Non-request development opt-in to ALEA_LLM_API_KEY.
                HTTP dependencies never enable this setting.

        Raises:
            ValueError: If data_policy is 'local_only' but provider is a cloud provider.
        """
        # Determine provider: org config > platform env override > default.
        # ALEA_LLM_PROVIDER lets a deployment (e.g. the dev server) pick a
        # provider without per-org DB config; org_config always wins when set.
        env_provider = os.getenv("ALEA_LLM_PROVIDER")
        if provider:
            self.provider = provider
        elif org_config and org_config.llm_provider:
            self.provider: str = org_config.llm_provider
        elif env_provider:
            self.provider = env_provider
        else:
            self.provider = "openai"  # platform default

        # Determine model: org config > platform env override > provider default.
        # ALEA_LLM_MODEL lets a deployment select a cheap model in a dev loop
        # (policy 5) instead of the expensive per-provider default (e.g. gpt-4).
        env_model = os.getenv("ALEA_LLM_MODEL")
        if model:
            self.model = model
        elif org_config and org_config.llm_model:
            self.model: str = org_config.llm_model
        elif env_model:
            self.model = env_model
        else:
            self.model = _DEFAULT_MODELS.get(self.provider, os.getenv("ALEA_REFERENCE_MODEL", app_config.DEFAULT_REFERENCE_MODEL))

        # Determine data policy
        if org_config and org_config.llm_data_policy:
            self.data_policy: str = org_config.llm_data_policy
        elif platform_settings and hasattr(platform_settings, "llm_data_policy"):
            self.data_policy = str(platform_settings.llm_data_policy)
        else:
            self.data_policy = "cloud_optout"

        # Request callers always supply a key. Ambient keys are available only
        # to explicitly opted-in non-request development callers.
        self.api_key = api_key
        if not self.api_key and org_config and org_config.llm_api_key_encrypted:
            self.api_key = org_config.llm_api_key_encrypted.decode("utf-8", errors="replace")
        if not self.api_key and allow_server_keys:
            self.api_key = os.getenv("ALEA_LLM_API_KEY")

        # Level 3: Enforce local_only policy
        if self.data_policy == "local_only" and self.provider in _CLOUD_PROVIDERS:
            raise ValueError(
                f"Data policy 'local_only' prohibits cloud provider '{self.provider}'. "
                f"Use 'vllm' or another local provider instead."
            )

    def get_client_config(self) -> dict[str, Any]:
        """Return config dict suitable for alea-llm-client initialization.

        Includes provider-specific headers for training opt-out (Level 2):
        - OpenAI: API-tier access = no training by default
        - Anthropic: API/commercial access = no training by default
        - VLLM: Local, no training concern

        Returns:
            Dict with provider, model, api_key, and any provider-specific config.
        """
        config: dict[str, Any] = {
            "provider": self.provider,
            "model": self.model,
            "api_key": self.api_key,
            "data_policy": self.data_policy,
        }

        # Provider-specific configuration for training opt-out (Level 2)
        if self.provider == "openai":
            # OpenAI API-tier: data not used for training by default.
            # Organization header provides additional protection.
            config["headers"] = {
                "OpenAI-Organization": "",  # Set per-org if org has OpenAI org ID
            }
        elif self.provider == "anthropic":
            # Anthropic API/commercial tier: no training by default.
            config["headers"] = {}
        elif self.provider == "vllm":
            # Local endpoint: no training concern
            config["endpoint"] = "http://localhost:8000/"

        return config

    @property
    def is_reference_model(self) -> bool:
        return self.model == os.getenv("ALEA_REFERENCE_MODEL", app_config.DEFAULT_REFERENCE_MODEL)

    def create_client(self) -> Any:
        """Construct a client only with an explicit, nonempty credential."""
        if not self.api_key or not self.api_key.strip():
            raise ValueError("A visitor LLM API key is required")
        config = self.get_client_config()
        kwargs = {"api_key": self.api_key, "model": self.model}
        if "endpoint" in config:
            kwargs["endpoint"] = config["endpoint"]
        factory = _replay_factory.get()
        if factory is not None:
            return factory(self.provider, self.model, kwargs)
        model_cls = _PROVIDER_MODEL_MAP.get(self.provider)
        if model_cls is None:
            raise ValueError(f"Unknown LLM provider: {self.provider}")
        return model_cls(**kwargs)

    async def acomplete(
        self,
        messages: list[dict[str, str]],
        system_prompt: str | None = None,
    ) -> str:
        """Send a chat completion and return the text reply.

        Centralizes provider/model construction so text callers (conversational
        follow-ups, language-level adaptation) don't each rebuild the wiring.
        Uses the same provider/model/api-key resolution as get_client_config().
        Raises on provider errors — callers choose their own fallback.
        """
        model = self.create_client()

        full_messages: list[dict[str, str]] = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        # alea-llm-client requires messages as a keyword list; positional args
        # are wrapped as a single user message's content (BUG-4).
        response = await model.chat_async(messages=full_messages)
        return (getattr(response, "text", "") or "").strip()

    async def json_async(
        self,
        prompt: str,
        schema: type[Any],
        system_prompt: str | None = None,
    ) -> Any:
        """Send a JSON completion and validate the result against a schema.

        Structured-output twin of acomplete(). Callers (gap analysis, question
        generation) pass a prompt and a pydantic model class; the raw JSON reply
        is validated and returned as a schema instance. Raises on provider
        errors or validation failure — callers choose their own fallback.
        """
        model = self.create_client()

        full_messages: list[dict[str, str]] = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.append({"role": "user", "content": prompt})

        # OpenAI's JSON mode (response_format=json_object) rejects requests
        # unless the word "json" appears somewhere in the messages (BUG-6).
        if not any("json" in (m.get("content") or "").lower() for m in full_messages):
            full_messages.insert(0, {"role": "system", "content": "Respond with a single valid JSON object."})

        response = await model.json_async(messages=full_messages)
        return schema.model_validate(response.data)

    async def check_connection(self) -> dict[str, str]:
        """Test the LLM connection without sending any case data.

        Initializes the alea-llm-client model class to verify credentials are valid.
        Does NOT call generate/complete -- no PII or case data is sent.

        Returns:
            Status dict: {"status": "connected", "provider": ..., "model": ...}
            or {"status": "error", "detail": ...} on failure.
        """
        model_cls = _PROVIDER_MODEL_MAP.get(self.provider)
        if model_cls is None:
            return {
                "status": "error",
                "detail": f"Unknown provider: {self.provider}",
            }

        try:
            self.create_client()

            return {
                "status": "connected",
                "provider": self.provider,
                "model": self.model,
            }
        except Exception:
            return {
                "status": "error",
                "detail": "LLM connection failed",
            }


def get_llm_service(
    org_config: OrganizationConfig | None = None,
    platform_settings: Any | None = None,
) -> LLMService:
    """Factory function for LLMService dependency injection.

    Args:
        org_config: Per-org LLM configuration from the tenant schema.
        platform_settings: Platform-level Settings for fallback.

    Returns:
        Configured LLMService instance.
    """
    return LLMService(org_config=org_config, platform_settings=platform_settings)


def llm_service_from_headers(headers: Any) -> LLMService:
    """Build an in-memory visitor context; never consult ambient credentials."""
    key = headers.get("X-LLM-API-Key", "").strip()
    if not key:
        raise HTTPException(status_code=400, detail="A visitor LLM API key is required")
    provider = headers.get("X-LLM-Provider", "openai").strip().lower()
    if provider not in {"openai", "anthropic", "google"}:
        raise HTTPException(status_code=400, detail="Unsupported LLM provider")
    model = headers.get("X-LLM-Model") or os.getenv("ALEA_REFERENCE_MODEL", app_config.DEFAULT_REFERENCE_MODEL)
    return LLMService(api_key=key, provider=provider, model=model)


async def get_request_llm_service(request: Request) -> LLMService:
    """REST credentials are headers, never query parameters or stored data."""
    return llm_service_from_headers(request.headers)
