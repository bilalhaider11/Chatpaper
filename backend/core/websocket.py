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

    async def connect(self, websocket: WebSocket, chat_list_id: int) -> None:
        await websocket.accept()
        self.rooms[self.room_key(chat_list_id)].append(websocket)


    def disconnect(self, websocket: WebSocket, chat_list_id: int) -> None:
        key = self.room_key(chat_list_id)
        if websocket in self.rooms[key]:
            self.rooms[key].remove(websocket)
        if not self.rooms[key]:
            del self.rooms[key]


    async def broadcast(self, chat_list_id: int, payload: dict) -> None:
        message = json.dumps(payload)
        connections = self.rooms.get(self.room_key(chat_list_id), [])
        
        if connections:
            connection = connections[0]  # Grab the only user
            try:
                await connection.send_text(message)
            except Exception:
                self.disconnect(connection, chat_list_id)



manager = ConnectionManager()
