"""WebSocket connection manager for real-time notifications, chat and the live workforce feed."""
import asyncio
from collections import defaultdict
from typing import Optional
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.users: dict[int, set[WebSocket]] = defaultdict(set)
        self.roles: dict[int, str] = {}
        self.loop: Optional[asyncio.AbstractEventLoop] = None

    async def connect(self, ws: WebSocket, user_id: int, role: str):
        await ws.accept()
        self.users[user_id].add(ws)
        self.roles[user_id] = role

    def disconnect(self, ws: WebSocket, user_id: int):
        self.users[user_id].discard(ws)
        if not self.users[user_id]:
            self.users.pop(user_id, None)
            self.roles.pop(user_id, None)

    def online_user_ids(self) -> list[int]:
        return list(self.users.keys())

    async def _send(self, ws: WebSocket, data: dict):
        try:
            await ws.send_json(data)
        except Exception:
            pass

    async def send_to_user(self, user_id: int, data: dict):
        for ws in list(self.users.get(user_id, [])):
            await self._send(ws, data)

    async def send_to_roles(self, roles: tuple, data: dict):
        for uid, role in list(self.roles.items()):
            if role in roles:
                await self.send_to_user(uid, data)

    # --- thread-safe publishers, callable from sync (threadpool) endpoints ---
    def _run(self, coro):
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(coro, self.loop)
        else:
            coro.close()

    def publish_user(self, user_id: int, data: dict):
        self._run(self.send_to_user(user_id, data))

    def publish_roles(self, roles: tuple, data: dict):
        self._run(self.send_to_roles(roles, data))


manager = ConnectionManager()
