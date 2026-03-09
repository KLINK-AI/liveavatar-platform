"""
ElevenLabs TTS Provider — Text to PCM 16Bit 24KHz Audio.

Converts LLM text output into raw PCM audio suitable for
LiveAvatar LITE Mode's `agent.speak` WebSocket command.

Key specs:
- Output: PCM signed 16-bit little-endian, mono
- Sample rate: 24000 Hz (required by LiveAvatar LITE)
- Streaming: ~1 second chunks for low-latency avatar speech
- Supports ElevenLabs Multilingual v2 for German content
"""

from typing import AsyncIterator, Optional
import io
import struct
import structlog

from config import get_settings
from services.tts import BaseTTSProvider

logger = structlog.get_logger()
settings = get_settings()


class ElevenLabsProvider(BaseTTSProvider):
    """
    ElevenLabs TTS implementation using their streaming API.

    Produces PCM 16Bit 24KHz audio chunks optimized for
    real-time avatar lip-sync via LiveAvatar LITE WebSocket.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_id: Optional[str] = None,
    ):
        self.api_key = api_key or settings.elevenlabs_api_key
        self.model_id = model_id or settings.elevenlabs_model_id
        self._client = None

    def _get_client(self):
        """Lazy-init ElevenLabs client."""
        if self._client is None:
            from elevenlabs.client import ElevenLabs
            self._client = ElevenLabs(api_key=self.api_key)
        return self._client

    async def text_to_speech_stream(
        self,
        text: str,
        voice_id: str,
        sample_rate: int = 24000,
    ) -> AsyncIterator[bytes]:
        """
        Stream text to PCM audio chunks via ElevenLabs API.

        Each yielded chunk is ~1 second of PCM 16Bit audio.
        The chunks are sent directly to LiveAvatar via
        WebSocket `agent.speak` command (Base64 encoded).

        Args:
            text: Text to synthesize (supports German, English, etc.)
            voice_id: ElevenLabs voice ID
            sample_rate: Must be 24000 for LiveAvatar LITE

        Yields:
            bytes: PCM 16Bit signed LE audio chunks
        """
        if not text.strip():
            return

        voice_id = voice_id or settings.elevenlabs_default_voice_id
        if not voice_id:
            raise ValueError("No voice_id configured. Set elevenlabs_default_voice_id or pass voice_id.")

        logger.info(
            "TTS streaming start",
            text_length=len(text),
            voice_id=voice_id,
            model=self.model_id,
            sample_rate=sample_rate,
        )

        client = self._get_client()

        try:
            # Use ElevenLabs generate with streaming
            # output_format: pcm_24000 = PCM signed 16-bit LE, 24kHz, mono
            audio_stream = client.text_to_speech.convert(
                text=text,
                voice_id=voice_id,
                model_id=self.model_id,
                output_format=f"pcm_{sample_rate}",
                voice_settings={
                    "stability": 0.5,
                    "similarity_boost": 0.75,
                    "style": 0.0,
                    "use_speaker_boost": True,
                },
            )

            # ElevenLabs returns an iterator of audio bytes
            # We accumulate into ~1 second chunks for smooth avatar speech
            chunk_size = sample_rate * 2  # 1 second of PCM 16Bit = sample_rate * 2 bytes
            buffer = bytearray()

            for audio_chunk in audio_stream:
                buffer.extend(audio_chunk)

                # Yield complete chunks (~1 second each)
                while len(buffer) >= chunk_size:
                    yield bytes(buffer[:chunk_size])
                    buffer = buffer[chunk_size:]

            # Yield remaining audio
            if buffer:
                yield bytes(buffer)

            logger.info("TTS streaming complete", text_length=len(text))

        except Exception as e:
            logger.error("TTS streaming error", error=str(e), voice_id=voice_id)
            raise

    async def text_to_speech(
        self,
        text: str,
        voice_id: str,
        sample_rate: int = 24000,
    ) -> bytes:
        """
        Convert text to complete PCM audio buffer.

        Collects all streaming chunks into a single buffer.
        Use for short texts or when you need the complete audio at once.

        Args:
            text: Text to synthesize
            voice_id: ElevenLabs voice ID
            sample_rate: Output sample rate

        Returns:
            bytes: Complete PCM 16Bit audio
        """
        audio_buffer = bytearray()

        async for chunk in self.text_to_speech_stream(text, voice_id, sample_rate):
            audio_buffer.extend(chunk)

        logger.info(
            "TTS batch complete",
            text_length=len(text),
            audio_bytes=len(audio_buffer),
            duration_seconds=round(len(audio_buffer) / (sample_rate * 2), 2),
        )

        return bytes(audio_buffer)

    async def close(self):
        """Release ElevenLabs client resources."""
        self._client = None
        logger.debug("ElevenLabs TTS provider closed")
