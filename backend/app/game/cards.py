import uuid
import random
from typing import List, Dict, Any, Optional

# Color mapping: R, Y, G, B, W (matching UNO No Mercy.html)
COLOR_NAMES = {
    "R": "Red",
    "Y": "Yellow",
    "G": "Green",
    "B": "Blue",
    "W": "Wild"
}
COLOR_CODES = ["R", "Y", "G", "B"]

# Type constants matching UNO No Mercy.html
TYPE_SKIP = "skip"
TYPE_REV = "rev"
TYPE_D2 = "d2"
TYPE_DISCARD = "discard"
TYPE_D4 = "d4"
TYPE_SKIPALL = "skipall"
TYPE_WRD4 = "wrd4"
TYPE_WD6 = "wd6"
TYPE_WD10 = "wd10"
TYPE_ROUL = "roul"

TYPE_NAMES = {
    "skip": "Skip",
    "rev": "Reverse",
    "d2": "Draw 2",
    "discard": "Discard All",
    "d4": "Draw 4",
    "skipall": "Skip Everyone",
    "wrd4": "Wild Reverse Draw 4",
    "wd6": "Wild Draw 6",
    "wd10": "Wild Draw 10",
    "roul": "Wild Color Roulette"
}

DRAW_VALUES = {
    "d2": 2,
    "d4": 4,
    "wrd4": 4,
    "wd6": 6,
    "wd10": 10
}

# Mapping to asset webp files
ASSET_COLOR_MAP = {
    "R": "red",
    "Y": "yellow",
    "G": "green",
    "B": "blue"
}

ASSET_TYPE_MAP = {
    "skip": "skip",
    "rev": "reverse",
    "d2": "draw2",
    "discard": "discard_all",
    "d4": "draw4",
    "skipall": "skip_all",
    "wrd4": "draw4",
    "wd6": "draw6",
    "wd10": "draw10",
    "roul": "roulette"
}

class Card:
    def __init__(
        self,
        color_or_id: str,
        card_type_or_color: str,
        card_type: Optional[str] = None,
        card_id: Optional[str] = None
    ):
        if card_type is not None:
            self.id = color_or_id
            self.color = card_type_or_color
            self.card_type = card_type
        else:
            self.color = color_or_id
            self.card_type = card_type_or_color
            self.id = card_id or f"{self.color}_{self.card_type}_{uuid.uuid4().hex[:6]}"

    @property
    def is_wild(self) -> bool:
        return self.color == "W"

    @property
    def draw_val(self) -> int:
        return DRAW_VALUES.get(self.card_type, 0)

    @property
    def is_draw_card(self) -> bool:
        return self.draw_val > 0

    @property
    def display_name(self) -> str:
        color_name = (COLOR_NAMES[self.color] + " ") if self.color != "W" else ""
        type_name = self.card_type if self.card_type.isdigit() else TYPE_NAMES.get(self.card_type, self.card_type)
        return color_name + type_name

    @property
    def image_url(self) -> str:
        if self.is_wild:
            asset_type = ASSET_TYPE_MAP.get(self.card_type, self.card_type)
            return f"/static/cards/wild_{asset_type}.webp"
        
        asset_color = ASSET_COLOR_MAP.get(self.color, "red")
        asset_type = ASSET_TYPE_MAP.get(self.card_type, self.card_type)
        return f"/static/cards/{asset_color}_{asset_type}.webp"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "color": self.color,
            "type": self.card_type,
            "draw_val": self.draw_val,
            "display_name": self.display_name,
            "is_wild": self.is_wild,
            "image_url": self.image_url
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Card":
        return cls(
            card_id=data["id"],
            color=data["color"],
            card_type=data.get("type", data.get("card_type"))
        )


def build_no_mercy_deck() -> List[Card]:
    """
    Builds the exact 168-card deck from UNO No Mercy.html:
    - 2 of each number 0..9 per color R, Y, G, B (80 cards)
    - 3 of each: skip, rev, d2, discard per color (48 cards)
    - 2 of each: d4, skipall per color (16 cards)
    - 8 of wrd4, 8 of wd6 (16 cards)
    - 4 of wd10, 4 of roul (8 cards)
    Total = 80 + 48 + 16 + 16 + 8 = 168 cards.
    """
    deck: List[Card] = []

    # Colored cards (144 cards)
    for c in COLOR_CODES:
        for n in range(10):
            deck.append(Card(f"{c}_{n}_1_{uuid.uuid4().hex[:6]}", c, str(n)))
            deck.append(Card(f"{c}_{n}_2_{uuid.uuid4().hex[:6]}", c, str(n)))

        for i in range(3):
            deck.append(Card(f"{c}_skip_{i+1}_{uuid.uuid4().hex[:6]}", c, TYPE_SKIP))
            deck.append(Card(f"{c}_rev_{i+1}_{uuid.uuid4().hex[:6]}", c, TYPE_REV))
            deck.append(Card(f"{c}_d2_{i+1}_{uuid.uuid4().hex[:6]}", c, TYPE_D2))
            deck.append(Card(f"{c}_discard_{i+1}_{uuid.uuid4().hex[:6]}", c, TYPE_DISCARD))

        for i in range(2):
            deck.append(Card(f"{c}_d4_{i+1}_{uuid.uuid4().hex[:6]}", c, TYPE_D4))
            deck.append(Card(f"{c}_skipall_{i+1}_{uuid.uuid4().hex[:6]}", c, TYPE_SKIPALL))

    # Wild cards (24 cards)
    for i in range(8):
        deck.append(Card(f"W_wrd4_{i+1}_{uuid.uuid4().hex[:6]}", "W", TYPE_WRD4))
        deck.append(Card(f"W_wd6_{i+1}_{uuid.uuid4().hex[:6]}", "W", TYPE_WD6))

    for i in range(4):
        deck.append(Card(f"W_wd10_{i+1}_{uuid.uuid4().hex[:6]}", "W", TYPE_WD10))
        deck.append(Card(f"W_roul_{i+1}_{uuid.uuid4().hex[:6]}", "W", TYPE_ROUL))

    return deck


create_deck = build_no_mercy_deck
