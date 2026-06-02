import json
from collections import defaultdict

from fastapi import WebSocket


class ConnectionManager:
    """Room-based WebSocket manager keyed by conversation list id."""

    def __init__(self):
        self.rooms: dict[str, list[WebSocket]] = defaultdict(list)

    @staticmethod
    def room_key(chat_list_id: int) -> str:
        return f"chat_{chat_list_id}"

    @staticmethod
    def room_channel(chat_list_id: int) -> str:
        return f"chat:room:{chat_list_id}"

    async def connect(self, websocket: WebSocket, chat_list_id: int) -> None:
        await websocket.accept()
        self.rooms[self.room_key(chat_list_id)].append(websocket)

    def register(self, websocket: WebSocket, chat_list_id: int) -> None:
        """Register an already-accepted WebSocket without calling accept() again."""
        self.rooms[self.room_key(chat_list_id)].append(websocket)

    def disconnect(self, websocket: WebSocket, chat_list_id: int) -> None:
        key = self.room_key(chat_list_id)
        if websocket in self.rooms[key]:
            self.rooms[key].remove(websocket)
        if not self.rooms[key]:
            del self.rooms[key]

    async def broadcast(self, chat_list_id: int, payload: dict) -> None:
        from core.redis_client import get_redis
        message = json.dumps(payload)
        redis = get_redis()
        if redis is not None:
            await redis.publish(self.room_channel(chat_list_id), message)
        else:
            # Single-worker fallback when Redis is unavailable — send to every open connection.
            for ws in list(self.rooms.get(self.room_key(chat_list_id), [])):
                try:
                    await ws.send_text(message)
                except Exception:
                    self.disconnect(ws, chat_list_id)


manager = ConnectionManager()
