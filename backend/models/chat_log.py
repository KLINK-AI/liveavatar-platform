"""Chat Log model for persistent conversation logging.

Stores every question/answer pair with:
- RAG source documents + confidence scores
- Timing breakdown (total, RAG, LLM)
- Token usage
- Tenant + session association

Used by:
- Tenant Admin Dashboard → Chat Logs tab
- Document Analytics (which docs are referenced most)
"""

import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Text, JSON, Float, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


class ChatLog(Base):
    __tablename__ = "chat_logs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # Tenant + Session association
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id"), nullable=False, index=True
    )
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("avatar_sessions.id"), nullable=False, index=True
    )

    # User question + Bot answer
    user_message: Mapped[str] = mapped_column(Text, nullable=False)
    bot_response: Mapped[str] = mapped_column(Text, nullable=False)

    # RAG metadata
    rag_used: Mapped[bool] = mapped_column(Boolean, default=False)
    rag_sources: Mapped[dict | None] = mapped_column(
        JSON, nullable=True,
        comment='[{"source": "filename.pdf", "score": 0.92, "chunk_text": "..."}]'
    )

    # Timing breakdown (milliseconds)
    duration_total_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_rag_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_llm_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_tts_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_first_sentence_ms: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        comment='Time until first sentence ready (RAG + LLM first sentence). '
                'This is the perceived latency — when the avatar starts speaking.'
    )

    # Token usage
    tokens_prompt: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_completion: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # LLM info
    llm_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    llm_model: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Language
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )

    # Relationships
    tenant = relationship("Tenant", backref="chat_logs", lazy="selectin")
    session = relationship("AvatarSession", backref="chat_logs", lazy="selectin")

    def __repr__(self) -> str:
        return f"<ChatLog {self.id[:8]} tenant={self.tenant_id[:8]}>"
