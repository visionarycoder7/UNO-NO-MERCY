import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    avatar = Column(String(50), default="avatar1")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    games_played = Column(Integer, default=0)
    games_won = Column(Integer, default=0)
    knockouts_caused = Column(Integer, default=0)

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "avatar": self.avatar,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "games_played": self.games_played,
            "games_won": self.games_won,
            "knockouts_caused": self.knockouts_caused,
            "win_rate": round((self.games_won / self.games_played * 100), 1) if self.games_played > 0 else 0.0
        }

class MatchHistory(Base):
    __tablename__ = "match_history"

    id = Column(Integer, primary_key=True, index=True)
    room_code = Column(String(10), index=True, nullable=False)
    winner_name = Column(String(50), nullable=False)
    total_players = Column(Integer, default=2)
    win_reason = Column(String(100), default="Emptied Hand") # e.g. "Emptied Hand" or "Last Survivor (Mercy Rule)"
    duration_seconds = Column(Integer, default=0)
    finished_at = Column(DateTime, default=datetime.datetime.utcnow)
    player_summary = Column(JSON, default=list)

    def to_dict(self):
        return {
            "id": self.id,
            "room_code": self.room_code,
            "winner_name": self.winner_name,
            "total_players": self.total_players,
            "win_reason": self.win_reason,
            "duration_seconds": self.duration_seconds,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "player_summary": self.player_summary
        }

