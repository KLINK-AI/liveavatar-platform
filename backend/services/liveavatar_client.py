"""
LiveAvatar LITE Mode API Client — REST Endpoints.

Communicates with the new LiveAvatar API (api.liveavatar.com)
for session management and avatar control.

LITE Mode means WE control everything:
- ASR (Speech-to-Text)    → Deepgram / OpenAI Whisper
- LLM (Text Generation)   → OpenAI / Anthropic / Ollama
- TTS (Text-to-Speech)    → ElevenLabs
- Avatar Rendering         → LiveAvatar (lip-sync from our audio)
- Video Transport          → LiveKit WebRTC

REST Endpoints (api.liveavatar.com):
- POST /v1/sessions/token      → Get session token (mode: LITE)
- POST /v1/sessions/start      → Start streaming
- POST /v1/sessions/stop       → Stop session
- POST /v1/sessions/keep_alive → Reset idle timer
- GET  /v1/avatars/public      → List public avatars
- GET  /v1/avatars             → List own avatars

Auth: X-API-KEY header
"""

from dataclasses import dataclass, field
from typing import Optional
import time
import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log
import logging

from config import get_settings

logger = structlog.get_logger()
settings = get_settings()


@dataclass
class LiveAvatarSession:
    """Result from Create Session Token — only session_id + session_token."""

    session_id: str
    session_token: str
    is_sandbox: bool = False


@dataclass
class LiveAvatarStartResult:
    """Result from Start Session — contains LiveKit connection details."""

    session_id: str
    livekit_url: Optional[str] = None
    livekit_client_token: Optional[str] = None
    livekit_agent_token: Optional[str] = None
    max_session_duration: Optional[int] = None
    ws_url: Optional[str] = None


class LiveAvatarClient:
    """
    REST API client for LiveAvatar LITE Mode.

    Handles session lifecycle: token → start → keep_alive → stop.
    Audio delivery happens via WebSocket (see liveavatar_ws.py).
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.api_key = api_key or settings.liveavatar_api_key
        self.base_url = (base_url or settings.liveavatar_api_base).rstrip("/")
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with auth headers.

        IMPORTANT: http1=True, http2=False is required because the LiveAvatar API
        (behind Cloudflare) hangs on HTTP/2 POST requests from server environments.
        Diagnosed 2026-03-16: httpx HTTP/2 causes ReadTimeout, requests (HTTP/1.1) works.
        Timeout raised to 60s because the API routinely takes 20-30s to respond.
        """
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "X-API-KEY": self.api_key,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                timeout=60.0,
                http1=True,
                http2=False,
            )
        return self._client

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=8),
        before_sleep=before_sleep_log(logging.getLogger("liveavatar"), logging.WARNING),
    )
    async def create_session_token(
        self,
        avatar_id: str,
        voice_id: Optional[str] = None,
        is_sandbox: bool = False,
        livekit_config: Optional[dict] = None,
    ) -> LiveAvatarSession:
        """
        Step 1: Create a session token for LITE Mode.

        In LITE Mode, LiveAvatar only renders the avatar video.
        We handle ASR, LLM, and TTS ourselves and send audio
        via WebSocket `agent.speak` command.

        Args:
            avatar_id: LiveAvatar avatar ID
            voice_id: Optional voice ID (only used if LiveAvatar handles TTS)
            is_sandbox: True for testing without consuming credits
            livekit_config: Custom LiveKit instance settings:
                {
                    "url": "wss://your-livekit.cloud",
                    "room": "room-name",
                    "token": "agent-token"
                }

        Returns:
            LiveAvatarSession with session_id, token, and ws_url
        """
        client = await self._get_client()

        payload = {
            "mode": "LITE",
            "avatar_id": avatar_id,
            "is_sandbox": is_sandbox,
        }

        # Voice config (optional — in LITE mode we usually do our own TTS)
        if voice_id:
            payload["voice"] = {"voice_id": voice_id}

        # Custom LiveKit instance (instead of LiveAvatar's built-in)
        if livekit_config:
            payload["livekit_config"] = livekit_config

        logger.info(
            "Creating LiveAvatar LITE session token",
            avatar_id=avatar_id,
            is_sandbox=is_sandbox,
            custom_livekit=bool(livekit_config),
        )

        t0 = time.monotonic()
        response = await client.post("/v1/sessions/token", json=payload)
        t1 = time.monotonic()
        logger.info("create_session_token HTTP — TIMING", elapsed_ms=round((t1 - t0) * 1000))

        # Log response body before raising, for debugging 500 errors
        if response.status_code >= 400:
            logger.warning(
                "create_session_token non-2xx response",
                status_code=response.status_code,
                body=response.text[:500],
            )
        response.raise_for_status()
        data = response.json()

        # Handle API error responses
        if data.get("error"):
            raise LiveAvatarError(
                f"Failed to create session token: {data.get('message', data.get('error', 'Unknown'))}"
            )

        session_data = data.get("data", data)

        session = LiveAvatarSession(
            session_id=session_data["session_id"],
            session_token=session_data.get("session_token", session_data.get("token", "")),
            is_sandbox=is_sandbox,
        )

        logger.info(
            "LiveAvatar LITE session token created",
            session_id=session.session_id,
            has_token=bool(session.session_token),
        )

        return session

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=8),
        before_sleep=before_sleep_log(logging.getLogger("liveavatar"), logging.WARNING),
    )
    async def start_session(self, session_token: str) -> LiveAvatarStartResult:
        """
        Step 2: Start the avatar streaming session.

        Must be called after create_session_token.
        Uses the session_token as Bearer auth.
        Returns LiveKit connection details for frontend + agent.

        NOTE: Retry added because LiveAvatar API intermittently returns 500.
        Timeout reduced to 35s (API usually responds in 20-30s, 60s was too long for UX).
        Max 2 attempts → worst case ~75s instead of ~186s.

        Args:
            session_token: Session token from create_session_token

        Returns:
            LiveAvatarStartResult with livekit_url, livekit_client_token, ws_url etc.
        """
        # Start Session uses Bearer token auth (the session_token), not X-API-KEY
        logger.info("start_session — attempting API call")
        t0 = time.monotonic()
        async with httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {session_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=35.0,
            http1=True,
            http2=False,
        ) as client:
            response = await client.post("/v1/sessions/start")
            # Log response body before raising, for debugging 500 errors
            if response.status_code >= 400:
                logger.warning(
                    "start_session non-2xx response",
                    status_code=response.status_code,
                    body=response.text[:500],
                )
            response.raise_for_status()
            data = response.json()
        t1 = time.monotonic()

        logger.info("start_session HTTP — TIMING", elapsed_ms=round((t1 - t0) * 1000))

        # === DIAGNOSTIC: Log the FULL raw response to understand API structure ===
        import json as _json
        logger.info(
            "start_session FULL RAW RESPONSE",
            raw_json=_json.dumps(data, default=str)[:2000],
        )

        session_data = data.get("data", data)
        logger.info(
            "start_session parsed session_data",
            session_data_keys=list(session_data.keys()) if isinstance(session_data, dict) else "not-dict",
            session_data_preview=_json.dumps(session_data, default=str)[:1000],
        )

        # Only raise on explicit error — code 100 is success per docs,
        # but we also accept any HTTP 2xx as success
        if data.get("error"):
            raise LiveAvatarError(
                f"Failed to start session: {data.get('message', data.get('error', 'Unknown'))}"
            )

        result = LiveAvatarStartResult(
            session_id=session_data.get("session_id", ""),
            livekit_url=session_data.get("livekit_url"),
            livekit_client_token=session_data.get("livekit_client_token"),
            livekit_agent_token=session_data.get("livekit_agent_token"),
            max_session_duration=session_data.get("max_session_duration"),
            ws_url=session_data.get("ws_url"),
        )

        logger.info(
            "LiveAvatar session started — RESULT",
            session_id=result.session_id,
            livekit_url=result.livekit_url[:80] if result.livekit_url else "NONE",
            ws_url=result.ws_url[:80] if result.ws_url else "NONE",
            has_client_token=bool(result.livekit_client_token),
            has_agent_token=bool(result.livekit_agent_token),
            max_duration=result.max_session_duration,
        )

        return result

    async def stop_session(self, session_token: str) -> dict:
        """
        Stop and close a streaming session.

        Releases all resources. The avatar disappears from LiveKit.

        Args:
            session_token: Session token (used as Bearer auth)
        """
        async with httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {session_token}",
                "Accept": "application/json",
            },
            timeout=30.0,
            http1=True,
            http2=False,
        ) as client:
            response = await client.post("/v1/sessions/stop")
            response.raise_for_status()

        logger.info("LiveAvatar session stopped")
        return response.json().get("data", {})

    async def keep_alive(self, session_token: str) -> dict:
        """
        Reset the idle timer for a session.

        Must be called periodically to prevent auto-close.
        Default timeout is ~300 seconds.

        Args:
            session_token: Session token (used as Bearer auth)
        """
        async with httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {session_token}",
                "Accept": "application/json",
            },
            timeout=30.0,
            http1=True,
            http2=False,
        ) as client:
            response = await client.post("/v1/sessions/keep_alive")
            response.raise_for_status()

        logger.debug("Keep-alive sent")
        return response.json().get("data", {})

    async def list_public_avatars(self) -> list[dict]:
        """
        List publicly available avatars.

        Returns:
            List of avatar dicts with id, name, preview_url
        """
        client = await self._get_client()

        response = await client.get("/v1/avatars/public")
        response.raise_for_status()
        data = response.json()

        avatars = data.get("data", {}).get("avatars", data.get("avatars", []))
        logger.info("Listed public avatars", count=len(avatars))
        return avatars

    async def list_own_avatars(self) -> list[dict]:
        """
        List avatars from your LiveAvatar account.

        Returns:
            List of avatar dicts with id, name, preview_url
        """
        client = await self._get_client()

        response = await client.get("/v1/avatars")
        response.raise_for_status()
        data = response.json()

        avatars = data.get("data", {}).get("avatars", data.get("avatars", []))
        logger.info("Listed own avatars", count=len(avatars))
        return avatars

    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()


class LiveAvatarError(Exception):
    """Custom exception for LiveAvatar API errors."""
    pass
