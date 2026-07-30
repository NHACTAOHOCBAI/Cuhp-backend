from fastapi import WebSocket
from typing import Dict, List
from loguru import logger

class ConnectionManager:
    def __init__(self):
        # user_id -> list of active WebSockets
        self.active_connections: Dict[str, List[WebSocket]] = {}
        # user_id -> user role ("admin" | "user")
        self.user_roles: Dict[str, str] = {}

    async def connect(self, websocket: WebSocket, user_id: str, role: str):
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        self.user_roles[user_id] = role
        logger.info(f"User {user_id} ({role}) connected via WebSocket. Active connections for user: {len(self.active_connections[user_id])}")

    def disconnect(self, websocket: WebSocket, user_id: str):
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
                logger.info(f"Removed WebSocket connection for user {user_id}")
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
                if user_id in self.user_roles:
                    del self.user_roles[user_id]
                logger.info(f"Cleaned up all connections and roles for user {user_id}")

    async def send_personal_message(self, message: dict, user_id: str):
        if user_id in self.active_connections:
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error sending message to user {user_id}: {e}")

    async def broadcast_to_room(self, room_id: str, room_user_id: str, payload: dict):
        """
        Broadcasts a message payload to:
        1. The user who owns the room (room_user_id)
        2. All connected administrators
        """
        targets = set()
        
        # Add room owner if connected
        if room_user_id:
            targets.add(room_user_id)
            
        # Add all connected admins
        for uid, role in self.user_roles.items():
            if role == "admin":
                targets.add(uid)
                
        logger.debug(f"Broadcasting to room {room_id} (owner: {room_user_id}). Targets: {targets}")
        
        for user_id in targets:
            await self.send_personal_message(payload, user_id)

    async def broadcast_room_update(self, room_id: str, room_user_id: str, payload: dict):
        """
        Broadcasts a room update metadata payload to:
        1. The user who owns the room (room_user_id)
        2. All connected administrators
        """
        await self.broadcast_to_room(room_id, room_user_id, payload)

manager = ConnectionManager()
