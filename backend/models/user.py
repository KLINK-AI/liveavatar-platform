"""User model for role-based access control.

Roles:
- superadmin: Platform operator (Stefan), manages all tenants
- tenant_admin: Customer admin, manages only their own tenant's KB, logs, analytics
"""

import uuid
import enum
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


class UserRole(str, enum.Enum):
    SUPERADMIN = "superadmin"
    TENANT_ADMIN = "tenant_admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SQLEnum(UserRole), nullable=False, default=UserRole.TENANT_ADMIN
    )

    # Tenant association (NULL for superadmin who can access all tenants)
    tenant_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tenants.id"), nullable=True, index=True
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    tenant = relationship("Tenant", backref="users", lazy="selectin")

    def __repr__(self) -> str:
        return f"<User {self.email} ({self.role.value})>"
