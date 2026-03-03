"""
WebSocket endpoint and message handler.

Clients connect with: ws://host/ws?token=<JWT>
After connecting, they send JSON messages to interact in real-time.
"""

import uuid
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.services.auth_service import decode_token, get_user_by_id
from app.services import channel_service, message_service
from app.websocket.manager import manager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
    """
    Main WebSocket endpoint.
    Authenticate via JWT in query param, then process messages.
    """
    # ── Authenticate ──
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            await websocket.close(code=4001, reason="Invalid token type")
            return
        user_id = uuid.UUID(payload["sub"])
    except Exception:
        await websocket.close(code=4001, reason="Invalid token")
        return

    # Look up user
    async with AsyncSessionLocal() as db:
        user = await get_user_by_id(db, user_id)
        if user is None:
            await websocket.close(code=4001, reason="User not found")
            return
        username = user.display_name or user.username

    # ── Connect ──
    await manager.connect(websocket, user_id, username)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "type": "error", "detail": "Invalid JSON"
                }))
                continue

            msg_type = data.get("type", "")
            await _handle_message(websocket, user_id, username, data, msg_type)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error for {user_id}: {e}")
    finally:
        await manager.disconnect(websocket, user_id)


async def _handle_message(
    websocket: WebSocket,
    user_id: uuid.UUID,
    username: str,
    data: dict,
    msg_type: str,
):
    if msg_type == "channel.subscribe":
        await _handle_subscribe(websocket, user_id, data)

    elif msg_type == "channel.unsubscribe":
        channel_id = uuid.UUID(data["channel_id"])
        manager.unsubscribe_from_channel(user_id, channel_id)

    elif msg_type == "message.send":
        await _handle_send_message(websocket, user_id, username, data)

    elif msg_type == "typing.start":
        await _handle_typing(user_id, username, data)

    elif msg_type == "typing.stop":
        await _handle_typing(user_id, username, data, started=False)

    else:
        await websocket.send_text(json.dumps({
            "type": "error", "detail": f"Unknown message type: {msg_type}"
        }))


async def _handle_subscribe(websocket: WebSocket, user_id: uuid.UUID, data: dict):
    """Subscribe to a channel's real-time messages."""
    channel_id = uuid.UUID(data["channel_id"])

    # Verify membership
    async with AsyncSessionLocal() as db:
        is_member = await channel_service.is_channel_member(db, channel_id, user_id)
        if not is_member:
            await websocket.send_text(json.dumps({
                "type": "error", "detail": "Not a member of this channel"
            }))
            return

    manager.subscribe_to_channel(user_id, channel_id)
    await websocket.send_text(json.dumps({
        "type": "channel.subscribed", "channel_id": str(channel_id)
    }))


async def _handle_send_message(
    websocket: WebSocket,
    user_id: uuid.UUID,
    username: str,
    data: dict,
):
    """Receive a message, persist it, and broadcast to channel subscribers."""
    channel_id = uuid.UUID(data["channel_id"])
    content = data.get("content", "").strip()
    reply_to = data.get("reply_to")

    if not content:
        await websocket.send_text(json.dumps({
            "type": "error", "detail": "Empty message"
        }))
        return

    if len(content) > 4000:
        await websocket.send_text(json.dumps({
            "type": "error", "detail": "Message too long (max 4000 chars)"
        }))
        return

    reply_to_uuid = uuid.UUID(reply_to) if reply_to else None

    # Persist
    async with AsyncSessionLocal() as db:
        is_member = await channel_service.is_channel_member(db, channel_id, user_id)
        if not is_member:
            await websocket.send_text(json.dumps({
                "type": "error", "detail": "Not a member of this channel"
            }))
            return

        msg_data = await message_service.create_message(
            db, channel_id, user_id, content, reply_to_uuid
        )
        await db.commit()

    # Build broadcast payload
    broadcast = {
        "type": "message.new",
        "id": str(msg_data["id"]),
        "channel_id": str(msg_data["channel_id"]),
        "sender_id": str(msg_data["sender_id"]),
        "sender_name": msg_data["sender_name"],
        "sender_role": msg_data.get("sender_role", "member"),
        "content": msg_data["content"],
        "reply_to": str(msg_data["reply_to"]) if msg_data["reply_to"] else None,
        "created_at": msg_data["created_at"].isoformat() if msg_data["created_at"] else None,
        "edited_at": None,
    }

    # Broadcast to all subscribers (including sender for confirmation)
    await manager.broadcast_to_channel(channel_id, broadcast)


async def _handle_typing(
    user_id: uuid.UUID, username: str, data: dict, started: bool = True
):
    channel_id = uuid.UUID(data["channel_id"])
    await manager.broadcast_to_channel(
        channel_id,
        {
            "type": "typing.start" if started else "typing.stop",
            "channel_id": str(channel_id),
            "user_id": str(user_id),
            "username": username,
        },
        exclude_user=user_id,
    )
