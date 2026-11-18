import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from backend.app.config import DATABASE_URL
from backend.app.models.db_models import Base, User, MatchHistory

logger = logging.getLogger("uno.database")

# Handle SQLite vs PostgreSQL connect_args
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

try:
    engine = create_engine(DATABASE_URL, connect_args=connect_args)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    logger.info(f"Database connected using: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL}")
except Exception as e:
    logger.error(f"Failed to connect to database {DATABASE_URL}: {e}. Falling back to SQLite.")
    engine = create_engine("sqlite:///./uno_no_mercy.db", connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# User helpers
def get_or_create_user(db: Session, username: str, avatar: str = "avatar1") -> User:
    username = username.strip()
    user = db.query(User).filter(User.username.ilike(username)).first()
    if not user:
        user = User(username=username, avatar=avatar)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user

def record_match_result(db: Session, room_code: str, winner_name: str, total_players: int, win_reason: str, duration_seconds: int, player_stats: list):
    try:
        # Create match history record
        match = MatchHistory(
            room_code=room_code,
            winner_name=winner_name,
            total_players=total_players,
            win_reason=win_reason,
            duration_seconds=duration_seconds,
            player_summary=player_stats
        )
        db.add(match)

        # Update each player's user stats
        for p in player_stats:
            user = db.query(User).filter(User.username.ilike(p.get("name", ""))).first()
            if user:
                user.games_played += 1
                if p.get("name", "").lower() == winner_name.lower():
                    user.games_won += 1
                user.knockouts_caused += p.get("knockouts_caused", 0)

        db.commit()
        return match
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to record match result: {e}")
        return None

def get_recent_matches(db: Session, limit: int = 10):
    return db.query(MatchHistory).order_by(MatchHistory.finished_at.desc()).limit(limit).all()

def get_leaderboard(db: Session, limit: int = 10):
    return db.query(User).order_by(User.games_won.desc(), User.knockouts_caused.desc()).limit(limit).all()

