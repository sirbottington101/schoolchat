"""
WebSocket connection manager.

Tracks connected clients, routes messages to channel subscribers,
and manages presence updates.
"""

import uuid
import json
import logging
from datetime import datetime, timezone
from fastapi import WebSocket
from collections import defaultdict

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        # user_id -> list of WebSocket connections (supports multiple tabs/devices)
        self._connections: dict[uuid.UUID, list[WebSocket]] = defaultdict(list)
        # channel_id -> set of user_ids currently subscribed
        self._channel_subscribers: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
        # user_id -> username (for presence broadcasts)
        self._user_names: dict[uuid.UUID, str] = {}

    async def connect(self, websocket: WebSocket, user_id: uuid.UUID, username: str):
        await websocket.accept()
        self._connections[user_id].append(websocket)
        self._user_names[user_id] = username
        logger.info(f"User {username} ({user_id}) connected. Total connections: {self._total_connections()}")

        # Broadcast presence
        await self._broadcast_presence(user_id, "online")

    async def disconnect(self, websocket: WebSocket, user_id: uuid.UUID):
        if user_id in self._connections:
            self._connections[user_id] = [
                ws for ws in self._connections[user_id] if ws != websocket
            ]
            if not self._connections[user_id]:
                del self._connections[user_id]
                # Remove from all channel subscriptions
                for subs in self._channel_subscribers.values():
                    subs.discard(user_id)
                username = self._user_names.pop(user_id, "unknown")
                logger.info(f"User {username} ({user_id}) fully disconnected")
                await self._broadcast_presence(user_id, "offline")

    def subscribe_to_channel(self, user_id: uuid.UUID, channel_id: uuid.UUID):
        self._channel_subscribers[channel_id].add(user_id)

    def unsubscribe_from_channel(self, user_id: uuid.UUID, channel_id: uuid.UUID):
        self._channel_subscribers[channel_id].discard(user_id)

    async def broadcast_to_channel(self, channel_id: uuid.UUID, message: dict, exclude_user: uuid.UUID | None = None):
        """Send a message to all users subscribed to a channel."""
        subscriber_ids = self._channel_subscribers.get(channel_id, set())
        payload = json.dumps(message, default=str)

        for user_id in subscriber_ids:
            if user_id == exclude_user:
                continue
            await self._send_to_user(user_id, payload)

    async def send_to_user(self, user_id: uuid.UUID, message: dict):
        payload = json.dumps(message, default=str)
        await self._send_to_user(user_id, payload)

    async def _send_to_user(self, user_id: uuid.UUID, payload: str):
        connections = self._connections.get(user_id, [])
        dead = []
        for ws in connections:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        # Clean up dead connections
        for ws in dead:
            self._connections[user_id] = [
                c for c in self._connections[user_id] if c != ws
            ]

    async def _broadcast_presence(self, user_id: uuid.UUID, status: str):
        message = {
            "type": "presence.update",
            "user_id": str(user_id),
            "username": self._user_names.get(user_id, "unknown"),
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        payload = json.dumps(message)
        # Send to all connected users
        for uid, connections in self._connections.items():
            for ws in connections:
                try:
                    await ws.send_text(payload)
                except Exception:
                    pass

    def get_online_user_ids(self) -> list[uuid.UUID]:
        return list(self._connections.keys())

    def _total_connections(self) -> int:
        return sum(len(conns) for conns in self._connections.values())


# Singleton manager
manager = ConnectionManager()
