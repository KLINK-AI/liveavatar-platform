"""Tenant model for multi-tenant white-label support."""

import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    api_key: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True,
        default=lambda: uuid.uuid4().hex + uuid.uuid4().hex[:32]
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # LiveAvatar / Avatar Config (migrated from heygen_*)
    liveavatar_avatar_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    liveavatar_voice_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        comment="LiveAvatar voice ID (only used if LiveAvatar handles TTS)"
    )

    # TTS — ElevenLabs (per-tenant override)
    elevenlabs_api_key: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Per-tenant ElevenLabs API key (falls back to global config)"
    )
    elevenlabs_voice_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        comment="Per-tenant ElevenLabs voice ID"
    )

    # STT Config (per-tenant override)
    stt_provider: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
        comment="'deepgram' or 'openai' — falls back to global config"
    )

    # LLM Config
    llm_provider: Mapped[str] = mapped_column(String(50), default="openai")
    llm_model: Mapped[str] = mapped_column(String(100), default="gpt-4o-mini")
    llm_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    system_prompt: Mapped[str] = mapped_column(
        Text,
        default="Du bist ein freundlicher und hilfreicher Assistent. Antworte präzise und verständlich auf Deutsch."
    )

    # Avatar Preview Image (shown before session starts)
    avatar_preview_image: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Base64-encoded preview image or URL, shown instead of black screen"
    )

    # Multi-Language Support
    supported_languages: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, default=lambda: ["de"],
        comment='JSON array of supported language codes, e.g. ["de","en","fr"]'
    )
    default_language: Mapped[str] = mapped_column(
        String(10), default="de",
        comment="Default/primary language for this tenant"
    )

    # Greeting System
    greeting_text: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        default="Hallo, ich bin Ihr digitaler Assistent und stehe Ihnen für Fragen zur Verfügung.",
        comment="Greeting text in the default language"
    )
    greeting_translations: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, default=lambda: {},
        comment='Greeting translations: {"en": "Hello...", "fr": "Bonjour..."}'
    )

    # White-Label Branding
    branding: Mapped[dict | None] = mapped_column(
        JSON, nullable=True,
        comment="JSON: {logo_url, primary_color, secondary_color, font_family, custom_css}"
    )

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    sessions = relationship("AvatarSession", back_populates="tenant", lazy="selectin")
    knowledge_bases = relationship("KnowledgeBase", back_populates="tenant", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Tenant {self.name} ({self.slug})>"
