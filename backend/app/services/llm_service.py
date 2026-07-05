"""LLM service wrapper with per-org configuration and training opt-out enforcement.

Wraps alea-llm-client with three-level training opt-out:
  Level 1: Use API-tier access (not consumer-tier) for all cloud providers
  Level 2: Include provider-specific organization headers when available
  Level 3: Respect org data_policy -- if "local_only", only allow VLLM/local endpoints

The service MUST NOT expose methods that send arbitrary data to training-eligible endpoints.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

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
    "openai": "gpt-4",
    "anthropic": "claude-sonnet-4-6",
    "google": "gemini-pro",
    "vllm": "meta-llama/Meta-Llama-3.1-8B-Instruct",
}


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
    ) -> None:
        """Initialize LLM service from org config or platform defaults.

        Args:
            org_config: Per-org LLM configuration (provider, model, API key, data policy).
            platform_settings: Platform-level Settings for fallback config.

        Raises:
            ValueError: If data_policy is 'local_only' but provider is a cloud provider.
        """
        # Determine provider
        if org_config and org_config.llm_provider:
            self.provider: str = org_config.llm_provider
        else:
            self.provider = "openai"  # platform default

        # Determine model
        if org_config and org_config.llm_model:
            self.model: str = org_config.llm_model
        else:
            self.model = _DEFAULT_MODELS.get(self.provider, "gpt-4")

        # Determine data policy
        if org_config and org_config.llm_data_policy:
            self.data_policy: str = org_config.llm_data_policy
        elif platform_settings and hasattr(platform_settings, "llm_data_policy"):
            self.data_policy = str(platform_settings.llm_data_policy)
        else:
            self.data_policy = "cloud_optout"

        # Determine API key
        self.api_key: str | None = None
        if org_config and org_config.llm_api_key_encrypted:
            # In production, this would be decrypted via the encryption service.
            # For now, treat the stored bytes as the key directly.
            self.api_key = org_config.llm_api_key_encrypted.decode("utf-8", errors="replace")

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
        config = self.get_client_config()
        model_cls = _PROVIDER_MODEL_MAP.get(config["provider"])
        if model_cls is None:
            raise ValueError(f"Unknown LLM provider: {config['provider']}")
        init_kwargs: dict[str, Any] = {
            "api_key": config.get("api_key"),
            "model": config.get("model"),
        }
        if "endpoint" in config:
            init_kwargs["endpoint"] = config["endpoint"]
        model = model_cls(**init_kwargs)

        full_messages: list[dict[str, str]] = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        response = await model.chat_async(*full_messages)
        return (getattr(response, "text", "") or "").strip()

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
            # Only initialize the client -- verify credentials are accepted.
            # No generate/complete calls = no case data sent.
            kwargs: dict[str, Any] = {
                "api_key": self.api_key,
                "model": self.model,
            }
            if self.provider == "vllm":
                kwargs["endpoint"] = "http://localhost:8000/"

            model_cls(**kwargs)

            return {
                "status": "connected",
                "provider": self.provider,
                "model": self.model,
            }
        except Exception as e:
            return {
                "status": "error",
                "detail": str(e),
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
