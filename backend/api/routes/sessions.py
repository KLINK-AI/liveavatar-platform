"""
Session API Routes — Manage LiveAvatar LITE Mode streaming sessions.

Endpoints:
- POST /          → Create a new avatar session (Token + Start)
- POST /{id}/start → Start streaming for a created session
- POST /{id}/stop  → Stop session + disconnect WebSocket
- GET  /{id}       → Get session details
- POST /{id}/keep-alive → Reset idle timer

LITE Mode Session Flow:
1. POST / → creates session token via LiveAvatar API, connects WebSocket
2. POST /{id}/start → starts avatar streaming
3. Messages flow via ConversationEngine → TTS → WebSocket → Avatar
4. POST /{id}/stop → stops avatar, disconnects WebSocket
"""

import asyncio
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import structlog

from database import get_db
from models.tenant import Tenant
from models.session import AvatarSession, SessionStatus
from models.conversation import Conversation
from api.middleware.auth import get_current_tenant
from services.liveavatar_client import LiveAvatarClient, LiveAvatarError
from services.liveavatar_ws import LiveAvatarWSManager
from services.livekit_manager import LiveKitManager
from services.livekit_agent import LiveKitAgentService
from services.conversation.engine import ConversationEngine

logger = structlog.get_logger()
router = APIRouter()

# Active WebSocket managers and LiveKit agents per session
_ws_managers: dict[str, LiveAvatarWSManager] = {}
_livekit_agents: dict[str, LiveKitAgentService] = {}

# Shared conversation engine
_engine: Optional[ConversationEngine] = None


def get_engine() -> ConversationEngine:
    global _engine
    if _engine is None:
        _engine = ConversationEngine()
    return _engine


class CreateSessionRequest(BaseModel):
    avatar_id: Optional[str] = None
    voice_id: Optional[str] = None
    use_own_livekit: bool = False
    is_sandbox: bool = False
    language: str = "de"


class SessionResponse(BaseModel):
    session_id: str
    liveavatar_session_id: Optional[str]
    status: str
    livekit_url: Optional[str]
    livekit_token: Optional[str]
    ws_status: Optional[str]
    created_at: str


@router.post("/", response_model=SessionResponse)
async def create_session(
    request: CreateSessionRequest,
    background_tasks: BackgroundTasks,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new LiveAvatar LITE Mode streaming session.

    Flow:
    1. Create session token via LiveAvatar REST API
    2. Connect WebSocket for audio command events
    3. Register WS manager in ConversationEngine
    4. Start LiveKit agent for STT (background)
    """
    avatar_id = request.avatar_id or tenant.liveavatar_avatar_id
    if not avatar_id:
        raise HTTPException(
            status_code=400,
            detail="No avatar_id configured. Set liveavatar_avatar_id on tenant or pass avatar_id in request."
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

    # Step 1: Get session token from LiveAvatar API
    liveavatar = LiveAvatarClient()
    livekit_mgr = LiveKitManager()

    try:
        # Optionally use own LiveKit instance
        livekit_config = None
        if request.use_own_livekit:
            room_name = f"avatar-{db_session.id}"
            livekit_config = livekit_mgr.get_livekit_config_for_liveavatar(room_name)

        la_session = await liveavatar.create_session_token(
            avatar_id=avatar_id,
            voice_id=request.voice_id or tenant.liveavatar_voice_id,
            is_sandbox=request.is_sandbox,
            livekit_config=livekit_config,
        )

        # Update DB session with LiveAvatar details
        db_session.liveavatar_session_id = la_session.session_id
        db_session.liveavatar_session_token = la_session.session_token
        db_session.ws_url = la_session.ws_url
        db_session.livekit_url = la_session.livekit_url
        db_session.livekit_token = la_session.livekit_client_token
        db_session.livekit_room_name = f"avatar-{db_session.id}"
        db_session.status = SessionStatus.CREATING
        db_session.ws_status = "connecting"

        # Step 2: Connect WebSocket for LITE Mode commands (background)
        if la_session.ws_url and la_session.session_token:
            background_tasks.add_task(
                _setup_session_services,
                session_id=db_session.id,
                la_session_id=la_session.session_id,
                ws_url=la_session.ws_url,
                session_token=la_session.session_token,
                livekit_url=la_session.livekit_url or livekit_mgr.livekit_url,
                livekit_agent_token=(
                    la_session.livekit_agent_token
                    or livekit_mgr.generate_stt_agent_token(f"avatar-{db_session.id}")
                ),
                stt_provider=tenant.stt_provider,
                language=request.language,
            )

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
        liveavatar_session_id=db_session.liveavatar_session_id,
        status=db_session.status.value,
        livekit_url=db_session.livekit_url,
        livekit_token=db_session.livekit_token,
        ws_status=db_session.ws_status,
        created_at=db_session.created_at.isoformat(),
    )


@router.post("/{session_id}/start")
async def start_session(
    session_id: str,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    Start streaming for a created session.

    Calls LiveAvatar API to begin avatar rendering in the LiveKit room.
    """
    db_session = await _get_session(session_id, tenant.id, db)

    if not db_session.liveavatar_session_id:
        raise HTTPException(status_code=400, detail="Session has no LiveAvatar session ID")

    liveavatar = LiveAvatarClient()
    try:
        result = await liveavatar.start_session(db_session.liveavatar_session_id)
        db_session.status = SessionStatus.ACTIVE
        db_session.started_at = datetime.utcnow()
        return {"status": "started", "data": result}
    finally:
        await liveavatar.close()


@router.post("/{session_id}/stop")
async def stop_session(
    session_id: str,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    Stop and close a streaming session.

    Cleans up: LiveAvatar session, WebSocket, LiveKit agent.
    """
    db_session = await _get_session(session_id, tenant.id, db)

    # Stop LiveAvatar session
    if db_session.liveavatar_session_id:
        liveavatar = LiveAvatarClient()
        try:
            await liveavatar.stop_session(db_session.liveavatar_session_id)
        except Exception:
            pass
        finally:
            await liveavatar.close()

    # Disconnect WebSocket
    ws_manager = _ws_managers.pop(session_id, None)
    if ws_manager:
        await ws_manager.disconnect()

    # Stop LiveKit agent
    agent = _livekit_agents.pop(session_id, None)
    if agent:
        await agent.stop()

    # Unregister from conversation engine
    engine = get_engine()
    engine.unregister_ws_manager(session_id)

    # Update DB
    db_session.status = SessionStatus.CLOSED
    db_session.ws_status = "disconnected"
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
        liveavatar_session_id=db_session.liveavatar_session_id,
        status=db_session.status.value,
        livekit_url=db_session.livekit_url,
        livekit_token=db_session.livekit_token,
        ws_status=db_session.ws_status,
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

    if not db_session.liveavatar_session_id:
        raise HTTPException(status_code=400, detail="No active LiveAvatar session")

    liveavatar = LiveAvatarClient()
    try:
        await liveavatar.keep_alive(db_session.liveavatar_session_id)
        return {"status": "alive"}
    finally:
        await liveavatar.close()


# --- Background Setup ---

async def _setup_session_services(
    session_id: str,
    la_session_id: str,
    ws_url: str,
    session_token: str,
    livekit_url: str,
    livekit_agent_token: str,
    stt_provider: Optional[str] = None,
    language: str = "de",
):
    """
    Background task: connect WebSocket + start LiveKit agent.

    Called after session token is created. Sets up:
    1. WebSocket connection to LiveAvatar for audio commands
    2. LiveKit agent for capturing user audio → STT
    """
    try:
        # 1. Connect WebSocket to LiveAvatar
        ws_manager = LiveAvatarWSManager(
            ws_url=ws_url,
            session_token=session_token,
            session_id=la_session_id,
        )
        await ws_manager.connect()
        _ws_managers[session_id] = ws_manager

        # Register in conversation engine
        engine = get_engine()
        engine.register_ws_manager(session_id, ws_manager)

        logger.info("WebSocket connected for session", session_id=session_id)

        # 2. Start LiveKit agent for STT
        agent = LiveKitAgentService(
            livekit_url=livekit_url,
            agent_token=livekit_agent_token,
            session_id=session_id,
            stt_provider=stt_provider,
            language=language,
        )

        # Register transcription callback → feeds into conversation engine
        async def on_transcription(result):
            if result.is_final and result.text:
                logger.info(
                    "User speech transcribed",
                    text=result.text[:80],
                    session=session_id,
                )
                # TODO: Auto-process transcribed speech through ConversationEngine
                # This enables fully voice-driven conversation without REST calls

        agent.on_transcription(on_transcription)
        await agent.start()
        _livekit_agents[session_id] = agent

        logger.info("LiveKit STT agent started for session", session_id=session_id)

    except Exception as e:
        logger.error(
            "Failed to setup session services",
            session_id=session_id,
            error=str(e),
        )


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
