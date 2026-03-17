"""
Tenant Admin API Routes — Knowledge Base management, Chat Logs, Analytics, Test Query.

These endpoints are accessible by:
- tenant_admin: Only sees their own tenant's data
- superadmin: Can access any tenant's data

Endpoints:
- GET  /chat-logs             → List chat logs with pagination + filter
- GET  /chat-logs/{log_id}    → Get single chat log detail
- POST /test-query            → Test query (LLM + RAG, no avatar)
- GET  /analytics/documents   → Document usage analytics
- GET  /analytics/overview    → General analytics overview

Note: System Prompt management is in the Master Admin area only (tenants.py PUT endpoint).
Customers must NOT have access to modify or view the system prompt.
"""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession
import time
import structlog

from config import get_settings
from database import get_db
from models.tenant import Tenant
from models.chat_log import ChatLog
from models.knowledge_base import KnowledgeBase
from models.user import User, UserRole
from api.middleware.auth import get_current_user, get_tenant_admin_tenant

# Lazy imports for conversation engine (avoid circular imports)
_conversation_engine = None


def _get_engine():
    global _conversation_engine
    if _conversation_engine is None:
        from services.conversation.engine import ConversationEngine
        _conversation_engine = ConversationEngine()
    return _conversation_engine


router = APIRouter()
settings = get_settings()
logger = structlog.get_logger()


# --- Request/Response Models ---

class TestQueryRequest(BaseModel):
    """Test query without avatar — just LLM + RAG."""
    message: str
    language: str = "de"


# --- Chat Logs ---

@router.get("/chat-logs")
async def list_chat_logs(
    tenant: Tenant = Depends(get_tenant_admin_tenant),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    search: Optional[str] = Query(None, description="Search in user messages"),
    rag_only: Optional[bool] = Query(None, description="Filter: only RAG-used logs"),
    date_from: Optional[str] = Query(None, description="Filter from date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Filter to date (YYYY-MM-DD)"),
):
    """
    List chat logs for the tenant with pagination and filters.
    Shows: timestamp, user question, bot answer, RAG tag, response time.
    """
    query = select(ChatLog).where(ChatLog.tenant_id == tenant.id)

    # Apply filters
    if search:
        query = query.where(ChatLog.user_message.ilike(f"%{search}%"))
    if rag_only is True:
        query = query.where(ChatLog.rag_used == True)
    if date_from:
        try:
            dt_from = datetime.fromisoformat(date_from)
            query = query.where(ChatLog.created_at >= dt_from)
        except ValueError:
            pass
    if date_to:
        try:
            dt_to = datetime.fromisoformat(date_to) + timedelta(days=1)
            query = query.where(ChatLog.created_at < dt_to)
        except ValueError:
            pass

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0

    # Paginate
    offset = (page - 1) * per_page
    query = query.order_by(desc(ChatLog.created_at)).offset(offset).limit(per_page)
    result = await db.execute(query)
    logs = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page if total > 0 else 0,
        "items": [
            {
                "id": log.id,
                "user_message": log.user_message,
                "bot_response": log.bot_response,
                "rag_used": log.rag_used,
                "rag_sources": log.rag_sources,
                "duration_total_ms": log.duration_total_ms,
                "duration_rag_ms": log.duration_rag_ms,
                "duration_llm_ms": log.duration_llm_ms,
                "duration_tts_ms": log.duration_tts_ms,
                "tokens_prompt": log.tokens_prompt,
                "tokens_completion": log.tokens_completion,
                "llm_provider": log.llm_provider,
                "llm_model": log.llm_model,
                "language": log.language,
                "session_id": log.session_id,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ],
    }


@router.get("/chat-logs/{log_id}")
async def get_chat_log_detail(
    log_id: str,
    tenant: Tenant = Depends(get_tenant_admin_tenant),
    db: AsyncSession = Depends(get_db),
):
    """Get detailed view of a single chat log entry."""
    result = await db.execute(
        select(ChatLog).where(
            ChatLog.id == log_id,
            ChatLog.tenant_id == tenant.id,
        )
    )
    log = result.scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="Chat log not found")

    return {
        "id": log.id,
        "user_message": log.user_message,
        "bot_response": log.bot_response,
        "rag_used": log.rag_used,
        "rag_sources": log.rag_sources,
        "duration_total_ms": log.duration_total_ms,
        "duration_rag_ms": log.duration_rag_ms,
        "duration_llm_ms": log.duration_llm_ms,
        "duration_tts_ms": log.duration_tts_ms,
        "tokens_prompt": log.tokens_prompt,
        "tokens_completion": log.tokens_completion,
        "llm_provider": log.llm_provider,
        "llm_model": log.llm_model,
        "language": log.language,
        "session_id": log.session_id,
        "created_at": log.created_at.isoformat(),
    }


# --- Test Query ---

@router.post("/test-query")
async def test_query(
    request: TestQueryRequest,
    tenant: Tenant = Depends(get_tenant_admin_tenant),
    db: AsyncSession = Depends(get_db),
):
    """
    Test query: run LLM + RAG pipeline without avatar.
    Returns answer text, RAG sources with confidence, and timing breakdown.
    Used by tenant admins to test KB quality directly in the admin panel.
    """
    import traceback
    test_session_id = None

    try:
        engine = _get_engine()
        t_start = time.monotonic()

        # Explicitly load knowledge bases (selectin lazy loading doesn't
        # work reliably across FastAPI dependency boundaries)
        kb_result = await db.execute(
            select(KnowledgeBase).where(KnowledgeBase.tenant_id == tenant.id)
        )
        knowledge_bases = kb_result.scalars().all()

        logger.info("Test query KB check",
                     tenant=tenant.slug,
                     kb_count=len(knowledge_bases),
                     kb_names=[kb.name for kb in knowledge_bases])

        # Use a synthetic session ID for test queries
        test_session_id = f"test-{tenant.slug}-{int(time.time())}"
        engine.set_session_language(test_session_id, request.language)

        # Process message WITHOUT sending to avatar, pass KBs explicitly
        result = await engine.process_message(
            tenant=tenant,
            session_id=test_session_id,
            user_message=request.message,
            send_to_avatar=False,
            knowledge_bases=knowledge_bases,
        )

        t_total = round((time.monotonic() - t_start) * 1000)

        # Note: Test queries are NOT logged to chat_logs because
        # ChatLog.session_id has a FK constraint to avatar_sessions,
        # and test queries don't have a real avatar session.

        return {
            "response": result["response"],
            "rag_used": result.get("context_used", False),
            "sources": result.get("sources", []),
            "llm_model": result.get("llm_model"),
            "llm_provider": result.get("llm_provider"),
            "duration_total_ms": t_total,
            "tokens": result.get("usage"),
        }

    except HTTPException:
        raise
    except Exception as e:
        tb = traceback.format_exc()
        logger.error("Test query failed", error=str(e), traceback=tb)
        raise HTTPException(
            status_code=500,
            detail=f"Test query error: {type(e).__name__}: {str(e)}"
        )

    finally:
        if test_session_id:
            try:
                _get_engine().clear_memory(test_session_id)
            except Exception:
                pass


# --- Document Analytics ---

@router.get("/analytics/documents")
async def get_document_analytics(
    tenant: Tenant = Depends(get_tenant_admin_tenant),
    db: AsyncSession = Depends(get_db),
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
):
    """
    Document usage analytics: which documents are referenced most?
    Returns usage frequency per source document, based on RAG sources in chat logs.
    """
    since = datetime.utcnow() - timedelta(days=days)

    # Get all chat logs with RAG sources for this tenant
    result = await db.execute(
        select(ChatLog.rag_sources, ChatLog.created_at).where(
            ChatLog.tenant_id == tenant.id,
            ChatLog.rag_used == True,
            ChatLog.rag_sources.isnot(None),
            ChatLog.created_at >= since,
        )
    )
    rows = result.all()

    # Aggregate document usage
    doc_usage: dict[str, dict] = {}
    daily_usage: dict[str, dict[str, int]] = {}  # date → {source: count}

    for rag_sources, created_at in rows:
        if not rag_sources:
            continue
        date_key = created_at.strftime("%Y-%m-%d")

        for source_entry in rag_sources:
            source_name = source_entry.get("source", "unknown")
            score = source_entry.get("score", 0)

            if source_name not in doc_usage:
                doc_usage[source_name] = {
                    "source": source_name,
                    "total_references": 0,
                    "avg_confidence": 0,
                    "scores_sum": 0,
                    "first_used": created_at.isoformat(),
                    "last_used": created_at.isoformat(),
                }

            doc_usage[source_name]["total_references"] += 1
            doc_usage[source_name]["scores_sum"] += score
            doc_usage[source_name]["last_used"] = created_at.isoformat()

            # Daily breakdown
            if date_key not in daily_usage:
                daily_usage[date_key] = {}
            daily_usage[date_key][source_name] = daily_usage[date_key].get(source_name, 0) + 1

    # Compute averages and sort
    documents = []
    for doc in doc_usage.values():
        doc["avg_confidence"] = round(doc["scores_sum"] / doc["total_references"], 3) if doc["total_references"] > 0 else 0
        del doc["scores_sum"]
        documents.append(doc)

    documents.sort(key=lambda d: d["total_references"], reverse=True)

    return {
        "period_days": days,
        "total_rag_queries": len(rows),
        "unique_documents": len(documents),
        "documents": documents,
        "daily_heatmap": daily_usage,
    }


@router.get("/analytics/overview")
async def get_analytics_overview(
    tenant: Tenant = Depends(get_tenant_admin_tenant),
    db: AsyncSession = Depends(get_db),
    days: int = Query(30, ge=1, le=365),
):
    """
    General analytics overview for the tenant:
    - Total queries, RAG usage rate, avg response time, token consumption
    - Daily query volume
    """
    since = datetime.utcnow() - timedelta(days=days)

    # Total queries
    total = await db.scalar(
        select(func.count(ChatLog.id)).where(
            ChatLog.tenant_id == tenant.id,
            ChatLog.created_at >= since,
        )
    ) or 0

    # RAG queries
    rag_count = await db.scalar(
        select(func.count(ChatLog.id)).where(
            ChatLog.tenant_id == tenant.id,
            ChatLog.rag_used == True,
            ChatLog.created_at >= since,
        )
    ) or 0

    # Average response time
    avg_duration = await db.scalar(
        select(func.avg(ChatLog.duration_total_ms)).where(
            ChatLog.tenant_id == tenant.id,
            ChatLog.created_at >= since,
        )
    )

    # Total tokens
    total_prompt_tokens = await db.scalar(
        select(func.sum(ChatLog.tokens_prompt)).where(
            ChatLog.tenant_id == tenant.id,
            ChatLog.created_at >= since,
        )
    ) or 0
    total_completion_tokens = await db.scalar(
        select(func.sum(ChatLog.tokens_completion)).where(
            ChatLog.tenant_id == tenant.id,
            ChatLog.created_at >= since,
        )
    ) or 0

    # Daily query volume
    result = await db.execute(
        select(
            func.date(ChatLog.created_at).label("date"),
            func.count(ChatLog.id).label("count"),
        ).where(
            ChatLog.tenant_id == tenant.id,
            ChatLog.created_at >= since,
        ).group_by(func.date(ChatLog.created_at)).order_by(func.date(ChatLog.created_at))
    )
    daily_volume = [{"date": str(row.date), "count": row.count} for row in result.all()]

    return {
        "period_days": days,
        "total_queries": total,
        "rag_queries": rag_count,
        "rag_usage_rate": round(rag_count / total * 100, 1) if total > 0 else 0,
        "avg_response_time_ms": round(avg_duration) if avg_duration else None,
        "total_tokens": {
            "prompt": total_prompt_tokens,
            "completion": total_completion_tokens,
            "total": total_prompt_tokens + total_completion_tokens,
        },
        "daily_volume": daily_volume,
    }


