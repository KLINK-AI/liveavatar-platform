"""
TTS (Text-to-Speech) Service Layer.

Converts LLM text responses into PCM 16Bit 24KHz audio
for LiveAvatar LITE Mode. The avatar receives raw audio
and performs lip-sync rendering.

Architecture:
  BaseTTSProvider (ABC)
    └── ElevenLabsProvider  — Primary (streaming, low latency)

Factory Pattern: get_tts_provider(tenant) returns the right provider.
"""

from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional
import structlog

logger = structlog.get_logger()


class BaseTTSProvider(ABC):
    """Abstract base class for TTS providers."""

    @abstractmethod
    async def text_to_speech_stream(
        self,
        text: str,
        voice_id: str,
        sample_rate: int = 24000,
    ) -> AsyncIterator[bytes]:
        """
        Convert text to audio in streaming mode.

        Yields PCM 16Bit audio chunks (~1 second each).
        This is the preferred method for LiveAvatar LITE —
        it enables sentence-by-sentence avatar speech.

        Args:
            text: Text to synthesize
            voice_id: Provider-specific voice identifier
            sample_rate: Output sample rate (24000 for LiveAvatar LITE)

        Yields:
            bytes: Raw PCM 16Bit audio chunks
        """
        ...

    @abstractmethod
    async def text_to_speech(
        self,
        text: str,
        voice_id: str,
        sample_rate: int = 24000,
    ) -> bytes:
        """
        Convert text to audio in batch mode.

        Returns complete PCM 16Bit audio buffer.
        Use for short texts where streaming overhead isn't justified.

        Args:
            text: Text to synthesize
            voice_id: Provider-specific voice identifier
            sample_rate: Output sample rate

        Returns:
            bytes: Complete raw PCM 16Bit audio
        """
        ...

    @abstractmethod
    async def close(self):
        """Release provider resources."""
        ...


class TTSProviderFactory:
    """Factory to instantiate TTS providers based on configuration."""

    _providers: dict[str, BaseTTSProvider] = {}

    @classmethod
    def get_provider(
        cls,
        provider_name: str = "elevenlabs",
        api_key: Optional[str] = None,
    ) -> BaseTTSProvider:
        """
        Get or create a TTS provider instance.

        Args:
            provider_name: "elevenlabs" (more providers can be added)
            api_key: Optional API key override (per-tenant)

        Returns:
            BaseTTSProvider instance
        """
        cache_key = f"{provider_name}:{api_key or 'default'}"

        if cache_key not in cls._providers:
            if provider_name == "elevenlabs":
                from services.tts.elevenlabs_provider import ElevenLabsProvider
                cls._providers[cache_key] = ElevenLabsProvider(api_key=api_key)
            else:
                raise ValueError(f"Unknown TTS provider: {provider_name}")

        return cls._providers[cache_key]

    @classmethod
    async def close_all(cls):
        """Close all cached provider instances."""
        for provider in cls._providers.values():
            await provider.close()
        cls._providers.clear()
