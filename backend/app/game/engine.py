import random
import time
from typing import List, Dict, Any, Optional, Tuple
from collections import Counter
from backend.app.game.cards import (
    Card,
    build_no_mercy_deck,
    COLOR_CODES,
    COLOR_NAMES,
    DRAW_VALUES,
    TYPE_SKIP,
    TYPE_REV,
    TYPE_D2,
    TYPE_DISCARD,
    TYPE_D4,
    TYPE_SKIPALL,
    TYPE_WRD4,
    TYPE_WD6,
    TYPE_WD10,
    TYPE_ROUL
)

MERCY_CARD_LIMIT = 25
INITIAL_HAND_SIZE = 7

class UnoNoMercyGame:
    def __init__(self, room_code: str, players_info: List[Dict[str, Any]]):
        self.room_code = room_code
        self.players: List[Dict[str, Any]] = []
        for p in players_info:
            self.players.append({
                "id": p["id"],
                "name": p["name"],
                "avatar": p.get("avatar", "avatar1"),
                "is_ai": p.get("is_ai", False),
                "hand": [],
                "is_eliminated": False,
                "eliminated_reason": None,
                "called_uno": False,
                "knockouts_caused": 0
            })

        self.direction = 1  # 1: clockwise, -1: counter-clockwise
        self.current_player_idx = 0
        self.draw_pile: List[Card] = []
        self.discard_pile: List[Card] = []
        self.current_color: Optional[str] = None  # 'R', 'Y', 'G', 'B'
        self.pending_penalty = 0

        # Modal/Action state
        self.pending_action: Optional[str] = None  # "color", "target", "roul"
        self.action_player_id: Optional[str] = None
        self.action_context: Dict[str, Any] = {}

        self.game_over = False
        self.winner: Optional[Dict[str, Any]] = None
        self.win_reason: Optional[str] = None
        self.start_time = time.time()
        self.event_log: List[Dict[str, Any]] = []

        self._start_game()

    def _log(self, text: str):
        self.event_log.append({
            "message": text,
            "timestamp": time.time()
        })
        if len(self.event_log) > 50:
            self.event_log.pop(0)

    def _start_game(self):
        # 1. Build and shuffle deck
        self.draw_pile = build_no_mercy_deck()
        random.shuffle(self.draw_pile)

        # 2. Deal 7 cards to each player
        for _ in range(INITIAL_HAND_SIZE):
            for p in self.players:
                p["hand"].append(self.draw_pile.pop())

        # 3. Find first card that is a standard number card
        first_card = None
        while True:
            c = self.draw_pile.pop()
            if c.card_type.isdigit():
                first_card = c
                break
            self.draw_pile.insert(0, c)

        self.discard_pile = [first_card]
        self.current_color = first_card.color
        self._log(f"Game started. First card: {first_card.display_name}")

    @property
    def top_card(self) -> Optional[Card]:
        return self.discard_pile[-1] if self.discard_pile else None

    @property
    def current_player(self) -> Dict[str, Any]:
        return self.players[self.current_player_idx]

    def _get_active_indices(self) -> List[int]:
        return [i for i, p in enumerate(self.players) if not p["is_eliminated"]]

    def _next_player_index(self, start_idx: int) -> int:
        n = len(self.players)
        curr = start_idx
        while True:
            curr = (curr + self.direction + n) % n
            if not self.players[curr]["is_eliminated"]:
                return curr

    def _advance_turn(self, skip: int = 0, from_idx: Optional[int] = None):
        if self.game_over:
            return

        c = self.current_player_idx if from_idx is None else from_idx
        for _ in range(skip + 1):
            c = self._next_player_index(c)

        self.current_player_idx = c
        self._log(f"It's now {self.current_player['name']}'s turn.")

    def _reshuffle_if_needed(self):
        if not self.draw_pile and len(self.discard_pile) > 1:
            top = self.discard_pile.pop()
            self.draw_pile = self.discard_pile[:]
            self.discard_pile = [top]
            random.shuffle(self.draw_pile)
            self._log("Reshuffled discard pile into draw deck.")

    def _draw_card_from_deck(self) -> Optional[Card]:
        self._reshuffle_if_needed()
        return self.draw_pile.pop() if self.draw_pile else None

    def _check_mercy(self):
        """
        Mercy Rule: If any player accumulates 25 or more cards, they are immediately knocked out.
        """
        for p in self.players:
            if not p["is_eliminated"] and len(p["hand"]) >= MERCY_CARD_LIMIT:
                p["is_eliminated"] = True
                p["eliminated_reason"] = f"Mercy Rule ({len(p['hand'])} cards)"
                # Return their hand to deck and shuffle
                self.draw_pile.extend(p["hand"])
                p["hand"] = []
                random.shuffle(self.draw_pile)
                self._log(f"💀 {p['name']} reached 25 cards and is out (Mercy Rule)!")

        active = self._get_active_indices()
        if len(active) == 1 and self.winner is None:
            self.winner = self.players[active[0]]
            self.win_reason = "Last Survivor (Mercy Rule)"
            self.game_over = True
            self._log(f"🏆 {self.winner['name']} WINS as the Last Survivor!")
            return True

        return False

    def can_play_card(self, player_id: str, card: Card) -> Tuple[bool, str]:
        """
        Validation logic matching UNO No Mercy.html:
        if (G.pend) return dv(c) > 0 && dv(c) >= dv(t);
        return c.color === 'W' || c.color === G.color || c.type === t.type;
        """
        if self.game_over:
            return False, "Game is over."

        if self.pending_action:
            return False, f"Waiting for action: {self.pending_action}"

        if self.current_player["id"] != player_id:
            return False, "Not your turn."

        top = self.top_card
        if not top:
            return True, "Valid."

        # Case 1: Penalty is pending (Stacking Rule)
        if self.pending_penalty > 0:
            if card.draw_val > 0 and card.draw_val >= top.draw_val:
                return True, "Valid stack move."
            return False, f"Must play an equal or higher draw card (+{top.draw_val}+) or take penalty."

        # Case 2: Normal turn
        if card.color == "W" or card.color == self.current_color or card.card_type == top.card_type:
            return True, "Valid move."

        return False, "Card does not match color or symbol."

    def get_valid_cards_for_player(self, player_id: str) -> List[str]:
        p = next((x for x in self.players if x["id"] == player_id), None)
        if not p or p["is_eliminated"] or self.current_player["id"] != player_id:
            return []
        return [c.id for c in p["hand"] if self.can_play_card(player_id, c)[0]]

    def play_card(
        self,
        player_id: str,
        card_id: str,
        chosen_color: Optional[str] = None,
        target_player_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Exact play logic from UNO No Mercy.html:
        - discard extra cards on 'discard'
        - reverse / wrd4 logic
        - accumulate penalty
        - 7 swap hands
        - 0 rotate hands
        - wild color roulette
        """
        p = self.current_player
        if p["id"] != player_id:
            return {"success": False, "error": "Not your turn."}

        card_idx = next((i for i, c in enumerate(p["hand"]) if c.id == card_id), None)
        if card_idx is None:
            return {"success": False, "error": "Card not in hand."}

        card = p["hand"][card_idx]
        can_play, reason = self.can_play_card(player_id, card)
        if not can_play:
            return {"success": False, "error": reason}

        # Check interactive modals required
        if card.card_type == "7":
            active_opponents = [x for x in self.players if x["id"] != player_id and not x["is_eliminated"]]
            if len(active_opponents) > 1 and not target_player_id:
                if p["is_ai"]:
                    # Bot swaps with player having lowest hand
                    target_player_id = min(active_opponents, key=lambda x: len(x["hand"]))["id"]
                else:
                    self.pending_action = "target"
                    self.action_player_id = player_id
                    self.action_context = {"card_id": card_id, "chosen_color": chosen_color}
                    return {
                        "success": True,
                        "needs_action": "target",
                        "options": [{"id": x["id"], "name": x["name"], "cards": len(x["hand"])} for x in active_opponents],
                        "message": "Choose a player to swap hands with!"
                    }

        if card.color == "W" and card.card_type != TYPE_ROUL and not chosen_color:
            if p["is_ai"]:
                chosen_color = self._bot_color(p)
            else:
                self.pending_action = "color"
                self.action_player_id = player_id
                self.action_context = {"card_id": card_id}
                return {
                    "success": True,
                    "needs_action": "color",
                    "message": "Choose a color!"
                }

        # Execute card removal
        p["hand"].pop(card_idx)
        self.discard_pile.append(card)

        # Update current color
        if card.color != "W":
            self.current_color = card.color
        elif chosen_color:
            self.current_color = chosen_color

        color_str = f" → {COLOR_NAMES.get(chosen_color, chosen_color)}" if card.color == "W" and chosen_color else ""
        self._log(f"{p['name']} played {card.display_name}{color_str}")

        # Discard All: dump every card of that color from hand
        if card.card_type == TYPE_DISCARD:
            matching = [c for c in p["hand"] if c.color == card.color]
            p["hand"] = [c for c in p["hand"] if c.color != card.color]
            self.discard_pile = matching + self.discard_pile
            if matching:
                self._log(f"{p['name']} discarded {len(matching)} more {COLOR_NAMES[card.color]} card(s)!")

        # Win check: hand emptied
        if len(p["hand"]) == 0:
            self.winner = p
            self.win_reason = "Emptied Hand"
            self.game_over = True
            self._log(f"🏆 {p['name']} played their final card and WINS!")
            return {"success": True, "game_over": True, "winner": self.winner}

        skip = 0
        again = False

        if card.card_type == TYPE_SKIP:
            skip = 1

        if card.card_type == TYPE_REV or card.card_type == TYPE_WRD4:
            self.direction *= -1
            active_count = len(self._get_active_indices())
            if card.card_type == TYPE_REV and active_count == 2:
                skip = 1

        if card.draw_val > 0:
            self.pending_penalty += card.draw_val

        if card.card_type == TYPE_SKIPALL:
            again = True
            self._log("Everyone else is skipped! Taking another turn.")

        # 7 Swap Hands
        if card.card_type == "7":
            active_opponents = [x for x in self.players if x["id"] != player_id and not x["is_eliminated"]]
            target = None
            if target_player_id:
                target = next((x for x in active_opponents if x["id"] == target_player_id), None)
            if not target and active_opponents:
                target = active_opponents[0]

            if target:
                p["hand"], target["hand"] = target["hand"], p["hand"]
                self._log(f"{p['name']} swapped hands with {target['name']}!")

        # 0 Rotate Hands
        if card.card_type == "0":
            # Order of players in direction of play
            curr_idx = self.current_player_idx
            order = [curr_idx]
            nxt_idx = self._next_player_index(curr_idx)
            while nxt_idx != curr_idx:
                order.append(nxt_idx)
                nxt_idx = self._next_player_index(nxt_idx)

            old_hands = [self.players[k]["hand"][:] for k in order]
            m = len(order)
            for n_idx, k in enumerate(order):
                self.players[k]["hand"] = old_hands[(n_idx - 1 + m) % m]
            self._log("All hands rotate in direction of play!")

        # Check Mercy knockout
        if self._check_mercy():
            return {"success": True, "game_over": True, "winner": self.winner}

        # Wild Color Roulette
        if card.card_type == TYPE_ROUL:
            victim_idx = self._next_player_index(self.current_player_idx)
            victim = self.players[victim_idx]
            self.pending_action = "roul"
            self.action_player_id = victim["id"]
            self.action_context = {"victim_idx": victim_idx}

            if victim["is_ai"]:
                bot_color = self._bot_color(victim)
                return self.resolve_roulette(bot_color)

            return {
                "success": True,
                "needs_action": "roul",
                "message": f"{victim['name']}, pick a color to draw until!"
            }

        if again:
            return {"success": True}

        self._advance_turn(skip=skip)
        return {"success": True}

    def resolve_roulette(self, color: str) -> Dict[str, Any]:
        """
        Victim draws cards until one matches chosen color, then their turn is skipped.
        """
        victim_idx = self.action_context.get("victim_idx")
        if victim_idx is None:
            victim_idx = self._next_player_index(self.current_player_idx)

        victim = self.players[victim_idx]
        self.pending_action = None
        self.action_player_id = None
        self.action_context = {}
        self.current_color = color

        n = 0
        while True:
            c = self._draw_card_from_deck()
            if not c:
                break
            victim["hand"].append(c)
            n += 1
            if c.color == color or len(victim["hand"]) >= MERCY_CARD_LIMIT:
                break

        self._log(f"{victim['name']} chose {COLOR_NAMES.get(color, color)} and drew {n} card(s), turn skipped.")

        if self._check_mercy():
            return {"success": True, "game_over": True, "winner": self.winner}

        # Advance turn from the victim
        self._advance_turn(skip=0, from_idx=victim_idx)
        return {"success": True}

    def player_draw(self, player_id: str) -> Dict[str, Any]:
        """
        Draw logic matching UNO No Mercy.html drawAct(i):
        - If penalty pending: draws pending_penalty, resets pending_penalty=0, turn ends.
        - If normal: draws until canPlay(c) or hand.length >= 25.
        """
        p = self.current_player
        if p["id"] != player_id:
            return {"success": False, "error": "Not your turn."}

        pen = self.pending_penalty > 0
        if pen:
            drawn_count = self.pending_penalty
            for _ in range(drawn_count):
                c = self._draw_card_from_deck()
                if not c:
                    break
                p["hand"].append(c)
            self.pending_penalty = 0
            self._log(f"{p['name']} drew {drawn_count} (penalty).")
        else:
            n = 0
            while True:
                c = self._draw_card_from_deck()
                if not c:
                    break
                p["hand"].append(c)
                n += 1
                if self.can_play_card(player_id, c)[0] or len(p["hand"]) >= MERCY_CARD_LIMIT:
                    break
            self._log(f"{p['name']} drew {n} card(s).")

        if self._check_mercy():
            return {"success": True, "game_over": True, "winner": self.winner}

        has_playable = any(self.can_play_card(player_id, c)[0] for c in p["hand"])

        # If took penalty or eliminated or no playable move, turn ends
        if pen or p["is_eliminated"] or not has_playable:
            self._advance_turn(skip=0)
            return {"success": True, "turn_ended": True}

        # Normal draw yielded a playable card: turn remains active so they can play it!
        return {"success": True, "turn_ended": False}

    # ---------------- BOT AI (MATCHING UNO No Mercy.html) ---------------- #

    def _bot_color(self, bot_player: Dict[str, Any]) -> str:
        counts = {c: 0 for c in COLOR_CODES}
        for c in bot_player["hand"]:
            if c.color != "W" and c.color in counts:
                counts[c.color] += 1
        m = max(counts.values()) if counts else 0
        best = [k for k, v in counts.items() if v == m]
        return random.choice(best) if best else random.choice(COLOR_CODES)

    def execute_bot_turn_if_needed(self) -> Optional[Dict[str, Any]]:
        """
        Exact botMove scoring function from UNO No Mercy.html:
        const sc = c => {
          let s = Math.random(), v = dv(c);
          if (v) s += nx <= 4 ? 3 + v / 10 : (G.pend ? 4 : .3);
          if (c.type === 'skipall') s += 1.5;
          if (c.type === 'discard') s += 1 + p.hand.filter(x => x.color === c.color).length * .5;
          if (c.type === 'roul') s += .8;
          if (c.type === '7') s += p.hand.length > minO ? 1.5 : -3;
          if (c.color === 'W') s -= 1;
          return s;
        };
        """
        if self.game_over or self.pending_action:
            return None

        curr = self.current_player
        if not curr.get("is_ai") or curr.get("is_eliminated"):
            return None

        bot_id = curr["id"]
        valid_cards = [c for c in curr["hand"] if self.can_play_card(bot_id, c)[0]]

        if not valid_cards:
            return self.player_draw(bot_id)

        # Calculate opponent hand metrics
        next_p = self.players[self._next_player_index(self.current_player_idx)]
        nx = len(next_p["hand"])

        other_actives = [self.players[j] for j in self._get_active_indices() if self.players[j]["id"] != bot_id]
        min_other = min(len(x["hand"]) for x in other_actives) if other_actives else 99
        best_target = min(other_actives, key=lambda x: len(x["hand"]))["id"] if other_actives else None

        def score(c: Card) -> float:
            s = random.random()
            v = c.draw_val
            if v > 0:
                s += (3 + v / 10.0) if nx <= 4 else (4.0 if self.pending_penalty > 0 else 0.3)
            if c.card_type == TYPE_SKIPALL:
                s += 1.5
            if c.card_type == TYPE_DISCARD:
                s += 1.0 + len([x for x in curr["hand"] if x.color == c.color]) * 0.5
            if c.card_type == TYPE_ROUL:
                s += 0.8
            if c.card_type == "7":
                s += 1.5 if len(curr["hand"]) > min_other else -3.0
            if c.color == "W":
                s -= 1.0
            return s

        valid_cards.sort(key=score, reverse=True)
        chosen = valid_cards[0]
        chosen_col = self._bot_color(curr) if chosen.color == "W" else None
        target_id = best_target if chosen.card_type == "7" else None

        return self.play_card(bot_id, chosen.id, chosen_color=chosen_col, target_player_id=target_id)

    def resolve_action(self, player_id: str, payload: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        if not self.pending_action or self.action_player_id != player_id:
            return {"success": False, "error": "No pending action for you."}

        merged = {}
        if payload and isinstance(payload, dict):
            merged.update(payload)
        merged.update(kwargs)
        if "target_id" in merged and "target_player_id" not in merged:
            merged["target_player_id"] = merged["target_id"]

        action_type = self.pending_action
        card_id = self.action_context.get("card_id")

        if action_type == "color":
            col = merged.get("color")
            if col not in COLOR_CODES:
                return {"success": False, "error": "Invalid color."}
            self.pending_action = None
            self.action_player_id = None
            self.action_context = {}
            return self.play_card(player_id, card_id, chosen_color=col)

        elif action_type == "target":
            target_id = merged.get("target_player_id")
            chosen_col = self.action_context.get("chosen_color")
            self.pending_action = None
            self.action_player_id = None
            self.action_context = {}
            return self.play_card(player_id, card_id, chosen_color=chosen_col, target_player_id=target_id)

        elif action_type == "roul":
            col = merged.get("color")
            if col not in COLOR_CODES:
                return {"success": False, "error": "Invalid color."}
            return self.resolve_roulette(col)

        return {"success": False, "error": "Unknown action."}

    def get_player_view(self, player_id: str) -> Dict[str, Any]:
        p = next((x for x in self.players if x["id"] == player_id), None)
        valid_ids = self.get_valid_cards_for_player(player_id) if p else []

        players_view = []
        for pl in self.players:
            players_view.append({
                "id": pl["id"],
                "name": pl["name"],
                "avatar": pl["avatar"],
                "is_ai": pl.get("is_ai", False),
                "card_count": len(pl["hand"]),
                "is_eliminated": pl["is_eliminated"],
                "eliminated_reason": pl["eliminated_reason"],
                "is_current": (not self.game_over and self.players[self.current_player_idx]["id"] == pl["id"]),
                "is_danger": len(pl["hand"]) >= (MERCY_CARD_LIMIT - 5)
            })

        own_hand = [c.to_dict() for c in p["hand"]] if p else []

        return {
            "room_code": self.room_code,
            "direction": self.direction,
            "current_player_id": self.current_player["id"] if not self.game_over else None,
            "current_player_name": self.current_player["name"] if not self.game_over else None,
            "is_current_ai": self.current_player.get("is_ai", False) if not self.game_over else False,
            "current_color": self.current_color,
            "top_card": self.top_card.to_dict() if self.top_card else None,
            "draw_pile_count": len(self.draw_pile),
            "discard_pile_count": len(self.discard_pile),
            "pending_penalty": self.pending_penalty,
            "pending_action": self.pending_action if self.action_player_id == player_id else None,
            "action_context": self.action_context if self.action_player_id == player_id else {},
            "game_over": self.game_over,
            "winner": self.winner,
            "win_reason": self.win_reason,
            "mercy_limit": MERCY_CARD_LIMIT,
            "players": players_view,
            "my_hand": own_hand,
            "my_valid_cards": valid_ids,
            "can_draw": (p and not p["is_eliminated"] and self.current_player["id"] == player_id and not self.pending_action),
            "recent_events": self.event_log[-8:]
        }

    get_state_for_player = get_player_view



GameEngine = UnoNoMercyGame

