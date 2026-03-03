import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base
import enum


class UserRole(str, enum.Enum):
    admin = "admin"
    moderator = "moderator"
    member = "member"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    username: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, index=True
    )
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole), default=UserRole.member, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    last_seen: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    memberships = relationship("ChannelMember", back_populates="user", lazy="selectin")
