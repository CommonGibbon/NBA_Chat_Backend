import asyncio 
from typing import Dict, Set
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        # Map chat _id -> set of WebSocket connections, each websocket connection represents a client (e.g. ios app)
        self.connections: Dict[str, Set[WebSocket]] = {}
        self.lock = asyncio.Lock()

    async def connect(self, chat_id:str, websocket: WebSocket):
        """Add a websocket connection to a chat."""
        async with self.lock:
            if chat_id not in self.connections:
                self.connections[chat_id] = set()
            self.connections[chat_id].add(websocket)

    async def disconnect(self, chat_id: str, websocket: WebSocket):
        """Remove a websocket connection from a chat."""
        async with self.lock:
            if chat_id in self.connections:
                self.connections[chat_id].discard(websocket)
                # clean up empty sets
                if not self.connections[chat_id]:
                    del self.connections[chat_id]

    async def send_to_chat(self, chat_id: str, message_dict: dict):
        """Broadcast a message to all connections on a chat."""
        async with self.lock:
            if chat_id not in self.connections:
                return
            
            broken = set()
            for websocket in self.connections[chat_id]:
                try:
                    await websocket.send_json(message_dict)
                except Exception:
                    # Mark broken connections for removal
                    broken.add(websocket)
            # remove broken connections
            for websocket in broken:
                self.connections[chat_id].discard(websocket)
                if not self.connections[chat_id]:
                    del self.connections[chat_id]
