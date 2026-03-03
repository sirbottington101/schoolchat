from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas import (
    ChannelCreate, ChannelUpdate, ChannelOut, ChannelMemberOut,
    AddMemberRequest, MessageOut, MessageSend, MessageEdit,
    SetChannelRoleRequest,
)
from app.services import channel_service, message_service
from app.websocket.manager import manager

router = APIRouter(prefix="/api/channels", tags=["channels"])


# ─────────────────── Channel CRUD ───────────────────

@router.get("", response_model=list[ChannelOut])
async def list_channels(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await channel_service.get_channels_for_user(db, user.id)


@router.post("", response_model=ChannelOut, status_code=status.HTTP_201_CREATED)
async def create_channel(
    req: ChannelCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Any user can create a channel; creator becomes channel admin."""
    channel = await channel_service.create_channel(
        db, name=req.name, created_by=user.id,
        description=req.description, category=req.category, is_private=req.is_private,
    )
    return {**channel_service._channel_to_dict(channel), "member_count": 1}


@router.patch("/{channel_id}", response_model=ChannelOut)
async def update_channel(
    channel_id: UUID, req: ChannelUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not await channel_service.is_channel_admin(db, channel_id, user.id):
        raise HTTPException(status_code=403, detail="Channel admin access required")
    channel = await channel_service.get_channel_by_id(db, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    updated = await channel_service.update_channel(
        db, channel, **req.model_dump(exclude_unset=True)
    )
    return updated


# ─────────────────── Members ───────────────────

@router.get("/{channel_id}/members", response_model=list[ChannelMemberOut])
async def list_members(
    channel_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not await channel_service.is_channel_member(db, channel_id, user.id):
        raise HTTPException(status_code=403, detail="Not a member")
    return await channel_service.get_channel_members(db, channel_id)


@router.post("/{channel_id}/members", status_code=status.HTTP_201_CREATED)
async def add_member(
    channel_id: UUID, req: AddMemberRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not await channel_service.is_channel_admin(db, channel_id, user.id):
        raise HTTPException(status_code=403, detail="Channel admin access required")
    channel = await channel_service.get_channel_by_id(db, channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    try:
        await channel_service.add_member(db, channel_id, req.user_id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    # Notify the added user via WebSocket to refresh their channel list
    await manager.send_to_user(req.user_id, {
        "type": "channel.added",
        "channel_id": str(channel_id),
        "channel_name": channel.name,
    })
    # Notify existing subscribers to refresh member list
    await manager.broadcast_to_channel(channel_id, {
        "type": "channel.member_update",
        "channel_id": str(channel_id),
    })
    return {"status": "ok"}


@router.delete("/{channel_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    channel_id: UUID, user_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user_id != user.id:
        if not await channel_service.is_channel_admin(db, channel_id, user.id):
            raise HTTPException(status_code=403, detail="Channel admin access required")
    removed = await channel_service.remove_member(db, channel_id, user_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Member not found")
    # Notify the removed user to refresh their channel list
    await manager.send_to_user(user_id, {
        "type": "channel.removed",
        "channel_id": str(channel_id),
    })
    # Notify remaining subscribers to refresh member list
    await manager.broadcast_to_channel(channel_id, {
        "type": "channel.member_update",
        "channel_id": str(channel_id),
    })


@router.patch("/{channel_id}/members/{user_id}/role")
async def set_member_role(
    channel_id: UUID, user_id: UUID,
    req: SetChannelRoleRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Channel admin can set per-channel roles for members."""
    if not await channel_service.is_channel_admin(db, channel_id, user.id):
        raise HTTPException(status_code=403, detail="Channel admin access required")
    if user_id == user.id:
        raise HTTPException(status_code=400, detail="Cannot change your own role")
    success = await channel_service.set_member_role(db, channel_id, user_id, req.role)
    if not success:
        raise HTTPException(status_code=404, detail="Member not found")
    # Notify channel subscribers to refresh member list
    await manager.broadcast_to_channel(channel_id, {
        "type": "channel.member_update",
        "channel_id": str(channel_id),
    })
    return {"status": "ok", "user_id": str(user_id), "new_role": req.role}


# ─────────────────── Messages ───────────────────

@router.get("/{channel_id}/messages", response_model=list[MessageOut])
async def get_messages(
    channel_id: UUID,
    before: datetime | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not await channel_service.is_channel_member(db, channel_id, user.id):
        raise HTTPException(status_code=403, detail="Not a member of this channel")
    return await message_service.get_messages(db, channel_id, before, limit)


@router.post("/{channel_id}/messages", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
async def send_message(
    channel_id: UUID, req: MessageSend,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not await channel_service.is_channel_member(db, channel_id, user.id):
        raise HTTPException(status_code=403, detail="Not a member of this channel")
    return await message_service.create_message(
        db, channel_id, user.id, req.content, req.reply_to
    )


@router.patch("/messages/{message_id}", response_model=MessageOut)
async def edit_message(
    message_id: UUID, req: MessageEdit,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await message_service.edit_message(db, message_id, user.id, req.content)
    if result is None:
        raise HTTPException(status_code=404, detail="Message not found or not yours")
    return result


@router.delete("/messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message(
    message_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    msg = await message_service.get_message_by_id(db, message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    is_own = msg.sender_id == user.id
    is_ch_mod = await channel_service.is_channel_mod_or_admin(db, msg.channel_id, user.id)
    if not is_own and not is_ch_mod:
        raise HTTPException(status_code=403, detail="Cannot delete this message")
    await message_service.delete_message(db, message_id, user.id, is_ch_mod)


@router.get("/{channel_id}/search", response_model=list[MessageOut])
async def search_messages(
    channel_id: UUID,
    q: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not await channel_service.is_channel_member(db, channel_id, user.id):
        raise HTTPException(status_code=403, detail="Not a member of this channel")
    return await message_service.search_messages(db, channel_id, q, limit)
