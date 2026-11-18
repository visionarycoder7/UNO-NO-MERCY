import json
import logging
import asyncio
from typing import Optional, Dict, Any
from backend.app.config import REDIS_URL

logger = logging.getLogger("uno.statestore")

class StateStore:
    def __init__(self):
        self._memory_rooms: Dict[str, Any] = {}
        self._memory_games: Dict[str, Any] = {}
        self._redis_client = None
        self._is_redis_ready = False
        self._lock = asyncio.Lock()
        self._init_redis()

    def _init_redis(self):
        if not REDIS_URL:
            logger.info("No REDIS_URL specified. Using in-memory state store.")
            return

        try:
            import redis
            client = redis.from_url(REDIS_URL, socket_connect_timeout=1, socket_timeout=1, decode_responses=True)
            # Ping test
            client.ping()
            self._redis_client = client
            self._is_redis_ready = True
            logger.info(f"Connected to Redis at {REDIS_URL}")
        except Exception as e:
            logger.info(f"Redis not reachable ({e}). Falling back to in-memory state store.")
            self._redis_client = None
            self._is_redis_ready = False

    async def save_room(self, room_code: str, room_data: dict, expire_seconds: int = 86400):
        room_code = room_code.upper()
        async with self._lock:
            self._memory_rooms[room_code] = room_data

        if self._is_redis_ready and self._redis_client:
            try:
                self._redis_client.setex(f"room:{room_code}", expire_seconds, json.dumps(room_data))
            except Exception as e:
                logger.warning(f"Redis save_room failed: {e}")

    async def get_room(self, room_code: str) -> Optional[dict]:
        room_code = room_code.upper()
        if self._is_redis_ready and self._redis_client:
            try:
                data = self._redis_client.get(f"room:{room_code}")
                if data:
                    return json.loads(data)
            except Exception as e:
                logger.warning(f"Redis get_room failed: {e}")

        async with self._lock:
            return self._memory_rooms.get(room_code)

    async def delete_room(self, room_code: str):
        room_code = room_code.upper()
        async with self._lock:
            self._memory_rooms.pop(room_code, None)
            self._memory_games.pop(room_code, None)

        if self._is_redis_ready and self._redis_client:
            try:
                self._redis_client.delete(f"room:{room_code}", f"game:{room_code}")
            except Exception as e:
                logger.warning(f"Redis delete_room failed: {e}")

    async def list_active_rooms(self) -> Dict[str, dict]:
        async with self._lock:
            return dict(self._memory_rooms)

# Global singleton instance
state_store = StateStore()

