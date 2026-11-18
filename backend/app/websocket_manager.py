import json
import logging
from typing import Dict
from fastapi import WebSocket

logger = logging.getLogger("uno.websocket")

class WebSocketManager:
    def __init__(self):
        # room_code -> { player_id -> WebSocket }
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}

    async def connect(self, room_code: str, player_id: str, websocket: WebSocket):
        await websocket.accept()
        room_code = room_code.strip().upper()
        if room_code not in self.active_connections:
            self.active_connections[room_code] = {}

        old_ws = self.active_connections[room_code].get(player_id)
        self.active_connections[room_code][player_id] = websocket
        logger.info(f"WebSocket connected: player {player_id} in room {room_code}")

        if old_ws and old_ws != websocket:
            try:
                await old_ws.close()
            except Exception:
                pass

    def disconnect(self, room_code: str, player_id: str, websocket: WebSocket = None):
        room_code = room_code.strip().upper()
        if room_code in self.active_connections:
            if player_id in self.active_connections[room_code]:
                # Only remove if it matches the socket being disconnected
                if websocket is None or self.active_connections[room_code][player_id] == websocket:
                    del self.active_connections[room_code][player_id]
            if not self.active_connections[room_code]:
                del self.active_connections[room_code]
        logger.info(f"WebSocket disconnected: player {player_id} from room {room_code}")

    async def send_to_player(self, room_code: str, player_id: str, data: dict):
        room_code = room_code.strip().upper()
        if room_code in self.active_connections and player_id in self.active_connections[room_code]:
            ws = self.active_connections[room_code][player_id]
            try:
                await ws.send_text(json.dumps(data))
            except Exception as e:
                logger.warning(f"Error sending to player {player_id}: {e}")

    async def broadcast_to_room(self, room_code: str, data: dict, exclude_player_id: str = None):
        room_code = room_code.strip().upper()
        if room_code not in self.active_connections:
            return

        connections = list(self.active_connections[room_code].items())
        text_data = json.dumps(data)
        for pid, ws in connections:
            if exclude_player_id and pid == exclude_player_id:
                continue
            try:
                await ws.send_text(text_data)
            except Exception as e:
                logger.warning(f"Error broadcasting to {pid} in room {room_code}: {e}")

    async def broadcast_game_state(self, room):
        if not room.game:
            return

        room_code = room.code.strip().upper()
        for p in room.players:
            pid = p["id"]
            if p.get("is_ai"):
                continue  # AI doesn't need WebSocket frames
            player_view = room.game.get_player_view(pid)
            await self.send_to_player(room_code, pid, {
                "type": "game_state",
                "state": player_view
            })

ws_manager = WebSocketManager()
