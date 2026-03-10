"""
Conversation API Routes — Handle chat messages with the avatar.

Endpoints:
- POST /{session_id}/message       → Send a text message, get response + avatar speech
- WS   /{session_id}/stream        → Stream response via WebSocket (live tokens + avatar audio)
- GET  /{session_id}/history        → Get conversation history

LITE Mode Flow:
  User sends text message (REST or WS)
    → ConversationEngine: RAG → LLM → Text response
    → ElevenLabs TTS: Text → PCM 16Bit 24KHz audio
    → LiveAvatar WebSocket: agent.speak(audio_base64)
    → Avatar renders lip-sync video in LiveKit room
"""

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.tenant import Tenant
from models.session import AvatarSession, SessionStatus
from models.conversation import Conversation, Message, MessageRole
from api.middleware.auth import get_current_tenant
from services.engine_instance import get_engine

router = APIRouter()


class MessageRequest(BaseModel):
    message: str
    send_to_avatar: bool = True


class MessageResponse(BaseModel):
    response: str
    context_used: bool
    sources: list[dict]
    llm_model: str
    llm_provider: str
    avatar_sent: bool


@router.post("/{session_id}/message", response_model=MessageResponse)
async def send_message(
    session_id: str,
    request: MessageRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    Send a text message to the conversation.

    Flow: Message → RAG → LLM → TTS → WebSocket → Avatar Speech → Response

    The avatar speaks the response via the LITE Mode audio pipeline:
    Text is converted to PCM audio by ElevenLabs, then sent as Base64
    chunks to the LiveAvatar WebSocket for real-time lip-sync.
    """
    session = await _get_active_session(session_id, tenant.id, db)

    engine = get_engine()
    result = await engine.process_message(
        tenant=tenant,
        session_id=session_id,
        user_message=request.message,
        send_to_avatar=request.send_to_avatar,
    )

    # Store messages in DB
    conversation = session.conversations[0] if session.conversations else None
    if conversation:
        db.add(Message(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content=request.message,
        ))
        db.add(Message(
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            content=result["response"],
        ))
        session.message_count += 1

    return MessageResponse(
        response=result["response"],
        context_used=result["context_used"],
        sources=result["sources"],
        llm_model=result["llm_model"],
        llm_provider=result["llm_provider"],
        avatar_sent=result["avatar_sent"],
    )


@router.websocket("/{session_id}/stream")
async def stream_message(
    websocket: WebSocket,
    session_id: str,
):
    """
    WebSocket endpoint for streaming conversations.

    The client sends: {"message": "user question", "api_key": "..."}
    The server streams back:
      - {"type": "token", "content": "partial text"}     → LLM token
      - {"type": "avatar_sent", "sentence": "..."}       → Sentence sent to avatar via audio
      - {"type": "done", "full_response": "..."}          → Complete response
      - {"type": "error", "message": "..."}               → Error

    Each completed sentence is converted to audio via ElevenLabs TTS
    and sent to the avatar for lip-sync speech in real-time.
    """
    await websocket.accept()

    try:
        while True:
            data = await websocket.receive_json()
            user_message = data.get("message", "")
            api_key = data.get("api_key", "")

            if not user_message:
                await websocket.send_json({"type": "error", "message": "Empty message"})
                continue

            # Resolve tenant from API key
            from database import async_session_factory
            from models.tenant import Tenant as TenantModel

            async with async_session_factory() as db:
                result = await db.execute(
                    select(TenantModel).where(TenantModel.api_key == api_key)
                )
                tenant = result.scalar_one_or_none()

                if not tenant:
                    await websocket.send_json({"type": "error", "message": "Invalid API key"})
                    continue

                session_result = await db.execute(
                    select(AvatarSession).where(
                        AvatarSession.id == session_id,
                        AvatarSession.tenant_id == tenant.id,
                    )
                )
                session = session_result.scalar_one_or_none()

                if not session:
                    await websocket.send_json({"type": "error", "message": "Session not found"})
                    continue

                # Stream the response (LLM tokens + avatar audio per sentence)
                engine = get_engine()
                async for chunk in engine.process_message_stream(
                    tenant=tenant,
                    session_id=session_id,
                    user_message=user_message,
                ):
                    await websocket.send_json(chunk)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass


@router.get("/{session_id}/history")
async def get_history(
    session_id: str,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Get conversation history for a session."""
    session = await _get_active_session(session_id, tenant.id, db)

    if not session.conversations:
        return {"messages": []}

    conversation = session.conversations[0]
    messages = [
        {
            "role": msg.role.value,
            "content": msg.content,
            "timestamp": msg.created_at.isoformat(),
        }
        for msg in conversation.messages
    ]

    return {"session_id": session_id, "messages": messages}


async def _get_active_session(
    session_id: str, tenant_id: str, db: AsyncSession
) -> AvatarSession:
    """Fetch session and verify it belongs to tenant."""
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
