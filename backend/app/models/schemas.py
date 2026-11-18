from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class CreateRoomRequest(BaseModel):
    host_name: str = Field(..., min_length=1, max_length=25)
    avatar: str = Field(default="avatar1")
    max_players: int = Field(default=6, ge=2, le=6)

class JoinRoomRequest(BaseModel):
    player_name: str = Field(..., min_length=1, max_length=25)
    avatar: str = Field(default="avatar1")

class UserAuthRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=30)
    avatar: str = Field(default="avatar1")

class ActionRequest(BaseModel):
    action: str  # "play", "draw", "call_uno", "catch_uno", "resolve_action"
    card_id: Optional[str] = None
    color: Optional[str] = None
    target_player_id: Optional[str] = None

class ChatPayload(BaseModel):
    message: str = Field(..., min_length=1, max_length=200)

