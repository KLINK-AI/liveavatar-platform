"""Authentication middleware — JWT and API Key based auth with RBAC.

Supports three auth methods:
1. X-API-Key header → Tenant lookup (for embed widgets, public API)
2. JWT Bearer token → Role-based access (superadmin or tenant_admin)
3. Hardcoded admin fallback → Legacy support during migration

Roles:
- superadmin: Full platform access, all tenants
- tenant_admin: Access only to their own tenant's data
"""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from database import get_db
from models.tenant import Tenant
from models.user import User, UserRole

settings = get_settings()
bearer_scheme = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a password with bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


async def get_current_tenant(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
    api_key: Optional[str] = Security(api_key_header),
    db: AsyncSession = Depends(get_db),
) -> Tenant:
    """
    Resolve the current tenant from either:
    - JWT Bearer token (admin/tenant_admin access)
    - X-API-Key header (tenant API key for embed/widget access)
    """
    # Try API Key first (simpler, for embedded widgets)
    if api_key:
        result = await db.execute(
            select(Tenant).where(Tenant.api_key == api_key, Tenant.is_active == True)
        )
        tenant = result.scalar_one_or_none()
        if tenant:
            return tenant
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    # Try JWT Bearer token
    if credentials:
        try:
            payload = jwt.decode(
                credentials.credentials,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
            )

            role = payload.get("role")

            # Superadmin or legacy admin → return first active tenant as context
            if role in ("admin", "superadmin"):
                result = await db.execute(
                    select(Tenant).where(Tenant.is_active == True).limit(1)
                )
                tenant = result.scalar_one_or_none()
                if tenant:
                    return tenant
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="No active tenants found"
                )

            # Tenant admin → return their specific tenant
            if role == "tenant_admin":
                tenant_id = payload.get("tenant_id")
                if not tenant_id:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid token: no tenant_id"
                    )
                result = await db.execute(
                    select(Tenant).where(Tenant.id == tenant_id, Tenant.is_active == True)
                )
                tenant = result.scalar_one_or_none()
                if tenant:
                    return tenant
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Tenant not found")

            # Tenant-specific token (legacy)
            tenant_id = payload.get("tenant_id")
            if tenant_id:
                result = await db.execute(
                    select(Tenant).where(Tenant.id == tenant_id, Tenant.is_active == True)
                )
                tenant = result.scalar_one_or_none()
                if tenant:
                    return tenant

            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        except JWTError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Provide X-API-Key header or Bearer token.",
    )


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Extract the authenticated User from a JWT token.
    Used for tenant_admin routes that need user identity.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token required",
        )

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user_id = payload.get("user_id")
    role = payload.get("role")

    # Legacy admin token (no user_id) → create a virtual superadmin user object
    if not user_id and role in ("admin", "superadmin"):
        virtual_admin = User(
            id="legacy-admin",
            email=settings.admin_username,
            password_hash="",
            display_name="Admin",
            role=UserRole.SUPERADMIN,
            tenant_id=None,
        )
        return virtual_admin

    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token: no user_id")

    result = await db.execute(
        select(User).where(User.id == user_id, User.is_active == True)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user


def require_role(*roles: UserRole):
    """
    Dependency factory: require the user to have one of the given roles.

    Usage:
        @router.get("/admin-only", dependencies=[Depends(require_role(UserRole.SUPERADMIN))])
    """
    async def _check(user: User = Depends(get_current_user)):
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {', '.join(r.value for r in roles)}",
            )
        return user
    return _check


async def get_tenant_admin_tenant(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Tenant:
    """
    Resolve the tenant for a tenant_admin or superadmin user.
    Superadmins get the first active tenant (for now).
    Tenant admins are locked to their own tenant.
    """
    if user.role == UserRole.SUPERADMIN:
        result = await db.execute(
            select(Tenant).where(Tenant.is_active == True).limit(1)
        )
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise HTTPException(status_code=404, detail="No active tenants found")
        return tenant

    if user.role == UserRole.TENANT_ADMIN:
        if not user.tenant_id:
            raise HTTPException(status_code=403, detail="User not assigned to a tenant")
        result = await db.execute(
            select(Tenant).where(Tenant.id == user.tenant_id, Tenant.is_active == True)
        )
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        return tenant

    raise HTTPException(status_code=403, detail="Access denied")


async def get_admin_tenant(
    tenant: Tenant = Depends(get_current_tenant),
) -> Tenant:
    """Require admin-level access (for dashboard operations). Legacy compatibility."""
    return tenant
