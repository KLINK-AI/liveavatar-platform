"""
Admin API Routes — Dashboard and analytics.

Endpoints:
- GET /stats           → Platform-wide statistics
- GET /stats/{tenant}  → Per-tenant statistics
- POST /auth/token     → Generate admin JWT token (username/password)
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta
import secrets

from config import get_settings
from database import get_db
from models.tenant import Tenant
from models.session import AvatarSession, SessionStatus
from models.conversation import Message
from api.middleware.auth import create_access_token

router = APIRouter()
settings = get_settings()


class AuthRequest(BaseModel):
    """Admin login with username and password."""
    username: str
    password: str


@router.post("/auth/token")
async def get_admin_token(request: AuthRequest):
    """
    Exchange admin username/password for a JWT token.
    The admin account manages ALL tenants.
    Credentials are configured via ADMIN_USERNAME and ADMIN_PASSWORD env vars.
    """
    if not secrets.compare_digest(request.username, settings.admin_username):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not secrets.compare_digest(request.password, settings.admin_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(
        data={"role": "admin", "sub": request.username},
        expires_delta=timedelta(hours=24),
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "role": "admin",
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
