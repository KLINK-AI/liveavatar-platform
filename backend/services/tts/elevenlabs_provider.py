"""
ElevenLabs TTS Provider — Text to PCM 16Bit 24KHz Audio.

Converts LLM text output into raw PCM audio suitable for
LiveAvatar LITE Mode's `agent.speak` WebSocket command.

Key specs:
- Output: PCM signed 16-bit little-endian, mono
- Sample rate: 24000 Hz (required by LiveAvatar LITE)
- TRUE STREAMING: Audio chunks flow to avatar as ElevenLabs generates them
- Supports ElevenLabs Turbo v2.5 for low-latency German/multilingual content

v2.4 (Latency Optimization):
  - Switched from collect-then-yield to true streaming via asyncio.Queue
  - Audio chunks are forwarded to avatar as soon as ElevenLabs produces them
  - Reduces time-to-first-audio by 500-2000ms
"""

from typing import AsyncIterator, Optional
import asyncio
import io
import struct
import time
import structlog

from config import get_settings
from services.tts import BaseTTSProvider

logger = structlog.get_logger()
settings = get_settings()


class ElevenLabsProvider(BaseTTSProvider):
    """
    ElevenLabs TTS implementation with TRUE streaming.

    Produces PCM 16Bit 24KHz audio chunks optimized for
    real-time avatar lip-sync via LiveAvatar LITE WebSocket.

    Key optimization: Audio chunks are forwarded to the avatar
    AS they arrive from ElevenLabs, not after the entire response
    is collected. This reduces perceived latency significantly.
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
        language: Optional[str] = None,
    ) -> AsyncIterator[bytes]:
        """
        TRUE STREAMING: Text → PCM audio chunks via ElevenLabs API.

        Each yielded chunk is ~0.5 seconds of PCM 16Bit audio.
        Chunks flow to the caller AS ElevenLabs generates them,
        using an asyncio.Queue to bridge the sync SDK to async code.

        Previous implementation collected ALL chunks before yielding any,
        adding 500-2000ms unnecessary latency. This version eliminates that.

        Args:
            text: Text to synthesize (supports German, English, etc.)
            voice_id: ElevenLabs voice ID
            sample_rate: Must be 24000 for LiveAvatar LITE
            language: ISO 639-1 language code for multilingual models (e.g. 'de', 'en')

        Yields:
            bytes: PCM 16Bit signed LE audio chunks (~0.5s each)
        """
        if not text.strip():
            return

        voice_id = voice_id or settings.elevenlabs_default_voice_id
        if not voice_id:
            raise ValueError("No voice_id configured. Set elevenlabs_default_voice_id or pass voice_id.")

        t_start = time.monotonic()
        logger.info(
            "TTS streaming start",
            text_length=len(text),
            voice_id=voice_id,
            model=self.model_id,
            sample_rate=sample_rate,
            language=language,
        )

        client = self._get_client()
        loop = asyncio.get_event_loop()
        queue: asyncio.Queue[bytes | None] = asyncio.Queue()
        error_holder: list[Exception] = []

        def _generate_and_stream():
            """Run synchronous ElevenLabs SDK and push chunks to async queue."""
            try:
                # Build convert kwargs — include language_code for multilingual models
                convert_kwargs = dict(
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
                if language:
                    convert_kwargs["language_code"] = language
                audio_stream = client.text_to_speech.convert(**convert_kwargs)
                for chunk in audio_stream:
                    loop.call_soon_threadsafe(queue.put_nowait, chunk)
            except Exception as e:
                error_holder.append(e)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)  # Sentinel

        # Start TTS generation in background thread
        gen_task = asyncio.get_event_loop().run_in_executor(None, _generate_and_stream)

        try:
            # Re-chunk into ~0.5 second pieces for smooth avatar speech
            chunk_size = sample_rate  # 0.5 sec of PCM 16Bit (24000 samples × 2 bytes)
            buffer = bytearray()
            t_first_chunk = None

            while True:
                raw_chunk = await queue.get()
                if raw_chunk is None:  # Sentinel — generation complete
                    break

                if t_first_chunk is None:
                    t_first_chunk = time.monotonic()
                    logger.info(
                        "TTS first chunk received (true streaming)",
                        ms_to_first_chunk=round((t_first_chunk - t_start) * 1000),
                        text_length=len(text),
                    )

                buffer.extend(raw_chunk)

                while len(buffer) >= chunk_size:
                    yield bytes(buffer[:chunk_size])
                    buffer = buffer[chunk_size:]

            # Yield remaining audio
            if buffer:
                yield bytes(buffer)

            # Check for errors from the generation thread
            if error_holder:
                raise error_holder[0]

            await gen_task  # Ensure thread cleanup

            logger.info(
                "TTS streaming complete",
                text_length=len(text),
                total_ms=round((time.monotonic() - t_start) * 1000),
            )

        except Exception as e:
            logger.error("TTS streaming error", error=str(e), voice_id=voice_id)
            raise

    async def text_to_speech(
        self,
        text: str,
        voice_id: str,
        sample_rate: int = 24000,
        language: Optional[str] = None,
    ) -> bytes:
        """
        Convert text to complete PCM audio buffer.

        Collects all streaming chunks into a single buffer.
        Use for short texts or when you need the complete audio at once.

        Args:
            text: Text to synthesize
            voice_id: ElevenLabs voice ID
            sample_rate: Output sample rate
            language: ISO 639-1 language code for multilingual models

        Returns:
            bytes: Complete PCM 16Bit audio
        """
        audio_buffer = bytearray()

        async for chunk in self.text_to_speech_stream(text, voice_id, sample_rate, language=language):
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
