import random
import time
from typing import List, Dict, Any, Optional, Tuple
from backend.app.game.cards import (
    Card,
    build_no_mercy_deck,
    COLORS,
    TYPE_NUMBER,
    TYPE_SKIP,
    TYPE_SKIP_EVERYONE,
    TYPE_REVERSE,
    TYPE_DRAW_2,
    TYPE_DRAW_4,
    TYPE_DISCARD_ALL,
    TYPE_WILD_ROULETTE,
    TYPE_WILD_REVERSE_DRAW_4,
    TYPE_WILD_DRAW_6,
    TYPE_WILD_DRAW_10
)
from backend.app.config import INITIAL_HAND_SIZE, MERCY_CARD_LIMIT

class UnoNoMercyGame:
    def __init__(self, room_code: str, players_info: List[Dict[str, Any]]):
        self.room_code = room_code
        self.players: List[Dict[str, Any]] = []
        for p in players_info:
            self.players.append({
                "id": p["id"],
                "name": p["name"],
                "avatar": p.get("avatar", "avatar1"),
                "hand": [],
                "is_eliminated": False,
                "eliminated_reason": None,
                "called_uno": False,
                "knockouts_caused": 0
            })

        self.direction = 1  # 1 for clockwise, -1 for counter-clockwise
        self.current_player_idx = 0
        self.draw_pile: List[Card] = []
        self.discard_pile: List[Card] = []
        self.current_color: Optional[str] = None

        # Stacking mechanic state
        self.pending_penalty = 0
        self.pending_penalty_value = 0  # 2, 4, 6, 10
        self.last_penalty_source_id: Optional[str] = None

        # Interactive states: "choose_color", "swap_hand", "roulette_target_color"
        self.pending_action: Optional[str] = None
        self.action_player_id: Optional[str] = None
        self.action_context: Dict[str, Any] = {}

        self.game_over = False
        self.winner: Optional[Dict[str, Any]] = None
        self.win_reason: Optional[str] = None
        self.start_time = time.time()
        self.event_log: List[Dict[str, Any]] = []

        self._initialize_game()

    def _log_event(self, event_type: str, message: str, details: Optional[dict] = None):
        event = {
            "type": event_type,
            "message": message,
            "timestamp": time.time(),
            "details": details or {}
        }
        self.event_log.append(event)
        if len(self.event_log) > 50:
            self.event_log.pop(0)

    def _initialize_game(self):
        # 1. Shuffle full 168 card deck
        self.draw_pile = build_no_mercy_deck()
        random.shuffle(self.draw_pile)

        # 2. Deal initial hand (7 cards) to each player
        for player in self.players:
            player["hand"] = [self.draw_pile.pop() for _ in range(INITIAL_HAND_SIZE)]

        # 3. Find a starting card from draw pile that is a standard number card
        first_card_idx = None
        for i, card in enumerate(self.draw_pile):
            if card.card_type == TYPE_NUMBER and not card.is_wild:
                first_card_idx = i
                break

        if first_card_idx is not None:
            first_card = self.draw_pile.pop(first_card_idx)
        else:
            first_card = self.draw_pile.pop()

        self.discard_pile.append(first_card)
        self.current_color = first_card.color

        self._log_event(
            "game_started",
            f"Game started! First card is {first_card.display_name}.",
            {"first_card": first_card.to_dict()}
        )

    @property
    def top_card(self) -> Optional[Card]:
        return self.discard_pile[-1] if self.discard_pile else None

    @property
    def current_player(self) -> Dict[str, Any]:
        return self.players[self.current_player_idx]

    def _get_active_players(self) -> List[Dict[str, Any]]:
        return [p for p in self.players if not p["is_eliminated"]]

    def _next_player_index(self, start_idx: int, step: int = 1) -> int:
        n = len(self.players)
        curr = start_idx
        for _ in range(n):
            curr = (curr + (step * self.direction)) % n
            if not self.players[curr]["is_eliminated"]:
                return curr
        return start_idx

    def _advance_turn(self, skip_count: int = 0):
        if self.game_over:
            return

        active = self._get_active_players()
        if len(active) <= 1:
            self._check_victory()
            return

        # Advance current player
        steps = 1 + skip_count
        new_idx = self.current_player_idx
        for _ in range(steps):
            new_idx = self._next_player_index(new_idx, step=1)

        self.current_player_idx = new_idx
        # Reset uno call for the new player if they have more than 1 card
        if len(self.current_player["hand"]) > 1:
            self.current_player["called_uno"] = False

        self._log_event(
            "turn_change",
            f"It's now {self.current_player['name']}'s turn.",
            {"current_player_id": self.current_player["id"]}
        )

    def _reshuffle_if_needed(self, count_needed: int = 1):
        if len(self.draw_pile) < count_needed and len(self.discard_pile) > 1:
            top = self.discard_pile.pop()
            reshuffled = self.discard_pile[:]
            self.discard_pile = [top]
            random.shuffle(reshuffled)
            self.draw_pile.extend(reshuffled)
            self._log_event("deck_reshuffle", "Draw deck was reshuffled from discard pile.")

    def _draw_cards_to_player(self, player: Dict[str, Any], count: int) -> List[Card]:
        drawn: List[Card] = []
        for _ in range(count):
            self._reshuffle_if_needed(1)
            if not self.draw_pile:
                break
            card = self.draw_pile.pop()
            player["hand"].append(card)
            drawn.append(card)

            # Check Mercy limit during draw
            if len(player["hand"]) >= MERCY_CARD_LIMIT:
                self._eliminate_player(player, reason=f"Mercy Rule ({len(player['hand'])} cards)")
                break

        return drawn

    def _eliminate_player(self, player: Dict[str, Any], reason: str = "Mercy Rule"):
        if player["is_eliminated"]:
            return

        player["is_eliminated"] = True
        player["eliminated_reason"] = reason

        # Credit knockout to source if applicable
        if self.last_penalty_source_id:
            for p in self.players:
                if p["id"] == self.last_penalty_source_id and p["id"] != player["id"]:
                    p["knockouts_caused"] += 1
                    break

        # Move eliminated player's hand to bottom of draw pile
        discarded_cards = player["hand"][:]
        player["hand"] = []
        self.draw_pile = discarded_cards + self.draw_pile

        self._log_event(
            "mercy_knockout",
            f"💀 {player['name']} was KNOCKED OUT by the {reason}!",
            {"eliminated_player_id": player["id"], "reason": reason}
        )

        self._check_victory()

    def _check_victory(self) -> bool:
        if self.game_over:
            return True

        active = self._get_active_players()
        if len(active) == 1:
            # Last player standing!
            self.winner = active[0]
            self.win_reason = "Last Survivor (Mercy Rule)"
            self.game_over = True
            self._log_event("game_over", f"🏆 {self.winner['name']} WINS as the Last Survivor!", {"winner": self.winner})
            return True

        for p in active:
            if len(p["hand"]) == 0:
                self.winner = p
                self.win_reason = "Emptied Hand"
                self.game_over = True
                self._log_event("game_over", f"🏆 {p['name']} played their final card and WINS!", {"winner": p})
                return True

        return False

    def can_play_card(self, player_id: str, card: Card) -> Tuple[bool, str]:
        """
        Validates whether a specific card can be played by the player right now.
        """
        if self.game_over:
            return False, "Game is already over."

        if self.pending_action:
            return False, f"Waiting for action: {self.pending_action}."

        if self.current_player["id"] != player_id:
            return False, "It is not your turn."

        # Case 1: Active Penalty Stacking Mode (+2, +4, +6, +10)
        if self.pending_penalty > 0:
            if not card.is_draw_card:
                return False, f"A penalty of +{self.pending_penalty} is active! You can only play an equal or higher draw card (+{self.pending_penalty_value}+) or draw."

            # Equal or higher penalty rule
            if card.penalty < self.pending_penalty_value:
                return False, f"Cannot play +{card.penalty} on top of +{self.pending_penalty_value}. Must be equal or higher!"

            return True, "Valid stack move."

        # Case 2: Normal Turn (no active penalty stack)
        top = self.top_card
        if not top:
            return True, "Valid move."

        # Wild cards can always be played on normal turn
        if card.is_wild:
            return True, "Valid wild move."

        # Matching color
        if card.color == self.current_color:
            return True, "Valid color match."

        # Matching number
        if card.card_type == TYPE_NUMBER and top.card_type == TYPE_NUMBER and card.value == top.value:
            return True, "Valid number match."

        # Matching action symbol
        if card.card_type == top.card_type and card.card_type != TYPE_NUMBER:
            return True, "Valid action match."

        return False, f"Card does not match current color ({self.current_color}) or symbol."

    def get_valid_cards_for_player(self, player_id: str) -> List[str]:
        player = next((p for p in self.players if p["id"] == player_id), None)
        if not player or player["is_eliminated"] or self.current_player["id"] != player_id:
            return []

        valid_ids = []
        for card in player["hand"]:
            can_play, _ = self.can_play_card(player_id, card)
            if can_play:
                valid_ids.append(card.id)
        return valid_ids

    def play_card(
        self,
        player_id: str,
        card_id: str,
        chosen_color: Optional[str] = None,
        target_player_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes playing a card from player's hand.
        """
        player = self.current_player
        if player["id"] != player_id:
            return {"success": False, "error": "Not your turn."}

        # Find card in hand
        card_idx = next((i for i, c in enumerate(player["hand"]) if c.id == card_id), None)
        if card_idx is None:
            return {"success": False, "error": "Card not in hand."}

        card = player["hand"][card_idx]
        can_play, reason = self.can_play_card(player_id, card)
        if not can_play:
            return {"success": False, "error": reason}

        # Wild card color selection check
        if card.is_wild and not chosen_color and card.card_type != TYPE_WILD_ROULETTE:
            # Need color choice
            self.pending_action = "choose_color"
            self.action_player_id = player_id
            self.action_context = {"card_id": card_id}
            return {
                "success": True,
                "needs_action": "choose_color",
                "message": "Choose a color to continue."
            }

        # 7 Card Hand Swap target check
        if card.card_type == TYPE_NUMBER and card.value == 7:
            active_opponents = [p for p in self._get_active_players() if p["id"] != player_id]
            if len(active_opponents) > 1 and not target_player_id:
                self.pending_action = "swap_hand"
                self.action_player_id = player_id
                self.action_context = {"card_id": card_id, "chosen_color": chosen_color}
                return {
                    "success": True,
                    "needs_action": "swap_hand",
                    "options": [{"id": p["id"], "name": p["name"], "cards": len(p["hand"])} for p in active_opponents],
                    "message": "Choose an opponent to swap hands with!"
                }

        # Roulette target color check
        if card.card_type == TYPE_WILD_ROULETTE and not chosen_color:
            self.pending_action = "choose_roulette_color"
            self.action_player_id = player_id
            self.action_context = {"card_id": card_id}
            return {
                "success": True,
                "needs_action": "choose_roulette_color",
                "message": "Choose a target color for Color Roulette!"
            }

        # Remove card from hand
        player["hand"].pop(card_idx)
        self.discard_pile.append(card)

        # Clear pending action if any
        self.pending_action = None
        self.action_player_id = None
        self.action_context = {}

        # Log play
        self._log_event(
            "card_played",
            f"{player['name']} played {card.display_name}.",
            {"player_id": player_id, "card": card.to_dict()}
        )

        # Process special card effects
        self._handle_card_effects(player, card, chosen_color, target_player_id)

        # Check UNO status
        if len(player["hand"]) == 1 and not player["called_uno"]:
            self._log_event("uno_warning", f"{player['name']} has only 1 card left! UNO!")

        # Check win condition
        if self._check_victory():
            return {"success": True, "game_over": True, "winner": self.winner}

        return {"success": True}

    def _handle_card_effects(
        self,
        player: Dict[str, Any],
        card: Card,
        chosen_color: Optional[str] = None,
        target_player_id: Optional[str] = None
    ):
        # 1. Update current color
        if card.is_wild:
            self.current_color = chosen_color or random.choice(COLORS)
            self._log_event("color_chosen", f"Color changed to {self.current_color.upper()}.", {"color": self.current_color})
        else:
            self.current_color = card.color

        # 2. Number 0 - Pass all hands in current direction of play
        if card.card_type == TYPE_NUMBER and card.value == 0:
            active = self._get_active_players()
            if len(active) >= 2:
                # Rotate hands in direction of play
                # If direction is 1 (clockwise), player i passes to player i+1
                # so player i receives from player i-1
                old_hands = [p["hand"][:] for p in active]
                num_active = len(active)
                for i in range(num_active):
                    giver_idx = (i - self.direction) % num_active
                    active[i]["hand"] = old_hands[giver_idx]

                self._log_event("pass_hands", "🔄 Number 0 played! All players passed their hands to the next player!")
            self._advance_turn()
            return

        # 3. Number 7 - Swap hand with chosen opponent
        if card.card_type == TYPE_NUMBER and card.value == 7:
            active_opponents = [p for p in self._get_active_players() if p["id"] != player["id"]]
            target = None
            if target_player_id:
                target = next((p for p in active_opponents if p["id"] == target_player_id), None)
            if not target and active_opponents:
                target = active_opponents[0]

            if target:
                player["hand"], target["hand"] = target["hand"], player["hand"]
                self._log_event(
                    "swap_hands",
                    f"🤝 Number 7 played! {player['name']} swapped entire hand with {target['name']}!",
                    {"swapper": player["name"], "target": target["name"]}
                )
            self._advance_turn()
            return

        # 4. Discard All - Discard all cards of matching color from hand
        if card.card_type == TYPE_DISCARD_ALL:
            target_color = card.color
            remaining_hand = []
            discarded_matching = []
            for c in player["hand"]:
                if c.color == target_color:
                    discarded_matching.append(c)
                else:
                    remaining_hand.append(c)

            player["hand"] = remaining_hand
            self.discard_pile.extend(discarded_matching)
            self._log_event(
                "discard_all",
                f"🗑️ {player['name']} dumped {len(discarded_matching)} extra {target_color.upper()} cards!",
                {"count": len(discarded_matching), "color": target_color}
            )
            self._advance_turn()
            return

        # 5. Skip Everyone - Skips all other players; current player plays again!
        if card.card_type == TYPE_SKIP_EVERYONE:
            self._log_event("skip_everyone", f"⚡ {player['name']} played SKIP EVERYONE and takes another turn!")
            # Turn does not advance!
            return

        # 6. Skip - Skips next player
        if card.card_type == TYPE_SKIP:
            next_p = self.players[self._next_player_index(self.current_player_idx, 1)]
            self._log_event("skip_player", f"⏭️ {next_p['name']} was skipped!")
            self._advance_turn(skip_count=1)
            return

        # 7. Reverse - Inverts direction of play (in 2 player, acts like skip)
        if card.card_type == TYPE_REVERSE:
            active = self._get_active_players()
            if len(active) == 2:
                # In 2-player game, Reverse functions as Skip
                other = next(p for p in active if p["id"] != player["id"])
                self._log_event("reverse", f"🔁 Reverse played! {other['name']} was skipped.")
                self._advance_turn(skip_count=1)
            else:
                self.direction *= -1
                self._log_event("reverse", f"🔁 Direction of play REVERSED ({'Clockwise' if self.direction == 1 else 'Counter-Clockwise'}).")
                self._advance_turn()
            return

        # 8. Wild Reverse Draw 4 (+4 Reverse)
        if card.card_type == TYPE_WILD_REVERSE_DRAW_4:
            active = self._get_active_players()
            if len(active) > 2:
                self.direction *= -1
            self.pending_penalty += 4
            self.pending_penalty_value = 4
            self.last_penalty_source_id = player["id"]
            self._log_event(
                "penalty_stack",
                f"🔥 Wild Reverse +4! Penalty is now +{self.pending_penalty}!",
                {"pending_penalty": self.pending_penalty, "value": 4}
            )
            self._advance_turn()
            return

        # 9. Draw Cards (+2, +4, Wild +6, Wild +10) - Stacking rules
        if card.is_draw_card:
            self.pending_penalty += card.penalty
            self.pending_penalty_value = card.penalty
            self.last_penalty_source_id = player["id"]
            self._log_event(
                "penalty_stack",
                f"🔥 {card.display_name} played! Penalty is now +{self.pending_penalty}!",
                {"pending_penalty": self.pending_penalty, "value": card.penalty}
            )
            self._advance_turn()
            return

        # 10. Wild Color Roulette
        if card.card_type == TYPE_WILD_ROULETTE:
            target_color = chosen_color or random.choice(COLORS)
            # Victim is the next player
            victim_idx = self._next_player_index(self.current_player_idx, 1)
            victim = self.players[victim_idx]

            self._log_event(
                "roulette_started",
                f"🎰 WILD COLOR ROULETTE on {victim['name']}! Must draw until hitting {target_color.upper()}!",
                {"victim": victim["name"], "target_color": target_color}
            )

            drawn_count = 0
            while not victim["is_eliminated"]:
                self._reshuffle_if_needed(1)
                if not self.draw_pile:
                    break
                drawn_card = self.draw_pile.pop()
                victim["hand"].append(drawn_card)
                drawn_count += 1

                # Check Mercy knockout
                if len(victim["hand"]) >= MERCY_CARD_LIMIT:
                    self.last_penalty_source_id = player["id"]
                    self._eliminate_player(victim, reason=f"Mercy Rule ({len(victim['hand'])} cards)")
                    break

                # Stop if card matches target color
                if drawn_card.color == target_color or drawn_card.is_wild:
                    break

            if not victim["is_eliminated"]:
                self._log_event(
                    "roulette_finished",
                    f"🎰 {victim['name']} drew {drawn_count} cards before hitting {target_color.upper()}!",
                    {"drawn_count": drawn_count}
                )

            # Victim loses their turn in Roulette
            self._advance_turn(skip_count=1)
            return

        # Standard number card with no special triggers
        self._advance_turn()

    def player_draw(self, player_id: str) -> Dict[str, Any]:
        """
        Player draws cards.
        - If penalty stack is pending: must draw full accumulated penalty!
        - If normal turn and no valid move: draws until playable card is drawn (No Mercy rule)!
        """
        player = self.current_player
        if player["id"] != player_id:
            return {"success": False, "error": "Not your turn."}

        if self.pending_action:
            return {"success": False, "error": f"Waiting for action: {self.pending_action}."}

        # Case 1: Drawing accumulated penalty stack (+2, +4, +6, +10, etc.)
        if self.pending_penalty > 0:
            penalty_count = self.pending_penalty
            drawn_cards = self._draw_cards_to_player(player, penalty_count)

            self._log_event(
                "penalty_drawn",
                f"💥 {player['name']} suffered the penalty and drew {len(drawn_cards)} cards!",
                {"drawn_count": len(drawn_cards), "player_id": player_id}
            )

            # Reset penalty stack
            self.pending_penalty = 0
            self.pending_penalty_value = 0
            self.last_penalty_source_id = None

            # Check if player was eliminated by Mercy
            if not player["is_eliminated"]:
                # Turn ends after taking penalty
                self._advance_turn()

            self._check_victory()
            return {
                "success": True,
                "type": "penalty_drawn",
                "drawn_count": len(drawn_cards),
                "eliminated": player["is_eliminated"]
            }

        # Case 2: Normal Turn - UNO No Mercy "Draw Until You Can Play" rule
        drawn_cards: List[Card] = []
        playable_card: Optional[Card] = None

        while not player["is_eliminated"]:
            self._reshuffle_if_needed(1)
            if not self.draw_pile:
                break

            card = self.draw_pile.pop()
            player["hand"].append(card)
            drawn_cards.append(card)

            # Check Mercy knockout
            if len(player["hand"]) >= MERCY_CARD_LIMIT:
                self._eliminate_player(player, reason=f"Mercy Rule ({len(player['hand'])} cards)")
                break

            # Check if this drawn card is playable
            can_play, _ = self.can_play_card(player_id, card)
            if can_play:
                playable_card = card
                break

        if player["is_eliminated"]:
            self._check_victory()
            return {
                "success": True,
                "type": "eliminated",
                "drawn_count": len(drawn_cards),
                "eliminated": True
            }

        self._log_event(
            "cards_drawn",
            f"{player['name']} drew {len(drawn_cards)} card(s) until finding a playable move.",
            {"drawn_count": len(drawn_cards), "playable_card": playable_card.to_dict() if playable_card else None}
        )

        return {
            "success": True,
            "type": "normal_draw",
            "drawn_count": len(drawn_cards),
            "playable_card": playable_card.to_dict() if playable_card else None
        }

    def call_uno(self, player_id: str) -> Dict[str, Any]:
        """
        Player calls UNO when on 1 card.
        """
        player = next((p for p in self.players if p["id"] == player_id), None)
        if not player or player["is_eliminated"]:
            return {"success": False, "error": "Player not found or eliminated."}

        if len(player["hand"]) > 2:
            return {"success": False, "error": "Cannot call UNO with more than 2 cards!"}

        player["called_uno"] = True
        self._log_event("called_uno", f"🗣️ {player['name']} shouted UNO!", {"player_id": player_id})
        return {"success": True, "message": f"{player['name']} called UNO!"}

    def catch_uno_failure(self, caller_id: str, target_id: str) -> Dict[str, Any]:
        """
        Calling out a player who has 1 card but forgot to say UNO.
        Penalty: 2 cards to target!
        """
        caller = next((p for p in self.players if p["id"] == caller_id), None)
        target = next((p for p in self.players if p["id"] == target_id), None)

        if not caller or not target or target["is_eliminated"]:
            return {"success": False, "error": "Invalid players."}

        if len(target["hand"]) == 1 and not target["called_uno"]:
            drawn = self._draw_cards_to_player(target, 2)
            self._log_event(
                "uno_caught",
                f"🚨 {caller['name']} caught {target['name']} forgetting UNO! +2 penalty cards!",
                {"target_id": target_id, "caller_id": caller_id}
            )
            return {"success": True, "message": f"{target['name']} drew 2 penalty cards!"}

        return {"success": False, "error": f"{target['name']} cannot be penalized."}

    def resolve_action(self, player_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resolves pending interactive choices (color picker, 7-hand swap, roulette color).
        """
        if not self.pending_action or self.action_player_id != player_id:
            return {"success": False, "error": "No pending action for you."}

        card_id = self.action_context.get("card_id")

        if self.pending_action == "choose_color":
            chosen_color = payload.get("color")
            if chosen_color not in COLORS:
                return {"success": False, "error": "Invalid color."}
            return self.play_card(player_id, card_id, chosen_color=chosen_color)

        elif self.pending_action == "swap_hand":
            target_id = payload.get("target_player_id")
            chosen_color = self.action_context.get("chosen_color")
            return self.play_card(player_id, card_id, chosen_color=chosen_color, target_player_id=target_id)

        elif self.pending_action == "choose_roulette_color":
            chosen_color = payload.get("color")
            if chosen_color not in COLORS:
                return {"success": False, "error": "Invalid color."}
            return self.play_card(player_id, card_id, chosen_color=chosen_color)

        return {"success": False, "error": "Unknown pending action."}

    def get_player_view(self, player_id: str) -> Dict[str, Any]:
        """
        Returns serialized game state tailored for a specific player:
        - Own hand cards are fully visible.
        - Other players' hands only expose card counts.
        - Valid card IDs for current turn are highlighted.
        """
        player = next((p for p in self.players if p["id"] == player_id), None)
        valid_card_ids = self.get_valid_cards_for_player(player_id) if player else []

        players_view = []
        for p in self.players:
            p_data = {
                "id": p["id"],
                "name": p["name"],
                "avatar": p["avatar"],
                "card_count": len(p["hand"]),
                "is_eliminated": p["is_eliminated"],
                "eliminated_reason": p["eliminated_reason"],
                "called_uno": p["called_uno"],
                "knockouts_caused": p["knockouts_caused"],
                "is_current": (not self.game_over and self.players[self.current_player_idx]["id"] == p["id"]),
                "is_danger": len(p["hand"]) >= (MERCY_CARD_LIMIT - 5)  # 20+ cards danger alert
            }
            players_view.append(p_data)

        own_hand = [c.to_dict() for c in player["hand"]] if player else []

        return {
            "room_code": self.room_code,
            "direction": self.direction,  # 1: CW, -1: CCW
            "current_player_id": self.current_player["id"] if not self.game_over else None,
            "current_player_name": self.current_player["name"] if not self.game_over else None,
            "current_color": self.current_color,
            "top_card": self.top_card.to_dict() if self.top_card else None,
            "draw_pile_count": len(self.draw_pile),
            "discard_pile_count": len(self.discard_pile),
            "pending_penalty": self.pending_penalty,
            "pending_penalty_value": self.pending_penalty_value,
            "pending_action": self.pending_action if self.action_player_id == player_id else None,
            "action_context": self.action_context if self.action_player_id == player_id else {},
            "game_over": self.game_over,
            "winner": self.winner,
            "win_reason": self.win_reason,
            "mercy_limit": MERCY_CARD_LIMIT,
            "players": players_view,
            "my_hand": own_hand,
            "my_valid_cards": valid_card_ids,
            "can_draw": (player and not player["is_eliminated"] and self.current_player["id"] == player_id and not self.pending_action),
            "can_call_uno": (player and not player["is_eliminated"] and len(player["hand"]) <= 2 and not player["called_uno"]),
            "recent_events": self.event_log[-8:]
        }

