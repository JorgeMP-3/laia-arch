from __future__ import annotations

import json
import logging
import threading
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger("agora.ws")

EventPayload = dict[str, Any]


class ConnectionManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._connections: dict[str, list[WebSocket]] = {}

    async def connect(self, ws: WebSocket, user_id: str) -> None:
        await ws.accept()
        with self._lock:
            self._connections.setdefault(user_id, []).append(ws)
        logger.info("ws connect user=%s total=%d", user_id, self.user_count())

    async def disconnect(self, ws: WebSocket, user_id: str) -> None:
        with self._lock:
            conns = self._connections.get(user_id, [])
            if ws in conns:
                conns.remove(ws)
            if not conns:
                self._connections.pop(user_id, None)
        logger.info("ws disconnect user=%s total=%d", user_id, self.user_count())

    async def send_json(self, ws: WebSocket, data: EventPayload) -> bool:
        try:
            await ws.send_json(data)
            return True
        except Exception:
            return False

    async def send_to_user(self, user_id: str, data: EventPayload) -> int:
        sent = 0
        with self._lock:
            conns = list(self._connections.get(user_id, []))
        for ws in conns:
            if await self.send_json(ws, data):
                sent += 1
        return sent

    async def send_to_roles(self, roles: set[str], store, data: EventPayload) -> int:
        sent = 0
        users = store.users()
        target_ids = {u.id for u in users if u.role in roles}
        for uid in target_ids:
            sent += await self.send_to_user(uid, data)
        return sent

    async def broadcast_event(self, event_type: str, payload: EventPayload,
                              target_user: str | None = None,
                              target_roles: set[str] | None = None) -> dict[str, int]:
        event = {
            "type": event_type,
            "payload": payload,
        }
        sent = 0
        admins_sent = 0
        if target_user:
            sent = await self.send_to_user(target_user, event)
        if target_roles:
            from .storage import store
            admins_sent = await self.send_to_roles(target_roles, store, event)
        if sent > 0 or admins_sent > 0:
            logger.info("ws event %s sent=%d roles=%d", event_type, sent, admins_sent)
        return {"user_sent": sent, "roles_sent": admins_sent}

    def user_count(self) -> int:
        with self._lock:
            return sum(len(v) for v in self._connections.values())

    def connected_users(self) -> list[str]:
        with self._lock:
            return sorted(self._connections.keys())


ws_manager = ConnectionManager()
