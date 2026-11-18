import os

# Database & Cache configuration
# Defaults to SQLite and In-Memory fallback for instant out-of-the-box local testing,
# but seamlessly switches to PostgreSQL & Redis when provided via environment variables.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./uno_no_mercy.db")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Game Rules
MIN_PLAYERS = 2
MAX_PLAYERS = 6
INITIAL_HAND_SIZE = 7
MERCY_CARD_LIMIT = 25

# Server configuration
SECRET_KEY = os.getenv("SECRET_KEY", "uno-no-mercy-secret-token-key-2026")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

