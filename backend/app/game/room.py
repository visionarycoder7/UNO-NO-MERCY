import secrets
import string
import time
from typing import List, Dict, Any, Optional, Tuple
from backend.app.game.engine import UnoNoMercyGame
from backend.app.config import MIN_PLAYERS, MAX_PLAYERS
from backend.app.storage.state_store import state_store

class Room:
    def __init__(self, code: str, host_id: str, host_name: str, avatar: str = "avatar1", max_players: int = 6):
        self.code = code.upper()
        self.host_id = host_id
        self.host_name = host_name
        self.max_players = max(MIN_PLAYERS, min(MAX_PLAYERS, max_players))
        self.created_at = time.time()
        self.status = "waiting"  # "waiting", "in_progress", "finished"
        self.players: List[Dict[str, Any]] = [
            {
                "id": host_id,
                "name": host_name,
                "avatar": avatar,
                "is_host": True,
                "is_ready": True,  # Host is ready by default
                "connected": True
            }
        ]
        self.game: Optional[UnoNoMercyGame] = None
        self.chat_messages: List[Dict[str, Any]] = []

    def to_summary_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "host_name": self.host_name,
            "player_count": len(self.players),
            "max_players": self.max_players,
            "status": self.status,
            "created_at": self.created_at
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "host_id": self.host_id,
            "host_name": self.host_name,
            "max_players": self.max_players,
            "status": self.status,
            "players": self.players,
            "can_start": self.can_start()[0],
            "created_at": self.created_at,
            "chat_messages": self.chat_messages[-30:]
        }

    def add_player(self, player_id: str, player_name: str, avatar: str = "avatar1") -> Dict[str, Any]:
        if self.status != "waiting":
            return {"success": False, "error": "Game is already in progress or completed."}

        # Check if already joined (e.g. reconnecting)
        existing = next((p for p in self.players if p["id"] == player_id), None)
        if existing:
            existing["connected"] = True
            existing["name"] = player_name
            existing["avatar"] = avatar
            return {"success": True, "reconnected": True}

        if len(self.players) >= self.max_players:
            return {"success": False, "error": f"Room is full (max {self.max_players} players)."}

        # Disallow duplicate names within room
        if any(p["name"].lower() == player_name.lower() for p in self.players):
            # Append random suffix if name collision
            player_name = f"{player_name}_{secrets.randbelow(999)}"

        new_player = {
            "id": player_id,
            "name": player_name,
            "avatar": avatar,
            "is_host": False,
            "is_ready": False,
            "connected": True
        }
        self.players.append(new_player)
        self.add_system_chat(f"👋 {player_name} joined the room.")
        return {"success": True, "player": new_player}

    def remove_player(self, player_id: str) -> Dict[str, Any]:
        idx = next((i for i, p in enumerate(self.players) if p["id"] == player_id), None)
        if idx is None:
            return {"success": False, "error": "Player not in room."}

        leaving_player = self.players.pop(idx)
        self.add_system_chat(f"🚪 {leaving_player['name']} left the room.")

        # If game is in progress, eliminate player
        if self.game and not self.game.game_over:
            g_player = next((p for p in self.game.players if p["id"] == player_id), None)
            if g_player:
                self.game._eliminate_player(g_player, reason="Abandoned Game")

        # Reassign host if host left
        if leaving_player["is_host"] and self.players:
            self.players[0]["is_host"] = True
            self.players[0]["is_ready"] = True
            self.host_id = self.players[0]["id"]
            self.host_name = self.players[0]["name"]
            self.add_system_chat(f"👑 {self.host_name} is now the host.")

        return {"success": True, "remaining_players": len(self.players)}

    def toggle_ready(self, player_id: str) -> Dict[str, Any]:
        player = next((p for p in self.players if p["id"] == player_id), None)
        if not player:
            return {"success": False, "error": "Player not found."}

        if player["is_host"]:
            player["is_ready"] = True
            return {"success": True, "is_ready": True}

        player["is_ready"] = not player["is_ready"]
        return {"success": True, "is_ready": player["is_ready"]}

    def can_start(self) -> Tuple[bool, str]:
        if len(self.players) < MIN_PLAYERS:
            return False, f"Need at least {MIN_PLAYERS} players to start."
        if not all(p["is_ready"] for p in self.players):
            return False, "Not all players are ready."
        return True, "Ready to start."

    def start_game(self, requesting_player_id: str) -> Dict[str, Any]:
        if requesting_player_id != self.host_id:
            return {"success": False, "error": "Only the host can start the game."}

        can, reason = self.can_start()
        if not can:
            return {"success": False, "error": reason}

        self.status = "in_progress"
        self.game = UnoNoMercyGame(
            room_code=self.code,
            players_info=[{"id": p["id"], "name": p["name"], "avatar": p["avatar"]} for p in self.players]
        )
        self.add_system_chat("🔥 The match has begun! Show 'Em NO MERCY! 🔥")
        return {"success": True}

    def add_chat(self, player_id: str, player_name: str, text: str):
        msg = {
            "sender_id": player_id,
            "sender_name": player_name,
            "text": text,
            "timestamp": time.time(),
            "is_system": False
        }
        self.chat_messages.append(msg)
        if len(self.chat_messages) > 60:
            self.chat_messages.pop(0)
        return msg

    def add_system_chat(self, text: str):
        msg = {
            "sender_id": "system",
            "sender_name": "Game",
            "text": text,
            "timestamp": time.time(),
            "is_system": True
        }
        self.chat_messages.append(msg)
        if len(self.chat_messages) > 60:
            self.chat_messages.pop(0)
        return msg


class RoomManager:
    def __init__(self):
        self.rooms: Dict[str, Room] = {}

    def _generate_unique_code(self) -> str:
        chars = string.ascii_uppercase + string.digits
        # Avoid confusing characters like O, 0, I, 1
        filtered_chars = "".join([c for c in chars if c not in "OI01"])
        for _ in range(100):
            code = "".join(secrets.choice(filtered_chars) for _ in range(6))
            if code not in self.rooms:
                return code
        return secrets.token_hex(3).upper()

    async def create_room(self, host_id: str, host_name: str, avatar: str = "avatar1", max_players: int = 6) -> Room:
        code = self._generate_unique_code()
        room = Room(code=code, host_id=host_id, host_name=host_name, avatar=avatar, max_players=max_players)
        self.rooms[code] = room
        await state_store.save_room(code, room.to_dict())
        return room

    async def get_room(self, room_code: str) -> Optional[Room]:
        code = room_code.upper()
        return self.rooms.get(code)

    async def delete_room(self, room_code: str):
        code = room_code.upper()
        if code in self.rooms:
            del self.rooms[code]
        await state_store.delete_room(code)

    async def list_available_rooms(self) -> List[Dict[str, Any]]:
        return [
            room.to_summary_dict()
            for room in self.rooms.values()
            if room.status == "waiting" and len(room.players) < room.max_players
        ]

room_manager = RoomManager()
