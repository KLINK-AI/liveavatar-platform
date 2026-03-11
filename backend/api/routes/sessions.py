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
import time
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
from services.liveavatar_client import LiveAvatarClient, LiveAvatarError, LiveAvatarStartResult
from services.liveavatar_ws import LiveAvatarWSManager
from services.livekit_manager import LiveKitManager
from services.engine_instance import get_engine

logger = structlog.get_logger()
router = APIRouter()

# Active WebSocket managers and LiveKit agents per session
_ws_managers: dict[str, LiveAvatarWSManager] = {}
_livekit_agents: dict[str, object] = {}  # LiveKitAgentService if available


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
    engine = get_engine()
    t_api_start = time.monotonic()

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
        t_token = time.monotonic()

        # Store token info in DB
        db_session.liveavatar_session_id = la_session.session_id
        db_session.liveavatar_session_token = la_session.session_token
        db_session.livekit_room_name = f"avatar-{db_session.id}"
        db_session.status = SessionStatus.CREATING

        # OPTIMIZATION: Resolve greeting text NOW and start TTS pre-generation
        # PARALLEL with start_session() — so TTS runs during the ~2.8s REST call
        greeting_text = ""
        lang = request.language
        if lang == tenant.default_language:
            greeting_text = tenant.greeting_text or ""
        elif tenant.greeting_translations:
            greeting_text = tenant.greeting_translations.get(lang, "")
        if not greeting_text:
            greeting_text = tenant.greeting_text or ""

        # Fire-and-forget TTS pre-generation (runs during start_session REST call)
        tts_task = None
        if greeting_text:
            tts_task = asyncio.create_task(
                engine.pre_generate_greeting_audio(
                    tenant=tenant,
                    greeting_text=greeting_text,
                    language=lang,
                )
            )

        # Step 2: Start session → returns LiveKit URL + tokens
        # TTS pre-generation runs IN PARALLEL with this REST call
        start_result = await liveavatar.start_session(la_session.session_token)
        t_start = time.monotonic()

        # Update DB with LiveKit connection details from Start Session response
        db_session.livekit_url = start_result.livekit_url or ""
        db_session.livekit_token = start_result.livekit_client_token or ""
        db_session.ws_url = start_result.ws_url or ""
        db_session.status = SessionStatus.ACTIVE
        db_session.ws_status = "connecting"

        logger.info(
            "Session created and started — TIMING",
            session_id=db_session.id,
            la_session_id=la_session.session_id,
            create_token_ms=round((t_token - t_api_start) * 1000),
            start_session_ms=round((t_start - t_token) * 1000),
            total_api_ms=round((t_start - t_api_start) * 1000),
            livekit_url=db_session.livekit_url[:50] if db_session.livekit_url else "none",
            has_client_token=bool(db_session.livekit_token),
            has_ws_url=bool(db_session.ws_url),
            tts_prestarted=bool(tts_task),
        )

        # Step 3: Connect WebSocket + send greeting + start STT agent (background)
        if start_result.ws_url and la_session.session_token:
            background_tasks.add_task(
                _setup_session_services,
                session_id=db_session.id,
                la_session_id=la_session.session_id,
                ws_url=start_result.ws_url,
                session_token=la_session.session_token,
                livekit_url=start_result.livekit_url or livekit_mgr.livekit_url,
                livekit_agent_token=(
                    start_result.livekit_agent_token
                    or livekit_mgr.generate_stt_agent_token(f"avatar-{db_session.id}")
                ),
                tenant=tenant,
                greeting_text=greeting_text,
                stt_provider=tenant.stt_provider,
                language=request.language,
                tts_task=tts_task,
            )

    except LiveAvatarError as e:
        db_session.status = SessionStatus.ERROR
        raise HTTPException(status_code=502, detail=f"LiveAvatar error: {str(e)}")
    except Exception as e:
        db_session.status = SessionStatus.ERROR
        logger.error("Session creation failed", error=str(e), session_id=db_session.id)
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
    Start streaming for a created session (if not auto-started).

    Calls LiveAvatar API to begin avatar rendering in the LiveKit room.
    Note: create_session() already calls start automatically.
    """
    db_session = await _get_session(session_id, tenant.id, db)

    if not db_session.liveavatar_session_token:
        raise HTTPException(status_code=400, detail="Session has no LiveAvatar session token")

    liveavatar = LiveAvatarClient()
    try:
        start_result = await liveavatar.start_session(db_session.liveavatar_session_token)

        # Update DB with LiveKit details
        db_session.livekit_url = start_result.livekit_url or ""
        db_session.livekit_token = start_result.livekit_client_token or ""
        db_session.ws_url = start_result.ws_url or ""
        db_session.status = SessionStatus.ACTIVE
        db_session.started_at = datetime.utcnow()

        return {
            "status": "started",
            "livekit_url": db_session.livekit_url,
            "livekit_token": db_session.livekit_token,
        }
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
    if db_session.liveavatar_session_token:
        liveavatar = LiveAvatarClient()
        try:
            await liveavatar.stop_session(db_session.liveavatar_session_token)
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

    # Unregister from conversation engine + clean up all session state
    engine = get_engine()
    engine.unregister_ws_manager(session_id)
    engine.clear_memory(session_id)

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


@router.post("/{session_id}/greeting")
async def send_greeting(
    session_id: str,
    language: str = "de",
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    Send the tenant's greeting message to the avatar.
    Called after session start + language selection.
    The avatar speaks the greeting in the selected language.
    """
    db_session = await _get_session(session_id, tenant.id, db)

    if db_session.status != SessionStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Session is not active")

    engine = get_engine()
    sent = await engine.send_greeting(
        session_id=session_id,
        tenant=tenant,
        language=language,
    )

    return {
        "status": "sent" if sent else "no_greeting",
        "language": language,
    }


@router.post("/{session_id}/keep-alive")
async def keep_alive(
    session_id: str,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Reset the idle timer for an active session."""
    db_session = await _get_session(session_id, tenant.id, db)

    if not db_session.liveavatar_session_token:
        raise HTTPException(status_code=400, detail="No active LiveAvatar session token")

    liveavatar = LiveAvatarClient()
    try:
        await liveavatar.keep_alive(db_session.liveavatar_session_token)
        return {"status": "alive"}
    except Exception as e:
        # Keep-alive failures are non-critical — WS heartbeat also keeps session alive
        logger.warning("REST keep_alive failed (WS heartbeat still active)", error=str(e))
        return {"status": "alive", "note": "REST keep-alive failed, WS heartbeat active"}
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
    tenant: "Tenant" = None,
    greeting_text: str = "",
    stt_provider: Optional[str] = None,
    language: str = "de",
    tts_task: Optional[asyncio.Task] = None,
):
    """
    Background task: connect WebSocket + send greeting + start STT agent.

    OPTIMIZED v2:
    - TTS pre-generation was already started DURING the start_session REST call
      (before this background task even begins)
    - WS connect no longer blocks waiting for "connected" state (~5s → ~0.6s)
    - Net effect: greeting plays ~6-7 seconds sooner than before

    Pipeline:
    1. Connect WS (non-blocking, ~600ms TCP/TLS only)
    2. Await TTS task if still running (likely already done)
    3. Send cached audio immediately
    4. Start LiveKit agent (optional)
    """
    t0 = time.monotonic()
    engine = get_engine()

    # === Step 1: Connect WebSocket (non-blocking — no wait for "connected" state) ===
    ws_manager = None
    try:
        t_ws0 = time.monotonic()
        ws_manager = LiveAvatarWSManager(
            ws_url=ws_url,
            session_token=session_token,
            session_id=la_session_id,
        )
        await ws_manager.connect()  # Non-blocking: just TCP/TLS, no wait for "connected"
        t_ws1 = time.monotonic()

        _ws_managers[session_id] = ws_manager
        engine.register_ws_manager(session_id, ws_manager)
        engine.set_session_language(session_id, language)

        logger.info(
            "WS connect complete (non-blocking) — TIMING",
            session_id=session_id,
            ws_connect_ms=round((t_ws1 - t_ws0) * 1000),
        )

    except Exception as e:
        logger.error(
            "Failed to connect WebSocket — avatar lip-sync will not work",
            session_id=session_id,
            error=str(e),
        )
        return

    # === Step 2: Ensure TTS is ready (was started during REST calls, likely done already) ===
    if tts_task and not tts_task.done():
        t_tts_wait0 = time.monotonic()
        try:
            await asyncio.wait_for(asyncio.shield(tts_task), timeout=5.0)
        except (asyncio.TimeoutError, Exception) as e:
            logger.warning("TTS pre-task did not complete in time", error=str(e))
        t_tts_wait1 = time.monotonic()
        logger.info(
            "TTS task await — TIMING",
            session_id=session_id,
            tts_wait_ms=round((t_tts_wait1 - t_tts_wait0) * 1000),
            tts_was_done=tts_task.done() if tts_task else True,
        )
    elif tts_task and tts_task.done():
        logger.info("TTS pre-generation already complete before background task", session_id=session_id)

    t_setup = time.monotonic()
    logger.info(
        "Setup phase complete — TIMING",
        session_id=session_id,
        setup_phase_ms=round((t_setup - t0) * 1000),
    )

    # Step 2: Send greeting — audio should be cached from parallel phase
    if greeting_text and tenant:
        try:
            t_greet0 = time.monotonic()
            sent = await engine.send_greeting_direct(
                session_id=session_id,
                tenant=tenant,
                greeting_text=greeting_text,
                language=language,
            )
            t_greet1 = time.monotonic()
            logger.info(
                "Auto-greeting sent — TIMING",
                session_id=session_id,
                language=language,
                sent=sent,
                greeting_send_ms=round((t_greet1 - t_greet0) * 1000),
                total_setup_ms=round((t_greet1 - t0) * 1000),
            )
        except Exception as e:
            logger.warning(
                "Auto-greeting failed — user can still trigger via REST",
                session_id=session_id,
                error=str(e),
            )
    else:
        logger.info("No greeting text configured, skipping auto-greeting", session_id=session_id)

    # Step 3: Start LiveKit agent for STT (OPTIONAL — text input still works without it)
    try:
        from services.livekit_agent import LiveKitAgentService

        agent = LiveKitAgentService(
            livekit_url=livekit_url,
            agent_token=livekit_agent_token,
            session_id=session_id,
            stt_provider=stt_provider,
            language=language,
        )

        async def on_transcription(result):
            if result.is_final and result.text:
                logger.info(
                    "User speech transcribed",
                    text=result.text[:80],
                    session=session_id,
                )

        agent.on_transcription(on_transcription)
        await agent.start()
        _livekit_agents[session_id] = agent

        logger.info("LiveKit STT agent started for session", session_id=session_id)

    except ImportError as e:
        logger.warning(
            "LiveKit agent not available — STT via LiveKit disabled (text input still works)",
            session_id=session_id,
            error=str(e),
        )
    except Exception as e:
        logger.warning(
            "LiveKit agent failed to start — STT disabled (text input still works)",
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
