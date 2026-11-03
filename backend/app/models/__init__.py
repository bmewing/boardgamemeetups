"""ORM models. Import every model module here so Alembic autogenerate sees it."""

from app.db import Base
from app.models.bgg_throttle import BggThrottle
from app.models.game import Game, PlayerCountVotes
from app.models.mood import Mood
from app.models.user import CollectionVisibility, User
from app.models.user_game import (
    Ownership,
    PlayerCountVote,
    PlaytimeFeel,
    Source,
    UserGame,
    UserGameMood,
    UserGamePlayerCount,
)

__all__ = [
    "Base",
    "BggThrottle",
    "CollectionVisibility",
    "Game",
    "Mood",
    "Ownership",
    "PlayerCountVote",
    "PlayerCountVotes",
    "PlaytimeFeel",
    "Source",
    "User",
    "UserGame",
    "UserGameMood",
    "UserGamePlayerCount",
]
