"""
LiveAvatar LITE Mode WebSocket Manager.

Manages the persistent WebSocket connection to LiveAvatar
for sending audio commands and receiving avatar state events.

LITE Mode Command Events (we send):
- agent.speak         → PCM 16Bit 24KHz audio (Base64) for lip-sync
- agent.speak_end     → Signal: finished speaking
- agent.interrupt     → Interrupt current avatar speech
- agent.start_listening → Put avatar in "listening" animation
- agent.stop_listening  → Put avatar in "idle" animation
- session.keep_alive  → Keep session alive

Server Events (we receive):
- session.state_updated   → connected/connecting/closed/closing
- agent.speak_started     → Avatar started speaking (lip-sync active)
- agent.speak_ended       → Avatar finished speaking

Connection: WebSocket to ws_url from session token response.
Auth: session_token as query parameter or in connect message.
"""

from typing import Optional, Callable, Awaitable
import asyncio
import base64
import json
import structlog
import websockets
from websockets.exceptions import ConnectionClosed

logger = structlog.get_logger()

# Type alias for event callbacks
EventCallback = Callable[[dict], Awaitable[None]]


class LiveAvatarWSManager:
    """
    WebSocket manager for LiveAvatar LITE Mode command events.

    Maintains a persistent connection to the LiveAvatar WebSocket
    and provides methods for each command event type.
    """

    def __init__(
        self,
        ws_url: str,
        session_token: str,
        session_id: str,
    ):
        self.ws_url = ws_url
        self.session_token = session_token
        self.session_id = session_id

        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._connected = False
        self._receive_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None

        # Event callbacks
        self._callbacks: dict[str, list[EventCallback]] = {}

        # State
        self.avatar_speaking = False
        self.session_state = "disconnected"

    # --- Connection Management ---

    async def connect(self, auto_heartbeat: bool = True):
        """
        Establish WebSocket connection to LiveAvatar.

        Args:
            auto_heartbeat: Start automatic keep-alive every 30s
        """
        try:
            # Build connection URL with auth
            url = self.ws_url
            if "?" in url:
                url += f"&session_token={self.session_token}"
            else:
                url += f"?session_token={self.session_token}"

            self._ws = await websockets.connect(
                url,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=5,
            )
            self._connected = True
            self.session_state = "connecting"

            logger.info(
                "LiveAvatar WebSocket connected (waiting for session.state_updated=connected)",
                session_id=self.session_id,
            )

            # Start receiving events in background
            self._receive_task = asyncio.create_task(self._receive_loop())

            # Wait for server to confirm "connected" state (required before sending events)
            for _ in range(50):  # up to 5 seconds
                if self.session_state == "connected":
                    break
                await asyncio.sleep(0.1)

            if self.session_state != "connected":
                logger.warning(
                    "Session state not 'connected' after 5s, proceeding anyway",
                    state=self.session_state,
                    session_id=self.session_id,
                )
            else:
                logger.info(
                    "LiveAvatar session confirmed connected",
                    session_id=self.session_id,
                )

            # Start heartbeat
            if auto_heartbeat:
                self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        except Exception as e:
            self._connected = False
            self.session_state = "error"
            logger.error("WebSocket connect failed", error=str(e))
            raise

    async def disconnect(self):
        """Gracefully close the WebSocket connection."""
        self._connected = False

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass

        if self._ws:
            await self._ws.close()
            self._ws = None

        self.session_state = "disconnected"
        logger.info("LiveAvatar WebSocket disconnected", session_id=self.session_id)

    @property
    def is_connected(self) -> bool:
        return self._connected and self._ws is not None

    # --- Command Events (we send) ---

    async def send_speak(self, audio_base64: str):
        """
        Send audio data to avatar for lip-sync speech.

        This is the core LITE Mode command — sends PCM 16Bit 24KHz
        audio (Base64-encoded) to the avatar for real-time lip-sync.

        Args:
            audio_base64: Base64-encoded PCM 16Bit 24KHz audio chunk
        """
        await self._send_event("agent.speak", {
            "audio": audio_base64,
        })

    async def send_speak_from_bytes(self, audio_bytes: bytes):
        """
        Convenience method: encode PCM bytes and send to avatar.

        Args:
            audio_bytes: Raw PCM 16Bit 24KHz audio bytes
        """
        audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
        await self.send_speak(audio_b64)

    async def send_speak_end(self):
        """
        Signal that we've finished sending audio.

        The avatar will complete the current lip-sync animation
        and return to idle state.
        """
        await self._send_event("agent.speak_end", {})
        logger.debug("Sent speak_end", session_id=self.session_id)

    async def send_interrupt(self):
        """
        Interrupt the avatar's current speech.

        Use when the user starts talking while the avatar is speaking,
        or when navigating away.
        """
        await self._send_event("agent.interrupt", {})
        logger.info("Sent interrupt", session_id=self.session_id)

    async def send_start_listening(self):
        """
        Put avatar in "listening" animation state.

        Shows the user that the system is processing their voice input.
        """
        await self._send_event("agent.start_listening", {})
        logger.debug("Avatar → listening state")

    async def send_stop_listening(self):
        """
        Put avatar in "idle" animation state.

        The avatar returns to a neutral, ambient animation.
        """
        await self._send_event("agent.stop_listening", {})
        logger.debug("Avatar → idle state")

    async def send_keep_alive(self):
        """
        Reset the session idle timer via WebSocket.

        Alternative to REST keep_alive endpoint.
        """
        await self._send_event("session.keep_alive", {})
        logger.debug("WebSocket keep_alive sent")

    # --- Event Callbacks ---

    def on(self, event_type: str, callback: EventCallback):
        """
        Register a callback for a specific event type.

        Args:
            event_type: "session.state_updated", "agent.speak_started", etc.
            callback: Async function receiving the event data dict
        """
        if event_type not in self._callbacks:
            self._callbacks[event_type] = []
        self._callbacks[event_type].append(callback)

    # --- Internal Methods ---

    async def _send_event(self, event_type: str, data: dict):
        """Send a command event via WebSocket."""
        if not self.is_connected:
            raise RuntimeError("WebSocket not connected")

        # LITE Mode event format: {"type": "event.name", ...data}
        # session_id is not needed — the WebSocket connection is already scoped to the session
        message = json.dumps({
            "type": event_type,
            **data,
        })

        try:
            await self._ws.send(message)
        except ConnectionClosed:
            self._connected = False
            self.session_state = "disconnected"
            logger.error("WebSocket closed while sending", event_type=event_type)
            raise

    async def _receive_loop(self):
        """Background task: receive and dispatch server events."""
        try:
            while self._connected and self._ws:
                try:
                    raw = await asyncio.wait_for(self._ws.recv(), timeout=60)
                    event = json.loads(raw)
                    event_type = event.get("type", "unknown")

                    # Update internal state
                    if event_type == "session.state_updated":
                        self.session_state = event.get("state", "unknown")
                        logger.info("Session state updated", state=self.session_state)

                    elif event_type == "agent.speak_started":
                        self.avatar_speaking = True
                        logger.debug("Avatar started speaking")

                    elif event_type == "agent.speak_ended":
                        self.avatar_speaking = False
                        logger.debug("Avatar finished speaking")

                    # Dispatch to registered callbacks
                    if event_type in self._callbacks:
                        for callback in self._callbacks[event_type]:
                            try:
                                await callback(event)
                            except Exception as e:
                                logger.error(
                                    "Callback error",
                                    event_type=event_type,
                                    error=str(e),
                                )

                except asyncio.TimeoutError:
                    # No message in 60s — connection still alive (ping/pong handles it)
                    continue

        except ConnectionClosed as e:
            self._connected = False
            self.session_state = "disconnected"
            logger.info("WebSocket connection closed", code=e.code, reason=e.reason)

        except asyncio.CancelledError:
            pass

        except Exception as e:
            self._connected = False
            self.session_state = "error"
            logger.error("Receive loop error", error=str(e))

    async def _heartbeat_loop(self, interval: int = 30):
        """Background task: send periodic keep-alive messages."""
        try:
            while self._connected:
                await asyncio.sleep(interval)
                if self.is_connected:
                    try:
                        await self.send_keep_alive()
                    except Exception:
                        pass
        except asyncio.CancelledError:
            pass
