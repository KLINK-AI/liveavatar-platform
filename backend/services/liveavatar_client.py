"""
HeyGen LiveAvatar API Client — SDK-frei, direkte REST API Nutzung.

Kommuniziert direkt mit der HeyGen Streaming API über HTTP,
ohne das komplexe HeyGen SDK. Nutzt LiveKit für WebRTC Streaming.

Endpoints:
- POST /v1/streaming.new    → Session erstellen
- POST /v1/streaming.start  → Stream starten
- POST /v1/streaming.task   → Text an Avatar senden (Lip-Sync)
- POST /v1/streaming.stop   → Session beenden
- POST /v1/streaming.keep_alive → Idle-Timer zurücksetzen
"""

from dataclasses import dataclass
from typing import Optional
import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from config import get_settings

logger = structlog.get_logger()
settings = get_settings()


@dataclass
class LiveAvatarSession:
    """Represents an active LiveAvatar streaming session."""
    session_id: str
    livekit_url: str
    livekit_client_token: str
    livekit_agent_token: Optional[str] = None
    max_session_duration: Optional[int] = None
    ws_url: Optional[str] = None


class LiveAvatarClient:
    """
    Direct REST API client for HeyGen LiveAvatar.
    No SDK dependency — communicates via httpx.
    """

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or settings.heygen_api_key
        self.base_url = (base_url or settings.liveavatar_api_base).rstrip("/")
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "x-api-key": self.api_key,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                timeout=30.0,
            )
        return self._client

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def create_session(
        self,
        avatar_id: str,
        voice_id: Optional[str] = None,
        quality: str = "high",
        activity_idle_timeout: int = 300,
        livekit_settings: Optional[dict] = None,
    ) -> LiveAvatarSession:
        """
        Create a new LiveAvatar streaming session in Custom Mode.

        Custom Mode means WE control the LLM — HeyGen only provides
        the avatar rendering and lip-sync.

        Args:
            avatar_id: HeyGen avatar ID from your account
            voice_id: Optional voice ID (if using HeyGen TTS)
            quality: Video quality ("low", "medium", "high")
            activity_idle_timeout: Seconds before auto-close (30-3599)
            livekit_settings: Optional custom LiveKit instance config
        """
        client = await self._get_client()

        payload = {
            "version": "v2",
            "avatar_id": avatar_id,
            "quality": quality,
            "activity_idle_timeout": max(30, min(activity_idle_timeout, 3599)),
            # Custom mode: we handle LLM ourselves, HeyGen only does avatar
            "voice": {},
        }

        if voice_id:
            payload["voice"] = {"voice_id": voice_id}

        # Optional: use your own LiveKit instance instead of HeyGen's
        if livekit_settings:
            payload["livekit_settings"] = livekit_settings

        logger.info("Creating LiveAvatar session", avatar_id=avatar_id, quality=quality)

        response = await client.post("/v1/streaming.new", json=payload)
        response.raise_for_status()
        data = response.json()

        if data.get("code") != 100 and data.get("error"):
            raise LiveAvatarError(f"Failed to create session: {data.get('message', 'Unknown error')}")

        session_data = data.get("data", {})

        session = LiveAvatarSession(
            session_id=session_data["session_id"],
            livekit_url=session_data.get("url", session_data.get("livekit_url", "")),
            livekit_client_token=session_data.get("access_token", session_data.get("livekit_client_token", "")),
            livekit_agent_token=session_data.get("livekit_agent_token"),
            max_session_duration=session_data.get("max_session_duration"),
            ws_url=session_data.get("ws_url"),
        )

        logger.info("LiveAvatar session created",
                     session_id=session.session_id,
                     livekit_url=session.livekit_url)
        return session

    async def start_session(self, session_id: str) -> dict:
        """
        Start streaming for a created session.
        Must be called after create_session.
        """
        client = await self._get_client()

        response = await client.post("/v1/streaming.start", json={
            "session_id": session_id,
        })
        response.raise_for_status()
        data = response.json()

        logger.info("LiveAvatar session started", session_id=session_id)
        return data.get("data", {})

    async def send_text(
        self,
        session_id: str,
        text: str,
        task_type: str = "talk",
    ) -> dict:
        """
        Send text to the avatar for lip-synced speech.

        This is the core method — after our LLM generates an answer,
        we send it here and the avatar speaks it.

        Args:
            session_id: Active session ID
            text: Text for the avatar to speak
            task_type: "talk" (default) or "repeat"
        """
        client = await self._get_client()

        response = await client.post("/v1/streaming.task", json={
            "session_id": session_id,
            "text": text,
            "task_type": task_type,
        })
        response.raise_for_status()
        data = response.json()

        logger.info("Text sent to avatar",
                     session_id=session_id,
                     text_length=len(text),
                     task_type=task_type)
        return data.get("data", {})

    async def send_text_streaming(
        self,
        session_id: str,
        text: str,
    ) -> dict:
        """
        Send text in streaming mode — for sentence-by-sentence delivery.
        Splits long text into sentences and sends them sequentially
        for more natural avatar speech.
        """
        sentences = self._split_into_sentences(text)
        results = []

        for sentence in sentences:
            if sentence.strip():
                result = await self.send_text(session_id, sentence.strip())
                results.append(result)

        return {"sentences_sent": len(results), "results": results}

    async def keep_alive(self, session_id: str) -> dict:
        """Reset the idle timer for a session."""
        client = await self._get_client()

        response = await client.post("/v1/streaming.keep_alive", json={
            "session_id": session_id,
        })
        response.raise_for_status()

        logger.debug("Keep-alive sent", session_id=session_id)
        return response.json().get("data", {})

    async def stop_session(self, session_id: str) -> dict:
        """Stop and close a streaming session."""
        client = await self._get_client()

        response = await client.post("/v1/streaming.stop", json={
            "session_id": session_id,
        })
        response.raise_for_status()

        logger.info("LiveAvatar session stopped", session_id=session_id)
        return response.json().get("data", {})

    async def list_avatars(self) -> list[dict]:
        """List available avatars from HeyGen account."""
        client = await self._get_client()

        response = await client.get("/v1/streaming.list")
        response.raise_for_status()
        data = response.json()

        return data.get("data", {}).get("avatars", [])

    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    @staticmethod
    def _split_into_sentences(text: str) -> list[str]:
        """Split text into sentences for natural streaming delivery."""
        import re
        # Split on sentence-ending punctuation, keeping the delimiter
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s for s in sentences if s.strip()]


class LiveAvatarError(Exception):
    """Custom exception for LiveAvatar API errors."""
    pass
