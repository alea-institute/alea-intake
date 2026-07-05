"""Tests for LLM service wrapper with per-org configuration and training opt-out.

Covers:
- Service initialization with org config
- Local-only policy enforcement
- Cloud opt-out config generation
- Connection check (mocked)
- No case data in connection check
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import Settings


def _make_org_config(
    *,
    provider: str | None = "openai",
    model: str | None = "gpt-4",
    data_policy: str = "cloud_optout",
    api_key_encrypted: bytes | None = None,
) -> MagicMock:
    """Create a mock OrganizationConfig with the given LLM settings."""
    config = MagicMock()
    config.llm_provider = provider
    config.llm_model = model
    config.llm_data_policy = data_policy
    config.llm_api_key_encrypted = api_key_encrypted
    return config


def _make_settings(**overrides) -> Settings:
    """Create test settings with sensible defaults."""
    defaults = {
        "secret_key": "test-secret",
        "database_backend": "sqlite",
        "sqlite_path": ":memory:",
    }
    defaults.update(overrides)
    return Settings(**defaults)


class TestLLMServiceInit:
    """Test LLMService initialization with various configurations."""

    def test_llm_service_init_with_org_config(self):
        """LLMService.__init__ with org config containing provider='openai', model='gpt-4' initializes correctly."""
        from app.services.llm_service import LLMService

        org_config = _make_org_config(provider="openai", model="gpt-4")
        service = LLMService(org_config=org_config)

        assert service.provider == "openai"
        assert service.model == "gpt-4"

    def test_llm_service_init_with_platform_defaults(self):
        """LLMService falls back to platform defaults when no org config."""
        from app.services.llm_service import LLMService

        service = LLMService()
        # Should have some default provider/model
        assert service.provider is not None
        assert service.data_policy == "cloud_optout"

    def test_llm_service_local_only_policy_blocks_cloud(self):
        """LLMService with llm_data_policy='local_only' raises error if cloud provider configured."""
        from app.services.llm_service import LLMService

        org_config = _make_org_config(provider="openai", data_policy="local_only")
        with pytest.raises(ValueError, match="local_only"):
            LLMService(org_config=org_config)

    def test_llm_service_local_only_allows_vllm(self):
        """LLMService with local_only policy allows VLLM (local endpoint)."""
        from app.services.llm_service import LLMService

        org_config = _make_org_config(provider="vllm", data_policy="local_only")
        service = LLMService(org_config=org_config)
        assert service.provider == "vllm"
        assert service.data_policy == "local_only"


class TestLLMServiceClientConfig:
    """Test get_client_config() returns correct provider-specific config."""

    def test_cloud_optout_config_openai(self):
        """get_client_config() for OpenAI includes provider and model."""
        from app.services.llm_service import LLMService

        org_config = _make_org_config(provider="openai", model="gpt-4")
        service = LLMService(org_config=org_config)
        config = service.get_client_config()

        assert config["provider"] == "openai"
        assert config["model"] == "gpt-4"
        assert "api_key" in config

    def test_cloud_optout_config_anthropic(self):
        """get_client_config() for Anthropic includes provider and model."""
        from app.services.llm_service import LLMService

        org_config = _make_org_config(provider="anthropic", model="claude-sonnet-4-6")
        service = LLMService(org_config=org_config)
        config = service.get_client_config()

        assert config["provider"] == "anthropic"
        assert config["model"] == "claude-sonnet-4-6"

    def test_vllm_config_includes_local_endpoint(self):
        """get_client_config() for VLLM includes local endpoint."""
        from app.services.llm_service import LLMService

        org_config = _make_org_config(provider="vllm", model="llama-3", data_policy="local_only")
        service = LLMService(org_config=org_config)
        config = service.get_client_config()

        assert config["provider"] == "vllm"
        assert "endpoint" in config


class TestLLMServiceConnectionCheck:
    """Test check_connection() method."""

    async def test_llm_service_check_connection_success(self):
        """check_connection returns status dict on success."""
        from app.services.llm_service import LLMService, _PROVIDER_MODEL_MAP

        org_config = _make_org_config(provider="openai", model="gpt-4")
        service = LLMService(org_config=org_config)

        # Mock the provider model class in the lookup map
        mock_model_cls = MagicMock()
        with patch.dict(_PROVIDER_MODEL_MAP, {"openai": mock_model_cls}):
            result = await service.check_connection()

        assert result["status"] == "connected"
        assert result["provider"] == "openai"
        assert result["model"] == "gpt-4"

    async def test_llm_service_check_connection_failure(self):
        """check_connection returns error status on failure."""
        from app.services.llm_service import LLMService, _PROVIDER_MODEL_MAP

        org_config = _make_org_config(provider="openai", model="gpt-4")
        service = LLMService(org_config=org_config)

        mock_model_cls = MagicMock(side_effect=Exception("Connection refused"))
        with patch.dict(_PROVIDER_MODEL_MAP, {"openai": mock_model_cls}):
            result = await service.check_connection()

        assert result["status"] == "error"
        assert "Connection refused" in result["detail"]

    async def test_llm_service_no_case_data_in_check(self):
        """check_connection does not send any PII or case data."""
        from app.services.llm_service import LLMService, _PROVIDER_MODEL_MAP

        org_config = _make_org_config(provider="openai", model="gpt-4")
        service = LLMService(org_config=org_config)

        mock_model_cls = MagicMock()
        mock_instance = MagicMock()
        mock_model_cls.return_value = mock_instance
        with patch.dict(_PROVIDER_MODEL_MAP, {"openai": mock_model_cls}):
            await service.check_connection()

        # Verify no generate/completion methods were called (no case data sent)
        mock_instance.generate.assert_not_called()
        if hasattr(mock_instance, "complete"):
            mock_instance.complete.assert_not_called()


class TestLLMServiceAcomplete:
    """Test acomplete() builds the provider model and returns response text."""

    async def test_acomplete_returns_response_text(self):
        """acomplete() constructs the model, calls chat_async, returns .text."""
        from app.services.llm_service import LLMService, _PROVIDER_MODEL_MAP

        org_config = _make_org_config(provider="openai", model="gpt-4")
        service = LLMService(org_config=org_config)

        mock_instance = MagicMock()
        mock_instance.chat_async = AsyncMock(return_value=MagicMock(text="hello"))
        mock_model_cls = MagicMock(return_value=mock_instance)

        with patch.dict(_PROVIDER_MODEL_MAP, {"openai": mock_model_cls}):
            result = await service.acomplete(
                [{"role": "user", "content": "hi"}], system_prompt="be brief"
            )

        assert result == "hello"
        # chat_async received the system prompt prepended to the messages
        sent = mock_instance.chat_async.await_args.args
        assert sent[0] == {"role": "system", "content": "be brief"}
        assert sent[1] == {"role": "user", "content": "hi"}

    async def test_acomplete_unknown_provider_raises(self):
        """acomplete() raises ValueError when provider has no model class."""
        from app.services.llm_service import LLMService, _PROVIDER_MODEL_MAP

        org_config = _make_org_config(provider="openai", model="gpt-4")
        service = LLMService(org_config=org_config)

        with patch.dict(_PROVIDER_MODEL_MAP, {}, clear=True):
            with pytest.raises(ValueError, match="Unknown LLM provider"):
                await service.acomplete([{"role": "user", "content": "hi"}])


class TestGetLLMServiceFactory:
    """Test the get_llm_service factory function."""

    def test_get_llm_service_returns_instance(self):
        """get_llm_service() returns an LLMService instance."""
        from app.services.llm_service import get_llm_service

        service = get_llm_service()
        from app.services.llm_service import LLMService

        assert isinstance(service, LLMService)

    def test_get_llm_service_with_org_config(self):
        """get_llm_service(org_config) passes config to LLMService."""
        from app.services.llm_service import get_llm_service

        org_config = _make_org_config(provider="anthropic", model="claude-sonnet-4-6")
        service = get_llm_service(org_config=org_config)
        assert service.provider == "anthropic"
