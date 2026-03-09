"""Avatar session model for tracking LiveAvatar streaming sessions."""

import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Integer, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base
import enum


class SessionStatus(str, enum.Enum):
    CREATING = "creating"
    ACTIVE = "active"
    PAUSED = "paused"
    CLOSED = "closed"
    ERROR = "error"


class AvatarSession(Base):
    __tablename__ = "avatar_sessions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id"), nullable=False, index=True
    )

    # HeyGen Session
    heygen_session_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[SessionStatus] = mapped_column(
        SQLEnum(SessionStatus), default=SessionStatus.CREATING
    )

    # LiveKit
    livekit_room_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    livekit_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    livekit_token: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    # Analytics
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)

    # Timestamps
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    tenant = relationship("Tenant", back_populates="sessions")
    conversations = relationship("Conversation", back_populates="session", lazy="selectin")

    def __repr__(self) -> str:
        return f"<AvatarSession {self.id} status={self.status}>"
