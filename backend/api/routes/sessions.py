"""
Session API Routes — Manage LiveAvatar streaming sessions.

Endpoints:
- POST /          → Create a new avatar session
- POST /{id}/start → Start streaming
- POST /{id}/stop  → Stop session
- GET  /{id}       → Get session details
- POST /{id}/keep-alive → Reset idle timer
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from database import get_db
from models.tenant import Tenant
from models.session import AvatarSession, SessionStatus
from models.conversation import Conversation
from api.middleware.auth import get_current_tenant
from services.liveavatar_client import LiveAvatarClient, LiveAvatarError
from services.livekit_manager import LiveKitManager

router = APIRouter()


class CreateSessionRequest(BaseModel):
    avatar_id: Optional[str] = None  # Override tenant's default avatar
    voice_id: Optional[str] = None
    quality: str = "high"
    use_own_livekit: bool = False  # Use self-hosted LiveKit?


class SessionResponse(BaseModel):
    session_id: str
    heygen_session_id: Optional[str]
    status: str
    livekit_url: Optional[str]
    livekit_token: Optional[str]
    created_at: str


@router.post("/", response_model=SessionResponse)
async def create_session(
    request: CreateSessionRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Create a new LiveAvatar streaming session."""
    avatar_id = request.avatar_id or tenant.heygen_avatar_id
    if not avatar_id:
        raise HTTPException(
            status_code=400,
            detail="No avatar_id configured. Set it in tenant config or pass it in the request."
        )

    # Create DB session record
    db_session = AvatarSession(
        tenant_id=tenant.id,
        status=SessionStatus.CREATING,
    )
    db.add(db_session)
    await db.flush()

    # Create conversation for this session
    conversation = Conversation(session_id=db_session.id)
    db.add(conversation)

    # Call HeyGen LiveAvatar API
    liveavatar = LiveAvatarClient()
    livekit_mgr = LiveKitManager()

    try:
        # Optionally pass own LiveKit instance settings
        livekit_settings = None
        if request.use_own_livekit:
            room_name = f"avatar-{db_session.id}"
            livekit_settings = livekit_mgr.get_livekit_settings_for_heygen(room_name)

        heygen_session = await liveavatar.create_session(
            avatar_id=avatar_id,
            voice_id=request.voice_id or tenant.heygen_voice_id,
            quality=request.quality,
            livekit_settings=livekit_settings,
        )

        # Update DB session with HeyGen details
        db_session.heygen_session_id = heygen_session.session_id
        db_session.livekit_url = heygen_session.livekit_url
        db_session.livekit_token = heygen_session.livekit_client_token
        db_session.livekit_room_name = f"avatar-{db_session.id}"
        db_session.status = SessionStatus.ACTIVE
        db_session.started_at = datetime.utcnow()

    except LiveAvatarError as e:
        db_session.status = SessionStatus.ERROR
        raise HTTPException(status_code=502, detail=f"LiveAvatar error: {str(e)}")
    except Exception as e:
        db_session.status = SessionStatus.ERROR
        raise HTTPException(status_code=500, detail=f"Session creation failed: {str(e)}")
    finally:
        await liveavatar.close()

    return SessionResponse(
        session_id=db_session.id,
        heygen_session_id=db_session.heygen_session_id,
        status=db_session.status.value,
        livekit_url=db_session.livekit_url,
        livekit_token=db_session.livekit_token,
        created_at=db_session.created_at.isoformat(),
    )


@router.post("/{session_id}/start")
async def start_session(
    session_id: str,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Start streaming for a created session."""
    db_session = await _get_session(session_id, tenant.id, db)

    if not db_session.heygen_session_id:
        raise HTTPException(status_code=400, detail="Session has no HeyGen session ID")

    liveavatar = LiveAvatarClient()
    try:
        result = await liveavatar.start_session(db_session.heygen_session_id)
        db_session.status = SessionStatus.ACTIVE
        return {"status": "started", "data": result}
    finally:
        await liveavatar.close()


@router.post("/{session_id}/stop")
async def stop_session(
    session_id: str,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Stop and close a streaming session."""
    db_session = await _get_session(session_id, tenant.id, db)

    if db_session.heygen_session_id:
        liveavatar = LiveAvatarClient()
        try:
            await liveavatar.stop_session(db_session.heygen_session_id)
        except Exception:
            pass  # Session might already be closed
        finally:
            await liveavatar.close()

    db_session.status = SessionStatus.CLOSED
    db_session.ended_at = datetime.utcnow()
    if db_session.started_at:
        db_session.duration_seconds = int(
            (db_session.ended_at - db_session.started_at).total_seconds()
        )

    return {"status": "closed", "duration_seconds": db_session.duration_seconds}


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Get session details."""
    db_session = await _get_session(session_id, tenant.id, db)

    return SessionResponse(
        session_id=db_session.id,
        heygen_session_id=db_session.heygen_session_id,
        status=db_session.status.value,
        livekit_url=db_session.livekit_url,
        livekit_token=db_session.livekit_token,
        created_at=db_session.created_at.isoformat(),
    )


@router.post("/{session_id}/keep-alive")
async def keep_alive(
    session_id: str,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Reset the idle timer for an active session."""
    db_session = await _get_session(session_id, tenant.id, db)

    if not db_session.heygen_session_id:
        raise HTTPException(status_code=400, detail="No active HeyGen session")

    liveavatar = LiveAvatarClient()
    try:
        await liveavatar.keep_alive(db_session.heygen_session_id)
        return {"status": "alive"}
    finally:
        await liveavatar.close()


async def _get_session(
    session_id: str, tenant_id: str, db: AsyncSession
) -> AvatarSession:
    """Helper to fetch and validate a session belongs to the tenant."""
    result = await db.execute(
        select(AvatarSession).where(
            AvatarSession.id == session_id,
            AvatarSession.tenant_id == tenant_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session
