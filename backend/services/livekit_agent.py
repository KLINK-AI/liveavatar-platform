"""
LiveKit Agent Service — Captures User Audio from LiveKit Room.

Joins a LiveKit room as an agent participant, subscribes to
the user's audio track, and forwards raw PCM audio to the
STT (Speech-to-Text) service for transcription.

Flow:
  User speaks into microphone
    → Audio via WebRTC to LiveKit room
    → This agent captures the audio track
    → Forwards PCM 16Bit chunks to STT provider
    → STT yields transcribed text
    → ConversationEngine processes the text
    → TTS generates response audio
    → WebSocket sends audio to LiveAvatar for lip-sync

This service bridges the gap between the user's microphone
and our STT pipeline.
"""

from typing import Optional, Callable, Awaitable
import asyncio
import structlog

from config import get_settings
from services.stt import STTProviderFactory, TranscriptionResult

logger = structlog.get_logger()
settings = get_settings()

# Callback type for transcription results
TranscriptionCallback = Callable[[TranscriptionResult], Awaitable[None]]


class LiveKitAgentService:
    """
    Joins a LiveKit room, captures user audio, feeds it to STT.

    Operates as a background service per-session:
    1. Joins room with agent token
    2. Subscribes to audio tracks
    3. Forwards audio chunks to STT provider
    4. Calls back with transcription results
    """

    def __init__(
        self,
        livekit_url: str,
        agent_token: str,
        session_id: str,
        stt_provider: Optional[str] = None,
        language: str = "de",
    ):
        self.livekit_url = livekit_url
        self.agent_token = agent_token
        self.session_id = session_id
        self.stt_provider_name = stt_provider or settings.stt_provider
        self.language = language

        self._room = None
        self._running = False
        self._audio_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._transcription_callback: Optional[TranscriptionCallback] = None
        self._tasks: list[asyncio.Task] = []

    def on_transcription(self, callback: TranscriptionCallback):
        """
        Register callback for transcription results.

        The callback receives TranscriptionResult objects with:
        - text: transcribed text
        - is_final: True when utterance is complete
        - confidence: 0.0 to 1.0

        The ConversationEngine registers here to process user speech.
        """
        self._transcription_callback = callback

    async def start(self):
        """
        Join the LiveKit room and start capturing audio.

        Connects to the room, subscribes to all audio tracks,
        and starts the STT processing pipeline.
        """
        from livekit import rtc

        self._running = True

        # Connect to LiveKit room
        self._room = rtc.Room()

        # Register track subscription handler
        @self._room.on("track_subscribed")
        def on_track_subscribed(
            track: rtc.Track,
            publication: rtc.RemoteTrackPublication,
            participant: rtc.RemoteParticipant,
        ):
            if track.kind == rtc.TrackKind.KIND_AUDIO:
                logger.info(
                    "Audio track subscribed",
                    participant=participant.identity,
                    session=self.session_id,
                )
                # Start capturing audio from this track
                task = asyncio.create_task(
                    self._capture_audio_track(track, participant.identity)
                )
                self._tasks.append(task)

        @self._room.on("participant_connected")
        def on_participant_connected(participant: rtc.RemoteParticipant):
            logger.info(
                "Participant connected",
                identity=participant.identity,
                session=self.session_id,
            )

        @self._room.on("disconnected")
        def on_disconnected():
            logger.info("Disconnected from LiveKit room", session=self.session_id)
            self._running = False

        # Connect to the room
        await self._room.connect(self.livekit_url, self.agent_token)

        logger.info(
            "LiveKit agent joined room",
            session=self.session_id,
            livekit_url=self.livekit_url[:50],
        )

        # Start STT processing pipeline
        stt_task = asyncio.create_task(self._stt_pipeline())
        self._tasks.append(stt_task)

    async def stop(self):
        """Leave the LiveKit room and stop all processing."""
        self._running = False

        # Cancel all tasks
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._tasks.clear()

        # Disconnect from room
        if self._room:
            await self._room.disconnect()
            self._room = None

        logger.info("LiveKit agent stopped", session=self.session_id)

    async def _capture_audio_track(
        self,
        track,
        participant_identity: str,
    ):
        """
        Capture audio frames from a LiveKit audio track.

        Converts LiveKit AudioFrame objects to raw PCM bytes
        and puts them in the processing queue.
        """
        from livekit import rtc

        audio_stream = rtc.AudioStream(track)

        try:
            async for event in audio_stream:
                if not self._running:
                    break

                frame = event.frame
                # LiveKit AudioFrame contains PCM data
                # Convert to bytes for STT processing
                pcm_data = frame.data.tobytes() if hasattr(frame.data, 'tobytes') else bytes(frame.data)

                await self._audio_queue.put(pcm_data)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(
                "Audio capture error",
                participant=participant_identity,
                error=str(e),
            )

    async def _stt_pipeline(self):
        """
        STT processing pipeline: reads audio queue → transcribes → callbacks.

        Runs as a background task for the duration of the session.
        """
        stt = STTProviderFactory.get_provider(self.stt_provider_name)

        logger.info(
            "STT pipeline started",
            provider=self.stt_provider_name,
            language=self.language,
            session=self.session_id,
        )

        try:
            # Create async audio stream from queue
            async def audio_stream():
                while self._running:
                    try:
                        chunk = await asyncio.wait_for(
                            self._audio_queue.get(), timeout=5.0
                        )
                        yield chunk
                    except asyncio.TimeoutError:
                        continue

            # Feed audio stream to STT
            async for result in stt.transcribe_stream(
                audio_stream(),
                sample_rate=24000,
                language=self.language,
            ):
                if result.text and self._transcription_callback:
                    logger.info(
                        "Transcription result",
                        text=result.text[:80],
                        is_final=result.is_final,
                        confidence=result.confidence,
                    )
                    await self._transcription_callback(result)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("STT pipeline error", error=str(e), session=self.session_id)

    @property
    def is_running(self) -> bool:
        return self._running
