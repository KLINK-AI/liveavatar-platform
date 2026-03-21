"""
Admin API Routes — Dashboard, analytics, and authentication.

Endpoints:
- POST /auth/token       → Legacy admin JWT token (username/password)
- POST /auth/login       → User-based login (email/password) — for tenant_admin + superadmin
- POST /auth/users       → Create new user (superadmin only)
- GET  /auth/users       → List users (superadmin only)
- GET  /auth/me          → Get current user info
- GET  /stats            → Platform-wide statistics
- GET  /stats/{tenant}   → Per-tenant statistics
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
import secrets
import structlog

from config import get_settings
from database import get_db
from models.tenant import Tenant
from models.session import AvatarSession, SessionStatus
from models.conversation import Message
from models.user import User, UserRole
from api.middleware.auth import (
    create_access_token,
    hash_password,
    verify_password,
    get_current_user,
    require_role,
)

router = APIRouter()
settings = get_settings()
logger = structlog.get_logger()


# --- Auth Request/Response Models ---

class AuthRequest(BaseModel):
    """Legacy admin login with username and password."""
    username: str
    password: str


class LoginRequest(BaseModel):
    """User-based login with email and password."""
    email: str
    password: str


class CreateUserRequest(BaseModel):
    """Create a new user (superadmin only)."""
    email: str
    password: str
    display_name: str
    role: str = "tenant_admin"
    tenant_id: str | None = None


# --- Auth Endpoints ---

@router.post("/auth/token")
async def get_admin_token(request: AuthRequest):
    """
    Legacy: Exchange admin username/password for a JWT token.
    The admin account manages ALL tenants.
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


@router.post("/auth/login")
async def user_login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    User-based login: email + password → JWT token.
    Works for both superadmin and tenant_admin users.
    """
    result = await db.execute(
        select(User).where(User.email == request.email, User.is_active == True)
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Ungültige Anmeldedaten")

    token_data = {
        "user_id": user.id,
        "role": user.role.value,
        "sub": user.email,
    }
    if user.tenant_id:
        token_data["tenant_id"] = user.tenant_id

    token = create_access_token(
        data=token_data,
        expires_delta=timedelta(hours=24),
    )

    user.last_login = datetime.utcnow()
    logger.info("User login successful", email=user.email, role=user.role.value)

    return {
        "access_token": token,
        "token_type": "bearer",
        "role": user.role.value,
        "user_id": user.id,
        "display_name": user.display_name,
        "tenant_id": user.tenant_id,
    }


@router.get("/auth/me")
async def get_current_user_info(
    user: User = Depends(get_current_user),
):
    """Get the currently authenticated user's info."""
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role.value,
        "tenant_id": user.tenant_id,
    }


@router.post("/auth/users")
async def create_user(
    request: CreateUserRequest,
    user: User = Depends(require_role(UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Create a new user. Superadmin only."""
    try:
        role = UserRole(request.role)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid role: {request.role}")

    if role == UserRole.TENANT_ADMIN and not request.tenant_id:
        raise HTTPException(status_code=400, detail="tenant_id is required for tenant_admin role")

    if request.tenant_id:
        result = await db.execute(select(Tenant).where(Tenant.id == request.tenant_id))
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Tenant not found")

    result = await db.execute(select(User).where(User.email == request.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    new_user = User(
        email=request.email,
        password_hash=hash_password(request.password),
        display_name=request.display_name,
        role=role,
        tenant_id=request.tenant_id,
    )
    db.add(new_user)
    await db.flush()

    logger.info("User created", email=new_user.email, role=role.value, tenant_id=request.tenant_id)

    return {
        "id": new_user.id,
        "email": new_user.email,
        "display_name": new_user.display_name,
        "role": new_user.role.value,
        "tenant_id": new_user.tenant_id,
    }


@router.get("/auth/users")
async def list_users(
    user: User = Depends(require_role(UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """List all users. Superadmin only."""
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()

    return [
        {
            "id": u.id,
            "email": u.email,
            "display_name": u.display_name,
            "role": u.role.value,
            "tenant_id": u.tenant_id,
            "tenant_name": u.tenant.name if u.tenant else None,
            "is_active": u.is_active,
            "last_login": u.last_login.isoformat() if u.last_login else None,
            "created_at": u.created_at.isoformat(),
        }
        for u in users
    ]


class UpdateUserRequest(BaseModel):
    """Update an existing user (superadmin only)."""
    email: str | None = None
    display_name: str | None = None
    password: str | None = None
    role: str | None = None
    tenant_id: str | None = None
    is_active: bool | None = None


@router.put("/auth/users/{user_id}")
async def update_user(
    user_id: str,
    request: UpdateUserRequest,
    current_user: User = Depends(require_role(UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Update an existing user. Superadmin only."""
    result = await db.execute(select(User).where(User.id == user_id))
    target_user = result.scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = request.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        if key == "password" and value:
            target_user.password_hash = hash_password(value)
        elif key == "role" and value:
            try:
                target_user.role = UserRole(value)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid role: {value}")
        elif key == "tenant_id":
            if value:
                tenant_check = await db.execute(select(Tenant).where(Tenant.id == value))
                if not tenant_check.scalar_one_or_none():
                    raise HTTPException(status_code=404, detail="Tenant not found")
            target_user.tenant_id = value
        elif key != "password":
            setattr(target_user, key, value)

    logger.info("User updated", user_id=user_id, fields=list(update_data.keys()))

    return {
        "id": target_user.id,
        "email": target_user.email,
        "display_name": target_user.display_name,
        "role": target_user.role.value,
        "tenant_id": target_user.tenant_id,
        "is_active": target_user.is_active,
    }


@router.delete("/auth/users/{user_id}")
async def delete_user(
    user_id: str,
    current_user: User = Depends(require_role(UserRole.SUPERADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Delete a user. Superadmin only."""
    result = await db.execute(select(User).where(User.id == user_id))
    target_user = result.scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    if target_user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    await db.delete(target_user)
    logger.info("User deleted", user_id=user_id, email=target_user.email)

    return {"status": "deleted", "user_id": user_id}


# --- Stats Endpoints ---

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
