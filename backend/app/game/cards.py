import uuid
import random
from typing import List, Dict, Any, Optional

COLORS = ["red", "yellow", "green", "blue"]

# Card type constants
TYPE_NUMBER = "number"
TYPE_SKIP = "skip"
TYPE_SKIP_EVERYONE = "skip_everyone"
TYPE_REVERSE = "reverse"
TYPE_DRAW_2 = "draw_2"
TYPE_DRAW_4 = "draw_4"
TYPE_DISCARD_ALL = "discard_all"
TYPE_WILD_ROULETTE = "wild_roulette"
TYPE_WILD_REVERSE_DRAW_4 = "wild_reverse_draw_4"
TYPE_WILD_DRAW_6 = "wild_draw_6"
TYPE_WILD_DRAW_10 = "wild_draw_10"

class Card:
    def __init__(
        self,
        card_id: str,
        color: str,
        card_type: str,
        value: Optional[int] = None,
        penalty: int = 0
    ):
        self.id = card_id
        self.color = color  # "red", "yellow", "green", "blue", or "wild"
        self.card_type = card_type
        self.value = value  # 0-9 for number cards, None for others
        self.penalty = penalty  # 2, 4, 6, 10 for draw cards

    @property
    def is_wild(self) -> bool:
        return self.color == "wild"

    @property
    def is_draw_card(self) -> bool:
        return self.penalty > 0

    @property
    def display_name(self) -> str:
        if self.card_type == TYPE_NUMBER:
            return f"{self.color.capitalize()} {self.value}"
        elif self.card_type == TYPE_SKIP:
            return f"{self.color.capitalize()} Skip"
        elif self.card_type == TYPE_SKIP_EVERYONE:
            return f"{self.color.capitalize()} Skip Everyone"
        elif self.card_type == TYPE_REVERSE:
            return f"{self.color.capitalize()} Reverse"
        elif self.card_type == TYPE_DRAW_2:
            return f"{self.color.capitalize()} +2"
        elif self.card_type == TYPE_DRAW_4:
            return f"{self.color.capitalize()} +4"
        elif self.card_type == TYPE_DISCARD_ALL:
            return f"{self.color.capitalize()} Discard All"
        elif self.card_type == TYPE_WILD_ROULETTE:
            return "Wild Color Roulette"
        elif self.card_type == TYPE_WILD_REVERSE_DRAW_4:
            return "Wild Reverse +4"
        elif self.card_type == TYPE_WILD_DRAW_6:
            return "Wild +6"
        elif self.card_type == TYPE_WILD_DRAW_10:
            return "Wild +10"
        return "Unknown Card"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "color": self.color,
            "card_type": self.card_type,
            "value": self.value,
            "penalty": self.penalty,
            "display_name": self.display_name,
            "is_wild": self.is_wild
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Card":
        return cls(
            card_id=data["id"],
            color=data["color"],
            card_type=data["card_type"],
            value=data.get("value"),
            penalty=data.get("penalty", 0)
        )


def build_no_mercy_deck() -> List[Card]:
    """
    Builds the official 168-card UNO Show 'Em No Mercy deck.
    """
    deck: List[Card] = []

    # 1. Number Cards: 0 to 9 in each of the 4 colors (2 each = 80 cards)
    for color in COLORS:
        for num in range(10):
            for i in range(2):
                deck.append(Card(
                    card_id=f"{color}_{num}_{i+1}_{uuid.uuid4().hex[:6]}",
                    color=color,
                    card_type=TYPE_NUMBER,
                    value=num
                ))

    # 2. Action Colored Cards
    for color in COLORS:
        # Skip: 3 per color (12 cards)
        for i in range(3):
            deck.append(Card(
                card_id=f"{color}_skip_{i+1}_{uuid.uuid4().hex[:6]}",
                color=color,
                card_type=TYPE_SKIP
            ))

        # Skip Everyone: 2 per color (8 cards)
        for i in range(2):
            deck.append(Card(
                card_id=f"{color}_skip_everyone_{i+1}_{uuid.uuid4().hex[:6]}",
                color=color,
                card_type=TYPE_SKIP_EVERYONE
            ))

        # Reverse: 3 per color (12 cards)
        for i in range(3):
            deck.append(Card(
                card_id=f"{color}_reverse_{i+1}_{uuid.uuid4().hex[:6]}",
                color=color,
                card_type=TYPE_REVERSE
            ))

        # Draw 2 (+2): 3 per color (12 cards)
        for i in range(3):
            deck.append(Card(
                card_id=f"{color}_draw2_{i+1}_{uuid.uuid4().hex[:6]}",
                color=color,
                card_type=TYPE_DRAW_2,
                penalty=2
            ))

        # Draw 4 (+4): 2 per color (8 cards)
        for i in range(2):
            deck.append(Card(
                card_id=f"{color}_draw4_{i+1}_{uuid.uuid4().hex[:6]}",
                color=color,
                card_type=TYPE_DRAW_4,
                penalty=4
            ))

        # Discard All: 3 per color (12 cards)
        for i in range(3):
            deck.append(Card(
                card_id=f"{color}_discard_all_{i+1}_{uuid.uuid4().hex[:6]}",
                color=color,
                card_type=TYPE_DISCARD_ALL
            ))

    # 3. Wild Cards
    # Wild Color Roulette: 8 cards
    for i in range(8):
        deck.append(Card(
            card_id=f"wild_roulette_{i+1}_{uuid.uuid4().hex[:6]}",
            color="wild",
            card_type=TYPE_WILD_ROULETTE
        ))

    # Wild Reverse Draw 4: 8 cards
    for i in range(8):
        deck.append(Card(
            card_id=f"wild_reverse_draw4_{i+1}_{uuid.uuid4().hex[:6]}",
            color="wild",
            card_type=TYPE_WILD_REVERSE_DRAW_4,
            penalty=4
        ))

    # Wild Draw 6: 4 cards
    for i in range(4):
        deck.append(Card(
            card_id=f"wild_draw6_{i+1}_{uuid.uuid4().hex[:6]}",
            color="wild",
            card_type=TYPE_WILD_DRAW_6,
            penalty=6
        ))

    # Wild Draw 10: 4 cards
    for i in range(4):
        deck.append(Card(
            card_id=f"wild_draw10_{i+1}_{uuid.uuid4().hex[:6]}",
            color="wild",
            card_type=TYPE_WILD_DRAW_10,
            penalty=10
        ))

    return deck

