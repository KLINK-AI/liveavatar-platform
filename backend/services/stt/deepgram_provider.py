"""
Deepgram STT Provider — Real-time Streaming Speech-to-Text.

Transcribes user audio from LiveKit WebRTC in real-time
using Deepgram's Nova-2 model. Optimized for German
with low-latency interim results.

Key specs:
- Input: PCM signed 16-bit LE, mono
- Streaming: WebSocket-based real-time transcription
- Model: nova-2 (best accuracy for German)
- Features: interim results, endpointing, punctuation
"""

from typing import AsyncIterator, Optional
import asyncio
import structlog

from config import get_settings
from services.stt import BaseSTTProvider, TranscriptionResult

logger = structlog.get_logger()
settings = get_settings()


class DeepgramProvider(BaseSTTProvider):
    """
    Deepgram real-time STT using their streaming WebSocket API.

    Produces interim + final transcription results for live
    conversation with the avatar.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        language: Optional[str] = None,
    ):
        self.api_key = api_key or settings.deepgram_api_key
        self.model = model or settings.deepgram_model
        self.language = language or settings.deepgram_language
        self._client = None

    def _get_client(self):
        """Lazy-init Deepgram client."""
        if self._client is None:
            from deepgram import DeepgramClient
            self._client = DeepgramClient(api_key=self.api_key)
        return self._client

    async def transcribe_stream(
        self,
        audio_stream: AsyncIterator[bytes],
        sample_rate: int = 24000,
        language: str = "de",
    ) -> AsyncIterator[TranscriptionResult]:
        """
        Transcribe audio stream in real-time via Deepgram WebSocket.

        Yields interim results (is_final=False) for UI feedback,
        and final results (is_final=True) when an utterance is complete.

        The ConversationEngine processes only final results —
        interim results are forwarded to the frontend for live display.
        """
        from deepgram import (
            LiveTranscriptionEvents,
            LiveOptions,
        )

        client = self._get_client()

        # Configure live transcription options
        options = LiveOptions(
            model=self.model,
            language=language or self.language,
            encoding="linear16",
            sample_rate=sample_rate,
            channels=1,
            punctuate=True,
            interim_results=True,
            endpointing=300,  # ms of silence before finalizing
            vad_events=True,
            smart_format=True,
        )

        # Result queue for async iteration
        result_queue: asyncio.Queue[Optional[TranscriptionResult]] = asyncio.Queue()

        # Create live connection
        connection = client.listen.live.v("1")

        # Event handlers
        @connection.on(LiveTranscriptionEvents.Transcript)
        async def on_transcript(self_conn, result, **kwargs):
            try:
                alt = result.channel.alternatives[0]
                text = alt.transcript.strip()

                if text:
                    is_final = result.is_final
                    confidence = alt.confidence if hasattr(alt, "confidence") else 1.0

                    await result_queue.put(TranscriptionResult(
                        text=text,
                        is_final=is_final,
                        confidence=confidence,
                        language=language,
                    ))

                    if is_final:
                        logger.info("STT final", text=text[:80], confidence=confidence)
                    else:
                        logger.debug("STT interim", text=text[:50])
            except (IndexError, AttributeError):
                pass

        @connection.on(LiveTranscriptionEvents.Error)
        async def on_error(self_conn, error, **kwargs):
            logger.error("Deepgram STT error", error=str(error))

        @connection.on(LiveTranscriptionEvents.Close)
        async def on_close(self_conn, close, **kwargs):
            logger.info("Deepgram connection closed")
            await result_queue.put(None)  # Signal end

        # Start connection
        if await connection.start(options) is False:
            raise RuntimeError("Failed to start Deepgram connection")

        logger.info("Deepgram STT streaming started",
                     model=self.model, language=language, sample_rate=sample_rate)

        # Feed audio in background
        async def feed_audio():
            try:
                async for chunk in audio_stream:
                    connection.send(chunk)
                await connection.finish()
            except Exception as e:
                logger.error("Audio feed error", error=str(e))
                await result_queue.put(None)

        feed_task = asyncio.create_task(feed_audio())

        # Yield results as they arrive
        try:
            while True:
                result = await result_queue.get()
                if result is None:
                    break
                yield result
        finally:
            feed_task.cancel()
            try:
                await feed_task
            except asyncio.CancelledError:
                pass

    async def transcribe(
        self,
        audio: bytes,
        sample_rate: int = 24000,
        language: str = "de",
    ) -> TranscriptionResult:
        """
        Batch transcription of a complete audio buffer.

        Uses Deepgram's pre-recorded API (REST, not WebSocket).
        """
        from deepgram import PrerecordedOptions

        client = self._get_client()

        options = PrerecordedOptions(
            model=self.model,
            language=language or self.language,
            encoding="linear16",
            sample_rate=sample_rate,
            channels=1,
            punctuate=True,
            smart_format=True,
        )

        source = {"buffer": audio, "mimetype": "audio/raw"}
        response = await client.listen.rest.v("1").transcribe_file(source, options)

        alt = response.results.channels[0].alternatives[0]
        text = alt.transcript.strip()
        confidence = alt.confidence if hasattr(alt, "confidence") else 1.0

        logger.info("STT batch complete",
                     text_length=len(text),
                     confidence=confidence,
                     audio_bytes=len(audio))

        return TranscriptionResult(
            text=text,
            is_final=True,
            confidence=confidence,
            language=language,
        )

    async def close(self):
        """Release Deepgram client resources."""
        self._client = None
        logger.debug("Deepgram STT provider closed")
