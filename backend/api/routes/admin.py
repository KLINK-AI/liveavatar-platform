"""
Admin API Routes — Dashboard and analytics.

Endpoints:
- GET /stats           → Platform-wide statistics
- GET /stats/{tenant}  → Per-tenant statistics
- POST /auth/token     → Generate admin JWT token
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta

from database import get_db
from models.tenant import Tenant
from models.session import AvatarSession, SessionStatus
from models.conversation import Message
from api.middleware.auth import create_access_token

router = APIRouter()


class AuthRequest(BaseModel):
    """Simple auth for admin dashboard."""
    tenant_slug: str
    api_key: str


@router.post("/auth/token")
async def get_admin_token(
    request: AuthRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Exchange tenant API key for a JWT token.
    Used by the admin dashboard for authenticated requests.
    """
    result = await db.execute(
        select(Tenant).where(
            Tenant.slug == request.tenant_slug,
            Tenant.api_key == request.api_key,
            Tenant.is_active == True,
        )
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(
        data={"tenant_id": tenant.id, "slug": tenant.slug},
        expires_delta=timedelta(hours=24),
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "tenant_id": tenant.id,
        "tenant_name": tenant.name,
    }


@router.get("/stats")
async def get_platform_stats(
    db: AsyncSession = Depends(get_db),
):
    """Get platform-wide statistics."""
    tenant_count = await db.scalar(select(func.count(Tenant.id)))
    session_count = await db.scalar(select(func.count(AvatarSession.id)))
    active_sessions = await db.scalar(
        select(func.count(AvatarSession.id)).where(
            AvatarSession.status == SessionStatus.ACTIVE
        )
    )
    message_count = await db.scalar(select(func.count(Message.id)))

    return {
        "tenants": tenant_count,
        "total_sessions": session_count,
        "active_sessions": active_sessions,
        "total_messages": message_count,
    }


@router.get("/stats/{tenant_slug}")
async def get_tenant_stats(
    tenant_slug: str,
    db: AsyncSession = Depends(get_db),
):
    """Get statistics for a specific tenant."""
    result = await db.execute(
        select(Tenant).where(Tenant.slug == tenant_slug)
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    session_count = await db.scalar(
        select(func.count(AvatarSession.id)).where(
            AvatarSession.tenant_id == tenant.id
        )
    )
    active_sessions = await db.scalar(
        select(func.count(AvatarSession.id)).where(
            AvatarSession.tenant_id == tenant.id,
            AvatarSession.status == SessionStatus.ACTIVE,
        )
    )
    total_duration = await db.scalar(
        select(func.sum(AvatarSession.duration_seconds)).where(
            AvatarSession.tenant_id == tenant.id
        )
    ) or 0
    total_messages = await db.scalar(
        select(func.sum(AvatarSession.message_count)).where(
            AvatarSession.tenant_id == tenant.id
        )
    ) or 0

    return {
        "tenant": tenant.name,
        "slug": tenant.slug,
        "total_sessions": session_count,
        "active_sessions": active_sessions,
        "total_duration_minutes": round(total_duration / 60, 1),
        "total_messages": total_messages,
        "llm_provider": tenant.llm_provider,
        "llm_model": tenant.llm_model,
    }
