import os
import json
import uuid
import time
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from sqlalchemy.orm import Session

from backend.app.config import MIN_PLAYERS, MAX_PLAYERS
from backend.app.storage.database import SessionLocal, get_db, get_or_create_user, record_match_result, get_leaderboard, get_recent_matches
from backend.app.game.room import room_manager
from backend.app.websocket_manager import ws_manager
from backend.app.models.schemas import CreateRoomRequest, JoinRoomRequest, UserAuthRequest

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("uno.main")

app = FastAPI(title="UNO Show 'Em No Mercy API")

# Enable CORS for cross-origin or local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------- REST Endpoints ----------------- #

@app.post("/api/auth/login")
def login(request: UserAuthRequest, db: Session = Depends(get_db)):
    user = get_or_create_user(db, request.username, request.avatar)
    return {
        "success": True,
        "user": user.to_dict(),
        "token": f"user_{user.id}_{uuid.uuid4().hex[:8]}"
    }

@app.get("/api/leaderboard")
def leaderboard(db: Session = Depends(get_db)):
    users = get_leaderboard(db, limit=10)
    return {"leaderboard": [u.to_dict() for u in users]}

@app.get("/api/history")
def history(db: Session = Depends(get_db)):
    matches = get_recent_matches(db, limit=10)
    return {"history": [m.to_dict() for m in matches]}

@app.post("/api/rooms")
async def create_room(request: CreateRoomRequest):
    host_id = f"player_{uuid.uuid4().hex[:8]}"
    room = await room_manager.create_room(
        host_id=host_id,
        host_name=request.host_name.strip(),
        avatar=request.avatar,
        max_players=request.max_players
    )
    return {
        "success": True,
        "room_code": room.code,
        "host_id": host_id,
        "room": room.to_dict()
    }

@app.get("/api/rooms")
async def list_rooms():
    rooms = await room_manager.list_available_rooms()
    return {"rooms": rooms}

@app.get("/api/rooms/{room_code}")
async def get_room(room_code: str):
    room = await room_manager.get_room(room_code)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return {"room": room.to_dict()}

@app.post("/api/rooms/{room_code}/join")
async def join_room(room_code: str, request: JoinRoomRequest):
    room = await room_manager.get_room(room_code)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    player_id = f"player_{uuid.uuid4().hex[:8]}"
    result = room.add_player(
        player_id=player_id,
        player_name=request.player_name.strip(),
        avatar=request.avatar
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Could not join room"))

    # Notify room via WebSocket
    await ws_manager.broadcast_to_room(room.code, {
        "type": "room_update",
        "room": room.to_dict()
    })

    return {
        "success": True,
        "player_id": player_id,
        "room": room.to_dict()
    }


# ----------------- WebSocket Endpoint ----------------- #

@app.websocket("/ws/{room_code}/{player_id}")
async def websocket_game(websocket: WebSocket, room_code: str, player_id: str):
    db = SessionLocal()
    room_code = room_code.upper()
    room = await room_manager.get_room(room_code)

    if not room:
        await websocket.close(code=4004, reason="Room does not exist")
        db.close()
        return

    player = next((p for p in room.players if p["id"] == player_id), None)
    if not player:
        await websocket.close(code=4003, reason="Player not in room")
        db.close()
        return

    await ws_manager.connect(room_code, player_id, websocket)

    try:
        # Send current room state on initial connection
        await ws_manager.send_to_player(room_code, player_id, {
            "type": "room_update",
            "room": room.to_dict()
        })

        # If game is already active, send player's game view
        if room.game:
            await ws_manager.send_to_player(room_code, player_id, {
                "type": "game_state",
                "state": room.game.get_player_view(player_id)
            })

        while True:
            raw_data = await websocket.receive_text()
            try:
                data = json.loads(raw_data)
            except Exception:
                continue

            msg_type = data.get("type")

            # 1. Player Ready Toggle
            if msg_type == "ready":
                result = room.toggle_ready(player_id)
                await ws_manager.broadcast_to_room(room_code, {
                    "type": "room_update",
                    "room": room.to_dict()
                })

            # 2. Host Starts Game
            elif msg_type == "start_game":
                result = room.start_game(player_id)
                if not result["success"]:
                    await ws_manager.send_to_player(room_code, player_id, {
                        "type": "error",
                        "message": result["error"]
                    })
                else:
                    await ws_manager.broadcast_to_room(room_code, {
                        "type": "game_started",
                        "room": room.to_dict()
                    })
                    await ws_manager.broadcast_game_state(room)

            # 3. Play Card
            elif msg_type == "play_card":
                if not room.game:
                    continue

                card_id = data.get("card_id")
                chosen_color = data.get("color")
                target_player_id = data.get("target_player_id")

                result = room.game.play_card(
                    player_id=player_id,
                    card_id=card_id,
                    chosen_color=chosen_color,
                    target_player_id=target_player_id
                )

                if not result["success"]:
                    await ws_manager.send_to_player(room_code, player_id, {
                        "type": "error",
                        "message": result.get("error", "Invalid move")
                    })
                elif result.get("needs_action"):
                    # Prompt player for selection (e.g. choose color, pick opponent for 7 swap)
                    await ws_manager.send_to_player(room_code, player_id, {
                        "type": "action_required",
                        "action": result["needs_action"],
                        "message": result["message"],
                        "options": result.get("options")
                    })
                else:
                    await ws_manager.broadcast_game_state(room)

                    # Check for Game Over
                    if room.game.game_over:
                        room.status = "finished"
                        duration = int(time.time() - room.game.start_time)
                        # Record in database
                        record_match_result(
                            db=db,
                            room_code=room.code,
                            winner_name=room.game.winner["name"],
                            total_players=len(room.players),
                            win_reason=room.game.win_reason,
                            duration_seconds=duration,
                            player_stats=[{
                                "name": p["name"],
                                "knockouts_caused": p["knockouts_caused"],
                                "is_eliminated": p["is_eliminated"]
                            } for p in room.game.players]
                        )
                        await ws_manager.broadcast_to_room(room_code, {
                            "type": "game_over",
                            "winner": room.game.winner,
                            "win_reason": room.game.win_reason,
                            "duration_seconds": duration
                        })

            # 4. Draw Cards / Take Penalty
            elif msg_type == "draw":
                if not room.game:
                    continue

                result = room.game.player_draw(player_id)
                if not result["success"]:
                    await ws_manager.send_to_player(room_code, player_id, {
                        "type": "error",
                        "message": result.get("error", "Cannot draw now")
                    })
                else:
                    await ws_manager.broadcast_game_state(room)

                    if room.game.game_over:
                        room.status = "finished"
                        duration = int(time.time() - room.game.start_time)
                        record_match_result(
                            db=db,
                            room_code=room.code,
                            winner_name=room.game.winner["name"],
                            total_players=len(room.players),
                            win_reason=room.game.win_reason,
                            duration_seconds=duration,
                            player_stats=[{
                                "name": p["name"],
                                "knockouts_caused": p["knockouts_caused"],
                                "is_eliminated": p["is_eliminated"]
                            } for p in room.game.players]
                        )
                        await ws_manager.broadcast_to_room(room_code, {
                            "type": "game_over",
                            "winner": room.game.winner,
                            "win_reason": room.game.win_reason,
                            "duration_seconds": duration
                        })

            # 5. Resolve Action Choice (Color Picker / 7 Swap Hand Target / Roulette Color)
            elif msg_type == "resolve_action":
                if not room.game:
                    continue

                result = room.game.resolve_action(player_id, data)
                if not result["success"]:
                    await ws_manager.send_to_player(room_code, player_id, {
                        "type": "error",
                        "message": result.get("error", "Failed action")
                    })
                else:
                    await ws_manager.broadcast_game_state(room)
                    if room.game.game_over:
                        room.status = "finished"
                        duration = int(time.time() - room.game.start_time)
                        record_match_result(
                            db=db,
                            room_code=room.code,
                            winner_name=room.game.winner["name"],
                            total_players=len(room.players),
                            win_reason=room.game.win_reason,
                            duration_seconds=duration,
                            player_stats=[{
                                "name": p["name"],
                                "knockouts_caused": p["knockouts_caused"],
                                "is_eliminated": p["is_eliminated"]
                            } for p in room.game.players]
                        )
                        await ws_manager.broadcast_to_room(room_code, {
                            "type": "game_over",
                            "winner": room.game.winner,
                            "win_reason": room.game.win_reason,
                            "duration_seconds": duration
                        })

            # 6. Call UNO
            elif msg_type == "call_uno":
                if room.game:
                    result = room.game.call_uno(player_id)
                    if result["success"]:
                        await ws_manager.broadcast_game_state(room)
                        await ws_manager.broadcast_to_room(room_code, {
                            "type": "uno_called",
                            "player_name": player["name"]
                        })

            # 7. Catch UNO Failure
            elif msg_type == "catch_uno":
                if room.game:
                    target_id = data.get("target_id")
                    result = room.game.catch_uno_failure(player_id, target_id)
                    if result["success"]:
                        await ws_manager.broadcast_game_state(room)

            # 8. Chat Message / Emote
            elif msg_type == "chat":
                text = data.get("message", "").strip()
                if text:
                    msg = room.add_chat(player_id, player["name"], text)
                    await ws_manager.broadcast_to_room(room_code, {
                        "type": "chat_message",
                        "message": msg
                    })

            # 9. Rematch / Reset Game (Host only)
            elif msg_type == "rematch":
                if player["is_host"] and room.status == "finished":
                    room.status = "waiting"
                    room.game = None
                    for p in room.players:
                        if not p["is_host"]:
                            p["is_ready"] = False
                    await ws_manager.broadcast_to_room(room_code, {
                        "type": "room_update",
                        "room": room.to_dict()
                    })

    except WebSocketDisconnect:
        ws_manager.disconnect(room_code, player_id)
        # Handle player leaving
        player["connected"] = False
        await ws_manager.broadcast_to_room(room_code, {
            "type": "player_disconnected",
            "player_id": player_id,
            "room": room.to_dict()
        })
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        ws_manager.disconnect(room_code, player_id)
    finally:
        db.close()


# ----------------- Static Frontend Mounting ----------------- #

frontend_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend")

if os.path.exists(os.path.join(frontend_path, "static")):
    app.mount("/static", StaticFiles(directory=os.path.join(frontend_path, "static")), name="static")

@app.get("/", response_class=HTMLResponse)
def serve_index():
    index_file = os.path.join(frontend_path, "index.html")
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>UNO No Mercy Backend running</h1>")
