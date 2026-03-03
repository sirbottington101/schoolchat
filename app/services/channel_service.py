import uuid
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.channel import Channel, ChannelMember
from app.models.user import User


async def create_channel(
    db: AsyncSession,
    name: str,
    created_by: uuid.UUID,
    description: str | None = None,
    category: str | None = None,
    is_private: bool = False,
) -> Channel:
    channel = Channel(
        name=name,
        description=description,
        category=category,
        is_private=is_private,
        created_by=created_by,
    )
    db.add(channel)
    await db.flush()

    # Creator auto-joins as admin
    member = ChannelMember(
        channel_id=channel.id,
        user_id=created_by,
        role_override="admin",
    )
    db.add(member)
    await db.flush()
    return channel


async def get_channels_for_user(
    db: AsyncSession, user_id: uuid.UUID
) -> list[dict]:
    """Return only channels the user is a member of."""
    stmt = (
        select(
            Channel,
            func.count(ChannelMember.user_id).label("member_count"),
        )
        .join(ChannelMember, Channel.id == ChannelMember.channel_id)
        .where(
            Channel.archived == False,
            Channel.id.in_(
                select(ChannelMember.channel_id)
                .where(ChannelMember.user_id == user_id)
            ),
        )
        .group_by(Channel.id)
        .order_by(Channel.category.nulls_last(), Channel.name)
    )

    result = await db.execute(stmt)
    rows = result.all()
    return [
        {**_channel_to_dict(ch), "member_count": count}
        for ch, count in rows
    ]


async def get_channel_by_id(db: AsyncSession, channel_id: uuid.UUID) -> Channel | None:
    result = await db.execute(select(Channel).where(Channel.id == channel_id))
    return result.scalar_one_or_none()


async def update_channel(
    db: AsyncSession,
    channel: Channel,
    **kwargs,
) -> Channel:
    for key, value in kwargs.items():
        if value is not None and hasattr(channel, key):
            setattr(channel, key, value)
    await db.flush()
    return channel


async def add_member(
    db: AsyncSession, channel_id: uuid.UUID, user_id: uuid.UUID
) -> ChannelMember:
    existing = await db.execute(
        select(ChannelMember).where(
            ChannelMember.channel_id == channel_id,
            ChannelMember.user_id == user_id,
        )
    )
    if existing.scalar_one_or_none():
        raise ValueError("User is already a member of this channel")

    member = ChannelMember(channel_id=channel_id, user_id=user_id)
    db.add(member)
    await db.flush()
    return member


async def remove_member(
    db: AsyncSession, channel_id: uuid.UUID, user_id: uuid.UUID
) -> bool:
    result = await db.execute(
        delete(ChannelMember).where(
            ChannelMember.channel_id == channel_id,
            ChannelMember.user_id == user_id,
        )
    )
    return result.rowcount > 0


async def get_channel_members(
    db: AsyncSession, channel_id: uuid.UUID
) -> list[dict]:
    stmt = (
        select(ChannelMember, User)
        .join(User, ChannelMember.user_id == User.id)
        .where(ChannelMember.channel_id == channel_id)
        .order_by(User.username)
    )
    result = await db.execute(stmt)
    return [
        {
            "user_id": member.user_id,
            "username": user.username,
            "display_name": user.display_name,
            "role_override": member.role_override,
            "joined_at": member.joined_at,
        }
        for member, user in result.all()
    ]


async def is_channel_member(
    db: AsyncSession, channel_id: uuid.UUID, user_id: uuid.UUID
) -> bool:
    result = await db.execute(
        select(ChannelMember).where(
            ChannelMember.channel_id == channel_id,
            ChannelMember.user_id == user_id,
        )
    )
    return result.scalar_one_or_none() is not None


async def get_member_role(
    db: AsyncSession, channel_id: uuid.UUID, user_id: uuid.UUID
) -> str | None:
    """Return the user's role in a channel, or None if not a member."""
    result = await db.execute(
        select(ChannelMember.role_override).where(
            ChannelMember.channel_id == channel_id,
            ChannelMember.user_id == user_id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        # Check if member exists at all (role_override could be null = 'member')
        exists = await is_channel_member(db, channel_id, user_id)
        return "member" if exists else None
    return row.value if hasattr(row, 'value') else row


async def is_channel_admin(
    db: AsyncSession, channel_id: uuid.UUID, user_id: uuid.UUID
) -> bool:
    """Check if user is a channel admin."""
    role = await get_member_role(db, channel_id, user_id)
    return role == "admin"


async def is_channel_mod_or_admin(
    db: AsyncSession, channel_id: uuid.UUID, user_id: uuid.UUID
) -> bool:
    """Check if user is a channel admin or moderator."""
    role = await get_member_role(db, channel_id, user_id)
    return role in ("admin", "moderator")


async def set_member_role(
    db: AsyncSession, channel_id: uuid.UUID, user_id: uuid.UUID, role: str
) -> bool:
    """Set a member's per-channel role."""
    result = await db.execute(
        select(ChannelMember).where(
            ChannelMember.channel_id == channel_id,
            ChannelMember.user_id == user_id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        return False
    member.role_override = role
    await db.flush()
    return True


def _channel_to_dict(ch: Channel) -> dict:
    return {
        "id": ch.id,
        "name": ch.name,
        "description": ch.description,
        "category": ch.category,
        "is_private": ch.is_private,
        "created_by": ch.created_by,
        "created_at": ch.created_at,
        "archived": ch.archived,
    }
