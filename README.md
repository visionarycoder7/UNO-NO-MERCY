# UNO Show 'Em No Mercy — Multiplayer Web Game

A full-stack, real-time multiplayer implementation of **UNO Show 'Em No Mercy** for **2 to 6 players**. Built strictly following the multi-tier system architecture:

```
┌────────────────────────────────────────────────────────┐
│               Frontend — Game Interface                │
│            Browser / HTML / CSS / JavaScript           │
│             Login • Lobby • Cards • Game Table         │
└──────────────────────────┬─────────────────────────────┘
                           │ HTTP + WebSocket
┌──────────────────────────▼─────────────────────────────┐
│                 Python Backend — FastAPI               │
│          Authentication • Room Manager • Game Engine   │
│         Turn Validation • Real-time Communication      │
└──────────────┬──────────────────────────┬──────────────┘
               │                          │
┌──────────────▼──────────┐    ┌──────────▼──────────────┐
│       PostgreSQL        │    │          Redis          │
│ Accounts • Profiles     │    │ Active rooms            │
│ Match history           │    │ Temporary game state    │
└─────────────────────────┘    └─────────────────────────┘
```

---

## ⚡ Key Features & Official "No Mercy" Rules

### 1. The 168-Card Deck
- **Number Cards (0-9 in 4 colors, 2 of each = 80 cards)**:
  - **`0` Cards**: *Table-wide Hand Pass* — Every active player passes their entire hand to the next player in the current direction of play.
  - **`7` Cards**: *Targeted Hand Swap* — The player who plays a 7 chooses any opponent and swaps entire hands with them!
- **Action Cards (12 Skip, 8 Skip Everyone, 12 Reverse, 12 Draw 2, 8 Draw 4, 12 Discard All)**:
  - **`Skip Everyone`**: Skips all other players — you get another turn immediately!
  - **`Discard All`**: Discards this card plus every single card of that color currently in your hand!
- **Wild Cards (8 Color Roulette, 8 Wild Reverse +4, 4 Wild +6, 4 Wild +10)**:
  - **`Wild Color Roulette`**: Next player chooses a color and must draw from the deck one-by-one until they hit that color!
  - **`Wild Reverse Draw 4`**: Reverses play direction AND stacks +4 on the next player in that direction!

### 2. Penalty Stacking (+2, +4, +6, +10)
- Draw penalty cards can be stacked! You can pass the penalty along to the next player by playing a draw card of **equal or higher value** (e.g. +4 on +2; +6 on +4; +10 on +6).
- If you cannot or choose not to stack, you must draw the accumulated penalty total (which can reach +16, +20 or more)!

### 3. The 25-Card Mercy Rule
- If any player accumulates **25 or more cards** in their hand at any point, they are immediately **knocked out (eliminated)** from the match!
- Last surviving player wins!

### 4. Draw Until Playable
- In normal turns, if you don't have a playable card, you draw from the deck until you find a card that can be played (or hit 25 cards and get eliminated)!

### 5. Multiplayer Room Management (2 to 6 Players)
- Host creates a room with custom player limit (2 to 6).
- Unique 6-character room code with one-click copy to invite friends.
- Real-time WebSockets synchronization of table state, player hands, active color halo, and directional arrows.
- Live in-game chat and quick reaction emotes (🔥, 💀, 😈, 🤡, 🚨, 👏).
- Zero external audio assets needed: procedural Web Audio synthesizer generates authentic card swooshes, draw pops, penalty sirens, knockout explosions, and victory fanfares.

---

## 🚀 How to Run

### 1. Activate Environment & Install Dependencies
```bash
# If using existing venv:
.\venv\Scripts\activate

# Install requirements:
pip install -r requirements.txt
```

### 2. Launch the Application
```bash
python main.py
```
Open **[http://localhost:8000](http://localhost:8000)** in your browser!

### 3. Playing with Friends
- **Single Machine Testing**: Open two or more browser tabs (or an Incognito window) at `http://localhost:8000`. Create a room in tab 1, copy the 6-character code, and join from tab 2.
- **Local Network (LAN)**: Run `python main.py` and share your local IP address (e.g. `http://192.168.1.X:8000`) with friends on the same Wi-Fi.

---

## 🗄️ Database & Redis Configuration (Optional Production Setup)
By default, the backend connects to built-in **SQLite** (`uno_no_mercy.db`) and uses an **in-memory thread-safe room store**, allowing immediate local play with zero setup.

To connect external PostgreSQL and Redis instances (as pictured in the architecture diagram):
```bash
set DATABASE_URL=postgresql://username:password@localhost:5432/uno_db
set REDIS_URL=redis://localhost:6379/0
python main.py
```

