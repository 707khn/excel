import asyncio
from collections import defaultdict

from fastapi import WebSocket


class _ConnectedUser:
    __slots__ = ("ws", "user_id", "full_name")

    def __init__(self, ws: WebSocket, user_id: int, full_name: str):
        self.ws = ws
        self.user_id = user_id
        self.full_name = full_name


class CollabManager:
    def __init__(self):
        self._rooms: dict[int, list[_ConnectedUser]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def connect(self, file_id: int, ws: WebSocket, user_id: int, full_name: str) -> None:
        await ws.accept()
        async with self._lock:
            self._rooms[file_id].append(_ConnectedUser(ws, user_id, full_name))
        await self._broadcast_presence(file_id)

    async def disconnect(self, file_id: int, ws: WebSocket) -> None:
        async with self._lock:
            self._rooms[file_id] = [u for u in self._rooms[file_id] if u.ws is not ws]
            if not self._rooms[file_id]:
                del self._rooms[file_id]
        await self._broadcast_presence(file_id)

    async def broadcast(self, file_id: int, sender_ws: WebSocket, message: dict) -> None:
        dead = []
        for user in list(self._rooms.get(file_id, [])):
            if user.ws is not sender_ws:
                try:
                    await user.ws.send_json(message)
                except Exception:
                    dead.append(user.ws)
        for ws in dead:
            await self.disconnect(file_id, ws)

    async def _broadcast_presence(self, file_id: int) -> None:
        users = [u.full_name for u in self._rooms.get(file_id, [])]
        msg = {"type": "presence", "users": users}
        dead = []
        for user in list(self._rooms.get(file_id, [])):
            try:
                await user.ws.send_json(msg)
            except Exception:
                dead.append(user.ws)
        for ws in dead:
            await self.disconnect(file_id, ws)


collab_manager = CollabManager()
