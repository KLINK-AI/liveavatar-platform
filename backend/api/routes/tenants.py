"""
Tenant API Routes — Manage tenants (white-label customers).

Endpoints:
- POST /         → Create a new tenant
- GET  /         → List all tenants
- GET  /{id}     → Get tenant details
- PUT  /{id}     → Update tenant configuration
- GET  /by-slug/{slug} → Public: resolve tenant by slug (incl. API key for public sessions)
- POST /{id}/preview-image → Upload avatar preview image
- POST /{id}/greeting → Update greeting + auto-translate
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
import base64
import re
import structlog

from database import get_db
from models.tenant import Tenant
from api.middleware.auth import get_current_tenant

logger = structlog.get_logger()
router = APIRouter()


def _mask_key(key: Optional[str]) -> Optional[str]:
    """Mask a secret key for display: show first 4 and last 4 chars."""
    if not key:
        return None
    if len(key) <= 8:
        return "****"
    return f"{key[:4]}...{key[-4:]}"


class CreateTenantRequest(BaseModel):
    name: str
    slug: str
    liveavatar_avatar_id: Optional[str] = None
    liveavatar_voice_id: Optional[str] = None
    elevenlabs_api_key: Optional[str] = None
    elevenlabs_voice_id: Optional[str] = None
    stt_provider: Optional[str] = None
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o"
    llm_api_key: Optional[str] = None
    system_prompt: Optional[str] = None
    branding: Optional[dict] = None
    supported_languages: Optional[list[str]] = None
    default_language: Optional[str] = None
    greeting_text: Optional[str] = None
    greeting_translations: Optional[dict] = None


class UpdateTenantRequest(BaseModel):
    name: Optional[str] = None
    liveavatar_avatar_id: Optional[str] = None
    liveavatar_voice_id: Optional[str] = None
    elevenlabs_api_key: Optional[str] = None
    elevenlabs_voice_id: Optional[str] = None
    stt_provider: Optional[str] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    llm_api_key: Optional[str] = None
    system_prompt: Optional[str] = None
    branding: Optional[dict] = None
    is_active: Optional[bool] = None
    supported_languages: Optional[list[str]] = None
    default_language: Optional[str] = None
    greeting_text: Optional[str] = None
    greeting_translations: Optional[dict] = None


class UpdateGreetingRequest(BaseModel):
    greeting_text: str
    default_language: str = "de"
    auto_translate: bool = True
    target_languages: Optional[list[str]] = None


class TenantResponse(BaseModel):
    id: str
    name: str
    slug: str
    api_key: str
    is_active: bool
    liveavatar_avatar_id: Optional[str]
    liveavatar_voice_id: Optional[str]
    elevenlabs_api_key_masked: Optional[str]
    elevenlabs_voice_id: Optional[str]
    stt_provider: Optional[str]
    llm_provider: str
    llm_model: str
    llm_api_key_masked: Optional[str]
    system_prompt: str
    branding: Optional[dict]
    avatar_preview_image: Optional[str]
    supported_languages: Optional[list[str]]
    default_language: str
    greeting_text: Optional[str]
    greeting_translations: Optional[dict]
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
        liveavatar_avatar_id=request.liveavatar_avatar_id,
        liveavatar_voice_id=request.liveavatar_voice_id,
        elevenlabs_api_key=request.elevenlabs_api_key,
        elevenlabs_voice_id=request.elevenlabs_voice_id,
        stt_provider=request.stt_provider,
        llm_provider=request.llm_provider,
        llm_model=request.llm_model,
        llm_api_key=request.llm_api_key,
        system_prompt=request.system_prompt or Tenant.system_prompt.default.arg,
        branding=request.branding,
        supported_languages=request.supported_languages or ["de"],
        default_language=request.default_language or "de",
        greeting_text=request.greeting_text,
        greeting_translations=request.greeting_translations or {},
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

    # Update only provided fields, skip masked key values
    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        # Don't overwrite API keys with masked values (e.g. "sk_2...8542")
        if key in ("elevenlabs_api_key", "llm_api_key") and value and "..." in value:
            continue
        setattr(tenant, key, value)

    return _tenant_to_response(tenant)


@router.post("/{tenant_id}/preview-image")
async def upload_preview_image(
    tenant_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload an avatar preview image for a tenant.
    Accepts PNG, JPG, WebP. Stored as base64 data URI.
    """
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # Validate file type
    allowed_types = {"image/png", "image/jpeg", "image/webp"}
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"File type {file.content_type} not allowed. Use PNG, JPG, or WebP."
        )

    # Read and encode as base64 data URI
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:  # 5MB limit
        raise HTTPException(status_code=400, detail="File too large. Max 5MB.")

    b64 = base64.b64encode(content).decode("utf-8")
    data_uri = f"data:{file.content_type};base64,{b64}"

    tenant.avatar_preview_image = data_uri

    logger.info(
        "Preview image uploaded",
        tenant=tenant.slug,
        size_kb=len(content) // 1024,
        content_type=file.content_type,
    )

    return {"status": "ok", "size_kb": len(content) // 1024}


@router.post("/{tenant_id}/greeting")
async def update_greeting(
    tenant_id: str,
    request: UpdateGreetingRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Update greeting text and optionally auto-translate to target languages.
    Uses OpenAI to translate the greeting text.
    """
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    tenant.greeting_text = request.greeting_text
    tenant.default_language = request.default_language

    # Auto-translate if requested
    if request.auto_translate:
        target_langs = request.target_languages or [
            lang for lang in (tenant.supported_languages or ["de"])
            if lang != request.default_language
        ]

        if target_langs:
            translations = await _auto_translate_greeting(
                text=request.greeting_text,
                source_lang=request.default_language,
                target_langs=target_langs,
                tenant=tenant,
            )
            # Merge with existing translations
            existing = tenant.greeting_translations or {}
            existing.update(translations)
            tenant.greeting_translations = existing

    return {
        "greeting_text": tenant.greeting_text,
        "default_language": tenant.default_language,
        "greeting_translations": tenant.greeting_translations,
    }


@router.get("/by-slug/{slug}")
async def get_tenant_by_slug(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Public endpoint: resolve tenant config by slug.
    Used by the avatar frontend page and embed widget.
    Returns public info + API key needed for session creation.
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
        "has_avatar": bool(tenant.liveavatar_avatar_id),
        "api_key": tenant.api_key,
        "avatar_preview_image": tenant.avatar_preview_image,
        "supported_languages": tenant.supported_languages or ["de"],
        "default_language": tenant.default_language or "de",
        "greeting_text": tenant.greeting_text,
        "greeting_translations": tenant.greeting_translations or {},
    }


@router.get("/by-slug/{slug}/avatar.jpg")
async def get_tenant_avatar_image(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Public endpoint: serve the tenant's avatar preview image as a real image.
    Used by widget.js bubble — img tags don't need CORS headers.
    Returns the image with proper Content-Type, or 404 if no image exists.
    """
    result = await db.execute(
        select(Tenant).where(Tenant.slug == slug, Tenant.is_active == True)
    )
    tenant = result.scalar_one_or_none()
    if not tenant or not tenant.avatar_preview_image:
        raise HTTPException(status_code=404, detail="No preview image")

    data_uri = tenant.avatar_preview_image
    # Parse data URI: data:image/jpeg;base64,/9j/4AAQ...
    match = re.match(r"data:(image/\w+);base64,(.+)", data_uri, re.DOTALL)
    if not match:
        raise HTTPException(status_code=500, detail="Invalid image data")

    content_type = match.group(1)
    image_bytes = base64.b64decode(match.group(2))

    return Response(
        content=image_bytes,
        media_type=content_type,
        headers={
            "Cache-Control": "public, max-age=3600",
            "Access-Control-Allow-Origin": "*",
        },
    )


async def _auto_translate_greeting(
    text: str,
    source_lang: str,
    target_langs: list[str],
    tenant: Tenant,
) -> dict[str, str]:
    """
    Translate greeting text to target languages using the tenant's LLM.
    Returns dict of {lang_code: translated_text}.
    """
    from services.llm.provider_factory import LLMProviderFactory
    from services.llm.base import LLMMessage

    LANG_NAMES = {
        "de": "German", "en": "English", "fr": "French", "es": "Spanish",
        "it": "Italian", "nl": "Dutch", "pt": "Portuguese", "pl": "Polish",
        "ru": "Russian", "uk": "Ukrainian", "tr": "Turkish", "ar": "Arabic",
        "zh": "Chinese", "ja": "Japanese", "ko": "Korean", "hi": "Hindi",
        "sv": "Swedish", "no": "Norwegian", "da": "Danish", "fi": "Finnish",
        "el": "Greek", "cs": "Czech", "ro": "Romanian", "hu": "Hungarian",
        "bg": "Bulgarian", "hr": "Croatian", "sk": "Slovak", "sl": "Slovenian",
    }

    translations = {}
    llm = LLMProviderFactory.get_provider_for_tenant(tenant)

    for lang in target_langs:
        lang_name = LANG_NAMES.get(lang, lang)
        source_name = LANG_NAMES.get(source_lang, source_lang)

        try:
            response = await llm.chat(
                messages=[
                    LLMMessage(
                        role="system",
                        content=(
                            f"You are a professional translator. "
                            f"Translate the following greeting from {source_name} to {lang_name}. "
                            f"Keep the same tone and meaning. Return ONLY the translated text, nothing else."
                        ),
                    ),
                    LLMMessage(role="user", content=text),
                ],
                model=tenant.llm_model,
                temperature=0.3,
                max_tokens=200,
            )
            translations[lang] = response.content.strip().strip('"').strip("'")
            logger.info(f"Translated greeting to {lang}: {translations[lang][:50]}...")
        except Exception as e:
            logger.error(f"Failed to translate greeting to {lang}: {e}")

    return translations


def _tenant_to_response(tenant: Tenant) -> TenantResponse:
    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        api_key=tenant.api_key,
        is_active=tenant.is_active,
        liveavatar_avatar_id=tenant.liveavatar_avatar_id,
        liveavatar_voice_id=tenant.liveavatar_voice_id,
        elevenlabs_api_key_masked=_mask_key(tenant.elevenlabs_api_key),
        elevenlabs_voice_id=tenant.elevenlabs_voice_id,
        stt_provider=tenant.stt_provider,
        llm_provider=tenant.llm_provider,
        llm_model=tenant.llm_model,
        llm_api_key_masked=_mask_key(tenant.llm_api_key),
        system_prompt=tenant.system_prompt,
        branding=tenant.branding,
        avatar_preview_image=tenant.avatar_preview_image,
        supported_languages=tenant.supported_languages or ["de"],
        default_language=tenant.default_language or "de",
        greeting_text=tenant.greeting_text,
        greeting_translations=tenant.greeting_translations or {},
        created_at=tenant.created_at.isoformat(),
    )
