"""
Tenant API Routes — Manage tenants (white-label customers).

Endpoints:
- POST /         → Create a new tenant
- GET  /         → List all tenants
- GET  /{id}     → Get tenant details
- PUT  /{id}     → Update tenant configuration
- GET  /by-slug/{slug} → Public: resolve tenant by slug
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from database import get_db
from models.tenant import Tenant
from api.middleware.auth import get_current_tenant

router = APIRouter()


class CreateTenantRequest(BaseModel):
    name: str
    slug: str
    heygen_avatar_id: Optional[str] = None
    heygen_voice_id: Optional[str] = None
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o"
    llm_api_key: Optional[str] = None
    system_prompt: Optional[str] = None
    branding: Optional[dict] = None


class UpdateTenantRequest(BaseModel):
    name: Optional[str] = None
    heygen_avatar_id: Optional[str] = None
    heygen_voice_id: Optional[str] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    llm_api_key: Optional[str] = None
    system_prompt: Optional[str] = None
    branding: Optional[dict] = None
    is_active: Optional[bool] = None


class TenantResponse(BaseModel):
    id: str
    name: str
    slug: str
    api_key: str
    is_active: bool
    heygen_avatar_id: Optional[str]
    llm_provider: str
    llm_model: str
    system_prompt: str
    branding: Optional[dict]
    created_at: str


@router.post("/", response_model=TenantResponse)
async def create_tenant(
    request: CreateTenantRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a new tenant (white-label customer)."""
    # Check slug uniqueness
    existing = await db.execute(
        select(Tenant).where(Tenant.slug == request.slug)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Slug '{request.slug}' already exists")

    tenant = Tenant(
        name=request.name,
        slug=request.slug,
        heygen_avatar_id=request.heygen_avatar_id,
        heygen_voice_id=request.heygen_voice_id,
        llm_provider=request.llm_provider,
        llm_model=request.llm_model,
        llm_api_key=request.llm_api_key,
        system_prompt=request.system_prompt or Tenant.system_prompt.default.arg,
        branding=request.branding,
    )
    db.add(tenant)
    await db.flush()

    return _tenant_to_response(tenant)


@router.get("/", response_model=list[TenantResponse])
async def list_tenants(
    db: AsyncSession = Depends(get_db),
):
    """List all tenants."""
    result = await db.execute(select(Tenant).order_by(Tenant.created_at.desc()))
    tenants = result.scalars().all()
    return [_tenant_to_response(t) for t in tenants]


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get tenant details by ID."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return _tenant_to_response(tenant)


@router.put("/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: str,
    request: UpdateTenantRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update tenant configuration."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # Update only provided fields
    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(tenant, key, value)

    return _tenant_to_response(tenant)


@router.get("/by-slug/{slug}")
async def get_tenant_by_slug(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Public endpoint: resolve tenant config by slug.
    Used by the embed widget to load branding and avatar config.
    Returns only public information (no API keys or secrets).
    """
    result = await db.execute(
        select(Tenant).where(Tenant.slug == slug, Tenant.is_active == True)
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    return {
        "name": tenant.name,
        "slug": tenant.slug,
        "branding": tenant.branding,
        "has_avatar": bool(tenant.heygen_avatar_id),
    }


def _tenant_to_response(tenant: Tenant) -> TenantResponse:
    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        api_key=tenant.api_key,
        is_active=tenant.is_active,
        heygen_avatar_id=tenant.heygen_avatar_id,
        llm_provider=tenant.llm_provider,
        llm_model=tenant.llm_model,
        system_prompt=tenant.system_prompt,
        branding=tenant.branding,
        created_at=tenant.created_at.isoformat(),
    )
