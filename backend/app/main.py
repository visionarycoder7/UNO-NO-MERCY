import os
import json
import uuid
import time
import asyncio
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from backend.app.config import MIN_PLAYERS, MAX_PLAYERS
from backend.app.storage.database import SessionLocal, get_db, get_or_create_user, record_match_result, get_leaderboard, get_recent_matches
from backend.app.game.room import room_manager
from backend.app.websocket_manager import ws_manager
from backend.app.models.schemas import CreateRoomRequest, JoinRoomRequest, UserAuthRequest

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("uno.main")

app = FastAPI(title="UNO Show 'Em No Mercy API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------- Helper for AI Automation ----------------- #

async def handle_ai_turns_in_background(room, room_code: str):
    while room.game and not room.game.game_over:
        curr = room.game.current_player
        if not curr.get("is_ai") or curr.get("is_eliminated"):
            break

        await asyncio.sleep(0.75)

        if not room.game or room.game.game_over:
            break

        res = room.game.execute_bot_turn_if_needed()
        if res:
            await ws_manager.broadcast_game_state(room)

            if room.game.game_over:
                room.status = "finished"
                duration = int(time.time() - room.game.start_time)
                db = SessionLocal()
                try:
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
                finally:
                    db.close()

                await ws_manager.broadcast_to_room(room_code, {
                    "type": "game_over",
                    "winner": room.game.winner,
                    "win_reason": room.game.win_reason,
                    "duration_seconds": duration
                })
                break
        else:
            break


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
    host_name = request.host_name.strip() if request.host_name else "Host"
    host_id = f"player_{uuid.uuid4().hex[:8]}"
    room = await room_manager.create_room(
        host_id=host_id,
        host_name=host_name,
        avatar=request.avatar,
        max_players=request.max_players,
        is_solo=False
    )
    return {
        "success": True,
        "room_code": room.code,
        "host_id": host_id,
        "room": room.to_dict()
    }

@app.post("/api/rooms/solo")
async def create_solo_room(request: CreateRoomRequest):
    host_name = request.host_name.strip() if request.host_name else "Player"
    host_id = f"player_{uuid.uuid4().hex[:8]}"
    room = await room_manager.create_room(
        host_id=host_id,
        host_name=host_name,
        avatar=request.avatar,
        max_players=4,
        is_solo=True
    )
    # Pre-add 2 AI bots for immediate solo play
    room.add_ai_bot()
    room.add_ai_bot()

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
    code = room_code.strip().upper()
    room = await room_manager.get_room(code)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return {"room": room.to_dict()}

@app.post("/api/rooms/{room_code}/join")
async def join_room(room_code: str, request: JoinRoomRequest):
    code = room_code.strip().upper()
    room = await room_manager.get_room(code)
    if not room:
        raise HTTPException(status_code=404, detail=f"Room '{code}' not found")

    player_name = request.player_name.strip() if request.player_name else "Player"
    player_id = f"player_{uuid.uuid4().hex[:8]}"
    result = room.add_player(
        player_id=player_id,
        player_name=player_name,
        avatar=request.avatar
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Could not join room"))

    # Return actual joined/reconnected player info
    actual_player = result.get("player", {})
    actual_id = actual_player.get("id", player_id)

    # Immediately broadcast updated room to all existing connected players
    await ws_manager.broadcast_to_room(room.code, {
        "type": "room_update",
        "room": room.to_dict()
    })

    return {
        "success": True,
        "player_id": actual_id,
        "room": room.to_dict()
    }

@app.post("/api/rooms/{room_code}/start")
async def start_game_endpoint(room_code: str, payload: dict):
    code = room_code.strip().upper()
    player_id = payload.get("player_id")
    room = await room_manager.get_room(code)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    result = room.start_game(player_id)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Could not start game"))

    await ws_manager.broadcast_to_room(code, {
        "type": "game_started",
        "room": room.to_dict()
    })
    await ws_manager.broadcast_game_state(room)

    if room.game.current_player.get("is_ai"):
        asyncio.create_task(handle_ai_turns_in_background(room, code))

    return {"success": True}


# ----------------- WebSocket Endpoint ----------------- #

@app.websocket("/ws/{room_code}/{player_id}")
async def websocket_game(websocket: WebSocket, room_code: str, player_id: str):
    db = SessionLocal()
    room_code = room_code.strip().upper()
    player_id = player_id.strip()
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
        # Mark player connected
        player["connected"] = True

        # Broadcast room state to everyone so all tabs reflect connection
        await ws_manager.broadcast_to_room(room_code, {
            "type": "room_update",
            "room": room.to_dict()
        })

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

            # 1. Ready
            if msg_type == "ready":
                room.toggle_ready(player_id)
                await ws_manager.broadcast_to_room(room_code, {
                    "type": "room_update",
                    "room": room.to_dict()
                })

            # 2. Add / Remove AI Bots
            elif msg_type == "add_ai" or msg_type == "addAI":
                if player["is_host"] and room.status == "waiting":
                    room.add_ai_bot()
                    await ws_manager.broadcast_to_room(room_code, {
                        "type": "room_update",
                        "room": room.to_dict()
                    })

            elif msg_type == "remove_ai" or msg_type == "removeAI":
                if player["is_host"] and room.status == "waiting":
                    bot_id = data.get("aiId")
                    room.remove_ai_bot(bot_id)
                    await ws_manager.broadcast_to_room(room_code, {
                        "type": "room_update",
                        "room": room.to_dict()
                    })

            # 3. Kick Player
            elif msg_type == "removePlayer":
                if player["is_host"] and room.status == "waiting":
                    target_id = data.get("targetId")
                    if target_id and target_id != player_id:
                        room.remove_player(target_id)
                        await ws_manager.broadcast_to_room(room_code, {
                            "type": "room_update",
                            "room": room.to_dict()
                        })

            # 4. Host Starts Game
            elif msg_type == "start_game" or msg_type == "startGame":
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

                    if room.game.current_player.get("is_ai"):
                        asyncio.create_task(handle_ai_turns_in_background(room, room_code))

            # 5. Play Card
            elif msg_type == "play_card" or msg_type == "playCard":
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
                    await ws_manager.send_to_player(room_code, player_id, {
                        "type": "action_required",
                        "action": result["needs_action"],
                        "message": result["message"],
                        "options": result.get("options")
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
                    else:
                        if room.game.current_player.get("is_ai"):
                            asyncio.create_task(handle_ai_turns_in_background(room, room_code))

            # 6. Draw Cards
            elif msg_type in ("draw", "drawCard", "draw_card"):
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
                    else:
                        if room.game.current_player.get("is_ai"):
                            asyncio.create_task(handle_ai_turns_in_background(room, room_code))

            # 7. Resolve Action (Color, 7 Swap, Roulette)
            elif msg_type == "resolve_action" or msg_type == "rouletteColorChosen":
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
                    else:
                        if room.game.current_player.get("is_ai"):
                            asyncio.create_task(handle_ai_turns_in_background(room, room_code))

            # 8. Call UNO
            elif msg_type == "call_uno":
                if room.game:
                    result = room.game.call_uno(player_id)
                    if result["success"]:
                        await ws_manager.broadcast_game_state(room)
                        await ws_manager.broadcast_to_room(room_code, {
                            "type": "uno_called",
                            "player_name": player["name"]
                        })

            # 9. Catch UNO Failure
            elif msg_type == "catch_uno":
                if room.game:
                    target_id = data.get("target_id")
                    result = room.game.catch_uno_failure(player_id, target_id)
                    if result["success"]:
                        await ws_manager.broadcast_game_state(room)

            # 10. Chat Message & Floating Emojis
            elif msg_type == "chat" or msg_type == "chatEmoji":
                emoji = data.get("emoji")
                text = data.get("message", emoji or "").strip()
                if text:
                    msg = room.add_chat(player_id, player["name"], text, is_emoji=bool(emoji))
                    await ws_manager.broadcast_to_room(room_code, {
                        "type": "chat_message",
                        "message": msg,
                        "emoji": emoji,
                        "sender_id": player_id
                    })

            # 11. Rematch / Reset Game
            elif msg_type == "rematch" or msg_type == "playAgain":
                if player["is_host"] and room.status == "finished":
                    room.status = "waiting"
                    room.game = None
                    for p in room.players:
                        if not p["is_host"] and not p.get("is_ai"):
                            p["is_ready"] = True
                    await ws_manager.broadcast_to_room(room_code, {
                        "type": "room_update",
                        "room": room.to_dict()
                    })

    except WebSocketDisconnect:
        ws_manager.disconnect(room_code, player_id, websocket)
        player["connected"] = False
        await ws_manager.broadcast_to_room(room_code, {
            "type": "player_disconnected",
            "player_id": player_id,
            "room": room.to_dict()
        })
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        ws_manager.disconnect(room_code, player_id, websocket)
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
