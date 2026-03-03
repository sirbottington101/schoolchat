import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base
from app.models.user import UserRole
import enum


class ChannelMemberRole(str, enum.Enum):
    """Per-channel role override."""
    admin = "admin"
    moderator = "moderator"
    member = "member"


class Channel(Base):
    __tablename__ = "channels"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(String(256), nullable=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_private: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    archived: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    members = relationship("ChannelMember", back_populates="channel", lazy="selectin")
    creator = relationship("User", foreign_keys=[created_by], lazy="selectin")


class ChannelMember(Base):
    __tablename__ = "channel_members"

    channel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channels.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role_override: Mapped[ChannelMemberRole | None] = mapped_column(
        SAEnum(ChannelMemberRole), nullable=True
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    channel = relationship("Channel", back_populates="members")
    user = relationship("User", back_populates="memberships")
