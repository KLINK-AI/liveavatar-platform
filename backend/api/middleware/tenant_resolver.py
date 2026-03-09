"""Tenant resolver middleware — resolves tenant from slug in URL or subdomain."""

from fastapi import Request, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import async_session_factory
from models.tenant import Tenant


async def resolve_tenant_by_slug(slug: str) -> Tenant:
    """Resolve a tenant by their URL slug (e.g., /widget/buettelborn)."""
    async with async_session_factory() as db:
        result = await db.execute(
            select(Tenant).where(Tenant.slug == slug, Tenant.is_active == True)
        )
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tenant '{slug}' not found",
            )
        return tenant
