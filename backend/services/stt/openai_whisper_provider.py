"""
OpenAI Whisper STT Provider — Batch Speech-to-Text Fallback.

Uses OpenAI's Whisper API for high-accuracy batch transcription.
Primarily serves as a fallback when Deepgram is unavailable
or for post-processing recorded sessions.

Key specs:
- Input: WAV, MP3, or raw PCM (converted to WAV internally)
- Mode: Batch only (no real-time streaming)
- Model: whisper-1
- Excellent for German, multilingual content
"""

from typing import AsyncIterator, Optional
import io
import wave
import structlog

from config import get_settings
from services.stt import BaseSTTProvider, TranscriptionResult

logger = structlog.get_logger()
settings = get_settings()


class OpenAIWhisperProvider(BaseSTTProvider):
    """
    OpenAI Whisper STT — high-accuracy batch transcription fallback.

    Since Whisper doesn't support real-time streaming,
    transcribe_stream() collects audio into a buffer and
    transcribes when speech pauses are detected.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.openai_api_key
        self._client = None

    def _get_client(self):
        """Lazy-init OpenAI client."""
        if self._client is None:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(api_key=self.api_key)
        return self._client

    @staticmethod
    def _pcm_to_wav(pcm_data: bytes, sample_rate: int = 24000) -> bytes:
        """
        Convert raw PCM 16Bit audio to WAV format.
        Whisper API requires a file format, not raw PCM.
        """
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(1)          # Mono
            wav_file.setsampwidth(2)          # 16-bit = 2 bytes
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_data)
        return wav_buffer.getvalue()

    async def transcribe_stream(
        self,
        audio_stream: AsyncIterator[bytes],
        sample_rate: int = 24000,
        language: str = "de",
    ) -> AsyncIterator[TranscriptionResult]:
        """
        Pseudo-streaming: collects audio chunks then batch-transcribes.

        Since Whisper doesn't support real-time streaming, this method:
        1. Collects audio until a significant pause (~2 seconds silence)
        2. Batch-transcribes the collected buffer
        3. Yields the result as a final transcription

        For real-time conversation, prefer DeepgramProvider.
        """
        import numpy as np

        SILENCE_THRESHOLD = 500      # RMS amplitude threshold
        SILENCE_DURATION = 2.0       # Seconds of silence before transcribing
        MIN_AUDIO_LENGTH = 0.5       # Minimum seconds of audio to transcribe

        buffer = bytearray()
        silence_frames = 0
        bytes_per_second = sample_rate * 2  # 16-bit mono
        silence_frames_threshold = int(SILENCE_DURATION * sample_rate * 2 / 4096)

        async for chunk in audio_stream:
            buffer.extend(chunk)

            # Detect silence by checking RMS of chunk
            if len(chunk) >= 2:
                samples = np.frombuffer(chunk, dtype=np.int16)
                rms = np.sqrt(np.mean(samples.astype(float) ** 2))

                if rms < SILENCE_THRESHOLD:
                    silence_frames += 1
                else:
                    silence_frames = 0

            # Transcribe when silence detected and buffer has enough audio
            audio_duration = len(buffer) / bytes_per_second
            if silence_frames >= silence_frames_threshold and audio_duration >= MIN_AUDIO_LENGTH:
                result = await self.transcribe(
                    bytes(buffer), sample_rate=sample_rate, language=language
                )
                if result.text:
                    yield result

                buffer.clear()
                silence_frames = 0

        # Transcribe remaining audio
        if len(buffer) > bytes_per_second * MIN_AUDIO_LENGTH:
            result = await self.transcribe(
                bytes(buffer), sample_rate=sample_rate, language=language
            )
            if result.text:
                yield result

    async def transcribe(
        self,
        audio: bytes,
        sample_rate: int = 24000,
        language: str = "de",
    ) -> TranscriptionResult:
        """
        Batch transcription of a complete audio buffer using Whisper.

        Converts PCM to WAV, sends to OpenAI Whisper API,
        returns transcription with confidence.
        """
        client = self._get_client()

        # Convert PCM to WAV (Whisper needs a file format)
        wav_data = self._pcm_to_wav(audio, sample_rate)

        # Create file-like object for the API
        audio_file = io.BytesIO(wav_data)
        audio_file.name = "audio.wav"

        logger.info("Whisper transcription start",
                     audio_bytes=len(audio),
                     duration_seconds=round(len(audio) / (sample_rate * 2), 2))

        response = await client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language=language,
            response_format="verbose_json",
        )

        text = response.text.strip() if hasattr(response, "text") else str(response).strip()

        logger.info("Whisper transcription complete",
                     text_length=len(text),
                     language=language)

        return TranscriptionResult(
            text=text,
            is_final=True,
            confidence=0.95,  # Whisper doesn't return confidence scores
            language=language,
        )

    async def close(self):
        """Release OpenAI client resources."""
        self._client = None
        logger.debug("OpenAI Whisper STT provider closed")
