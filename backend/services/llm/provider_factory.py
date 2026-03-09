"""Factory for creating LLM provider instances based on configuration."""

from typing import Optional
import structlog

from config import get_settings
from services.llm.base import BaseLLMProvider
from services.llm.openai_provider import OpenAIProvider
from services.llm.anthropic_provider import AnthropicProvider
from services.llm.ollama_provider import OllamaProvider

logger = structlog.get_logger()
settings = get_settings()


class LLMProviderFactory:
    """
    Creates LLM provider instances based on provider name.

    Each tenant can have a different LLM provider and model.
    The factory resolves the correct implementation.
    """

    _providers: dict[str, BaseLLMProvider] = {}

    @classmethod
    def get_provider(
        cls,
        provider_name: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> BaseLLMProvider:
        """
        Get or create an LLM provider instance.

        Args:
            provider_name: "openai", "anthropic", or "ollama"
            model: Model name override
            api_key: API key override (tenant-specific keys)
        """
        provider_name = provider_name or settings.default_llm_provider
        cache_key = f"{provider_name}:{api_key or 'default'}"

        if cache_key not in cls._providers:
            cls._providers[cache_key] = cls._create_provider(
                provider_name, model, api_key
            )

        return cls._providers[cache_key]

    @classmethod
    def _create_provider(
        cls,
        provider_name: str,
        model: Optional[str],
        api_key: Optional[str],
    ) -> BaseLLMProvider:
        """Create a new provider instance."""

        if provider_name == "openai":
            return OpenAIProvider(
                api_key=api_key or settings.openai_api_key,
                default_model=model or settings.default_llm_model,
            )
        elif provider_name == "anthropic":
            return AnthropicProvider(
                api_key=api_key or settings.anthropic_api_key,
                default_model=model or "claude-sonnet-4-20250514",
            )
        elif provider_name == "ollama":
            return OllamaProvider(
                base_url=settings.ollama_base_url,
                default_model=model or "llama3.1",
            )
        else:
            raise ValueError(
                f"Unknown LLM provider: {provider_name}. "
                f"Supported: openai, anthropic, ollama"
            )

    @classmethod
    def get_provider_for_tenant(cls, tenant) -> BaseLLMProvider:
        """Get the LLM provider configured for a specific tenant."""
        return cls.get_provider(
            provider_name=tenant.llm_provider,
            model=tenant.llm_model,
            api_key=tenant.llm_api_key,
        )

    @classmethod
    async def close_all(cls):
        """Close all cached provider connections."""
        for provider in cls._providers.values():
            await provider.close()
        cls._providers.clear()
