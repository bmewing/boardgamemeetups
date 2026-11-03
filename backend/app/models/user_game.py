"""What one user records about one game: ownership, opinions, and whether they can teach it.

There is one row per user per game, owned or not, so a user can rate or tag any game. Blank
(NULL) always means "no answer"; the UI may show a default without it being stored, so
group results only count real answers.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    false,
    func,
    text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _string_enum[E: StrEnum](enum: type[E]) -> Enum:
    """Store a StrEnum as its values in a plain string column (no Postgres enum type)."""
    return Enum(
        enum,
        native_enum=False,
        length=32,
        values_callable=lambda members: [member.value for member in members],
    )


class Ownership(StrEnum):
    OWNED = "owned"
    PREORDERED = "preordered"
    PREVIOUSLY_OWNED = "previously_owned"


class PlaytimeFeel(StrEnum):
    """How the game's length feels next to BGG's listed playing time."""

    SHORTER = "shorter"
    JUST_RIGHT = "just_right"
    LONGER = "longer"


class PlayerCountVote(StrEnum):
    """The same three answers as BGG's suggested-player-count poll."""

    BEST = "best"
    RECOMMENDED = "recommended"
    NOT_RECOMMENDED = "not_recommended"


class Source(StrEnum):
    """Where a row first came from."""

    BGG = "bgg"
    FILE = "file"
    MANUAL = "manual"


class UserGame(Base):
    __tablename__ = "user_games"
    __table_args__ = (
        CheckConstraint("wishlist_priority BETWEEN 1 AND 5", name="wishlist_priority_range"),
        CheckConstraint("rating BETWEEN 1 AND 10", name="rating_range"),
        CheckConstraint("weight_vote BETWEEN 1 AND 5", name="weight_vote_range"),
        CheckConstraint("teach_minutes > 0", name="teach_minutes_positive"),
        CheckConstraint("NOT can_teach OR teach_minutes IS NOT NULL", name="teacher_has_time"),
        CheckConstraint("plays >= 0", name="plays_not_negative"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    # Indexed on its own for group roll-ups, which look up every member's row for a game.
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), primary_key=True, index=True)

    ownership: Mapped[Ownership | None] = mapped_column(_string_enum(Ownership))
    wishlist_priority: Mapped[int | None] = mapped_column(Integer)  # 1 (must have) … 5
    want_to_play: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    rating: Mapped[float | None] = mapped_column(Float)  # BGG's 1 to 10 scale, decimals allowed
    weight_vote: Mapped[int | None] = mapped_column(Integer)  # BGG's 1 (light) … 5 (heavy)
    playtime_feel: Mapped[PlaytimeFeel | None] = mapped_column(_string_enum(PlaytimeFeel))
    can_teach: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    teach_minutes: Mapped[int | None] = mapped_column(Integer)
    plays: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    # Only meaningful for an owned copy: no for one that's lent out or never leaves home.
    will_bring: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    notes: Mapped[str | None] = mapped_column(Text)

    source: Mapped[Source] = mapped_column(_string_enum(Source))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    player_counts: Mapped[list["UserGamePlayerCount"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, lazy="selectin"
    )
    moods: Mapped[list["UserGameMood"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, lazy="selectin"
    )


class UserGamePlayerCount(Base):
    __tablename__ = "user_game_player_counts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id", "game_id"],
            ["user_games.user_id", "user_games.game_id"],
            ondelete="CASCADE",
        ),
        CheckConstraint("players > 0", name="players_positive"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    players: Mapped[int] = mapped_column(Integer, primary_key=True)
    vote: Mapped[PlayerCountVote] = mapped_column(_string_enum(PlayerCountVote))


class UserGameMood(Base):
    __tablename__ = "user_game_moods"
    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id", "game_id"],
            ["user_games.user_id", "user_games.game_id"],
            ondelete="CASCADE",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mood_id: Mapped[str] = mapped_column(String(32), ForeignKey("moods.id"), primary_key=True)
