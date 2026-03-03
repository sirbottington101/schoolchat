import uuid
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message
from app.models.user import User
from app.models.channel import ChannelMember
from app.services.encryption import get_encryption_service

enc = get_encryption_service()


async def get_message_by_id(
    db: AsyncSession, message_id: uuid.UUID
) -> Message | None:
    result = await db.execute(select(Message).where(Message.id == message_id))
    return result.scalar_one_or_none()


async def create_message(
    db: AsyncSession,
    channel_id: uuid.UUID,
    sender_id: uuid.UUID,
    content: str,
    reply_to: uuid.UUID | None = None,
) -> dict:
    ciphertext, nonce = enc.encrypt(content)

    msg = Message(
        channel_id=channel_id,
        sender_id=sender_id,
        ciphertext=ciphertext,
        nonce=nonce,
        reply_to=reply_to,
    )
    db.add(msg)
    await db.flush()

    sender = await db.execute(select(User).where(User.id == sender_id))
    sender_obj = sender.scalar_one_or_none()

    # Get channel role
    role_result = await db.execute(
        select(ChannelMember.role_override).where(
            ChannelMember.channel_id == channel_id,
            ChannelMember.user_id == sender_id,
        )
    )
    role_override = role_result.scalar_one_or_none()
    role = role_override.value if role_override and hasattr(role_override, 'value') else (role_override or "member")

    return {
        "id": msg.id,
        "channel_id": msg.channel_id,
        "sender_id": msg.sender_id,
        "sender_name": sender_obj.display_name if sender_obj else None,
        "sender_role": role,
        "content": content,
        "reply_to": msg.reply_to,
        "created_at": msg.created_at,
        "edited_at": msg.edited_at,
    }


async def get_messages(
    db: AsyncSession,
    channel_id: uuid.UUID,
    before: datetime | None = None,
    limit: int = 50,
) -> list[dict]:
    stmt = (
        select(Message, User, ChannelMember.role_override)
        .outerjoin(User, Message.sender_id == User.id)
        .outerjoin(ChannelMember, (ChannelMember.channel_id == Message.channel_id) & (ChannelMember.user_id == Message.sender_id))
        .where(
            Message.channel_id == channel_id,
            Message.is_deleted == False,
        )
    )

    if before:
        stmt = stmt.where(Message.created_at < before)

    stmt = stmt.order_by(Message.created_at.desc()).limit(limit)

    result = await db.execute(stmt)
    rows = result.all()

    messages = []
    for msg, user, role_override in reversed(rows):
        try:
            plaintext = enc.decrypt(msg.ciphertext, msg.nonce)
        except Exception:
            plaintext = "[decryption error]"

        role = role_override.value if role_override and hasattr(role_override, 'value') else (role_override or "member")

        messages.append({
            "id": msg.id,
            "channel_id": msg.channel_id,
            "sender_id": msg.sender_id,
            "sender_name": user.display_name if user else None,
            "sender_role": role,
            "content": plaintext,
            "reply_to": msg.reply_to,
            "created_at": msg.created_at,
            "edited_at": msg.edited_at,
        })

    return messages


async def edit_message(
    db: AsyncSession,
    message_id: uuid.UUID,
    user_id: uuid.UUID,
    new_content: str,
) -> dict | None:
    result = await db.execute(select(Message).where(Message.id == message_id))
    msg = result.scalar_one_or_none()

    if msg is None or msg.sender_id != user_id:
        return None

    ciphertext, nonce = enc.encrypt(new_content)
    msg.ciphertext = ciphertext
    msg.nonce = nonce
    msg.edited_at = datetime.now(timezone.utc)
    await db.flush()

    sender = await db.execute(select(User).where(User.id == user_id))
    sender_obj = sender.scalar_one_or_none()

    return {
        "id": msg.id,
        "channel_id": msg.channel_id,
        "sender_id": msg.sender_id,
        "sender_name": sender_obj.display_name if sender_obj else None,
        "content": new_content,
        "reply_to": msg.reply_to,
        "created_at": msg.created_at,
        "edited_at": msg.edited_at,
    }


async def delete_message(
    db: AsyncSession,
    message_id: uuid.UUID,
    user_id: uuid.UUID,
    is_admin: bool = False,
) -> bool:
    result = await db.execute(select(Message).where(Message.id == message_id))
    msg = result.scalar_one_or_none()

    if msg is None:
        return False
    if msg.sender_id != user_id and not is_admin:
        return False

    msg.is_deleted = True
    await db.flush()
    return True


async def search_messages(
    db: AsyncSession,
    channel_id: uuid.UUID,
    query: str,
    limit: int = 20,
) -> list[dict]:
    stmt = (
        select(Message, User, ChannelMember.role_override)
        .outerjoin(User, Message.sender_id == User.id)
        .outerjoin(ChannelMember, (ChannelMember.channel_id == Message.channel_id) & (ChannelMember.user_id == Message.sender_id))
        .where(
            Message.channel_id == channel_id,
            Message.is_deleted == False,
        )
        .order_by(Message.created_at.desc())
        .limit(500)
    )
    result = await db.execute(stmt)
    rows = result.all()

    query_lower = query.lower()
    matches = []

    for msg, user, role_override in rows:
        try:
            plaintext = enc.decrypt(msg.ciphertext, msg.nonce)
        except Exception:
            continue

        if query_lower in plaintext.lower():
            role = role_override.value if role_override and hasattr(role_override, 'value') else (role_override or "member")
            matches.append({
                "id": msg.id,
                "channel_id": msg.channel_id,
                "sender_id": msg.sender_id,
                "sender_name": user.display_name if user else None,
                "sender_role": role,
                "content": plaintext,
                "reply_to": msg.reply_to,
                "created_at": msg.created_at,
                "edited_at": msg.edited_at,
            })

        if len(matches) >= limit:
            break

    return matches
