"""
STT (Speech-to-Text) Service Layer.

Transcribes user audio from LiveKit WebRTC stream
into text for the ConversationEngine.

Architecture:
  BaseSTTProvider (ABC)
    ├── DeepgramProvider    — Primary (real-time streaming)
    └── OpenAIWhisperProvider — Fallback (batch transcription)

Factory Pattern: get_stt_provider(provider_name) returns the right provider.
"""

from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional
import structlog

logger = structlog.get_logger()


class TranscriptionResult:
    """Represents a transcription result from STT."""

    def __init__(
        self,
        text: str,
        is_final: bool = True,
        confidence: float = 1.0,
        language: Optional[str] = None,
    ):
        self.text = text
        self.is_final = is_final
        self.confidence = confidence
        self.language = language

    def __repr__(self) -> str:
        return f"<Transcription '{self.text[:50]}...' final={self.is_final} conf={self.confidence:.2f}>"


class BaseSTTProvider(ABC):
    """Abstract base class for STT providers."""

    @abstractmethod
    async def transcribe_stream(
        self,
        audio_stream: AsyncIterator[bytes],
        sample_rate: int = 24000,
        language: str = "de",
    ) -> AsyncIterator[TranscriptionResult]:
        """
        Transcribe an audio stream in real-time.

        Yields partial and final transcription results as they arrive.
        Use for live conversation with the avatar.

        Args:
            audio_stream: Async iterator of PCM 16Bit audio chunks
            sample_rate: Input audio sample rate
            language: BCP-47 language code

        Yields:
            TranscriptionResult with partial or final text
        """
        ...

    @abstractmethod
    async def transcribe(
        self,
        audio: bytes,
        sample_rate: int = 24000,
        language: str = "de",
    ) -> TranscriptionResult:
        """
        Transcribe a complete audio buffer (batch mode).

        Args:
            audio: Complete PCM 16Bit audio buffer
            sample_rate: Input audio sample rate
            language: BCP-47 language code

        Returns:
            TranscriptionResult with the full transcription
        """
        ...

    @abstractmethod
    async def close(self):
        """Release provider resources."""
        ...


class STTProviderFactory:
    """Factory to instantiate STT providers based on configuration."""

    _providers: dict[str, BaseSTTProvider] = {}

    @classmethod
    def get_provider(
        cls,
        provider_name: Optional[str] = None,
    ) -> BaseSTTProvider:
        """
        Get or create an STT provider instance.

        Args:
            provider_name: "deepgram" or "openai" (defaults to config)

        Returns:
            BaseSTTProvider instance
        """
        from config import get_settings
        settings = get_settings()

        provider_name = provider_name or settings.stt_provider

        if provider_name not in cls._providers:
            if provider_name == "deepgram":
                from services.stt.deepgram_provider import DeepgramProvider
                cls._providers[provider_name] = DeepgramProvider()
            elif provider_name == "openai":
                from services.stt.openai_whisper_provider import OpenAIWhisperProvider
                cls._providers[provider_name] = OpenAIWhisperProvider()
            else:
                raise ValueError(f"Unknown STT provider: {provider_name}")

        return cls._providers[provider_name]

    @classmethod
    async def close_all(cls):
        """Close all cached provider instances."""
        for provider in cls._providers.values():
            await provider.close()
        cls._providers.clear()
