"""
LiveKit Room and Token Management.

Handles:
- Generating access tokens for frontend clients to join LiveKit rooms
- Managing room lifecycle (for self-hosted LiveKit instances)
- Token generation for avatar participants
"""

from typing import Optional
from datetime import datetime
import structlog

from livekit.api import AccessToken, VideoGrants

from config import get_settings

logger = structlog.get_logger()
settings = get_settings()


class LiveKitManager:
    """Manages LiveKit rooms and access tokens."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        livekit_url: Optional[str] = None,
    ):
        self.api_key = api_key or settings.livekit_api_key
        self.api_secret = api_secret or settings.livekit_api_secret
        self.livekit_url = livekit_url or settings.livekit_url

    def generate_client_token(
        self,
        room_name: str,
        participant_name: str = "user",
        ttl: int = 3600,
    ) -> str:
        """
        Generate a LiveKit access token for a frontend client.

        This token allows the client to:
        - Join the specified room
        - Subscribe to audio/video tracks (avatar stream)
        - Publish audio (for voice input)

        Args:
            room_name: LiveKit room name (from HeyGen session)
            participant_name: Display name for the participant
            ttl: Token time-to-live in seconds
        """
        token = AccessToken(
            api_key=self.api_key,
            api_secret=self.api_secret,
        )
        token.with_identity(f"user-{participant_name}-{datetime.utcnow().timestamp():.0f}")
        token.with_name(participant_name)
        token.with_ttl(ttl)

        # Grant permissions
        grant = VideoGrants(
            room_join=True,
            room=room_name,
            can_subscribe=True,       # Can receive avatar video/audio
            can_publish=True,         # Can send audio (voice input)
            can_publish_data=True,    # Can send data messages
        )
        token.with_grants(grant)

        jwt_token = token.to_jwt()
        logger.info("Generated LiveKit client token",
                     room=room_name, participant=participant_name)
        return jwt_token

    def generate_agent_token(
        self,
        room_name: str,
        agent_name: str = "avatar-agent",
        ttl: int = 7200,
    ) -> str:
        """
        Generate a LiveKit token for the avatar agent participant.
        Used when running your own LiveKit instance and the avatar
        needs to join as a participant.
        """
        token = AccessToken(
            api_key=self.api_key,
            api_secret=self.api_secret,
        )
        token.with_identity(f"agent-{agent_name}")
        token.with_name(agent_name)
        token.with_ttl(ttl)

        grant = VideoGrants(
            room_join=True,
            room=room_name,
            can_subscribe=True,
            can_publish=True,
            can_publish_data=True,
            room_admin=True,
        )
        token.with_grants(grant)

        return token.to_jwt()

    def get_livekit_config_for_liveavatar(self, room_name: str) -> dict:
        """
        Generate LiveKit config to pass to LiveAvatar LITE API
        when using your own LiveKit instance.

        Returns a dict for the 'livekit_config' key in the
        POST /v1/sessions/token request.

        Format required by LiveAvatar LITE:
        {
            "url": "wss://your-livekit.cloud",
            "room": "room-name",
            "token": "agent-jwt-token"
        }
        """
        agent_token = self.generate_agent_token(room_name)

        return {
            "url": self.livekit_url,
            "room": room_name,
            "token": agent_token,
        }

    def generate_stt_agent_token(
        self,
        room_name: str,
        agent_name: str = "stt-agent",
        ttl: int = 7200,
    ) -> str:
        """
        Generate a LiveKit token for the STT agent.

        The STT agent joins the room to capture the user's audio
        and forward it to the speech-to-text pipeline.

        This is separate from the avatar agent token —
        the STT agent only subscribes to audio, it doesn't publish.
        """
        token = AccessToken(
            api_key=self.api_key,
            api_secret=self.api_secret,
        )
        token.with_identity(f"stt-agent-{agent_name}")
        token.with_name(agent_name)
        token.with_ttl(ttl)

        grant = VideoGrants(
            room_join=True,
            room=room_name,
            can_subscribe=True,       # Subscribe to user's audio
            can_publish=False,        # STT agent doesn't publish
            can_publish_data=True,    # May send transcription events
        )
        token.with_grants(grant)

        return token.to_jwt()
