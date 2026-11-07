import uuid
from datetime import datetime

from sqlalchemy import (
    ARRAY,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Sequence,
    String,
    false,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

EMPTY_ARRAY = text("'{}'")

# {"3": {"best": 1270, "recommended": 611, "not_recommended": 26}, "5+": {...}}
PlayerCountVotes = dict[str, dict[str, int]]


# Games people add that aren't on BGG count down from -1, so they never clash with BGG's ids.
CUSTOM_GAME_IDS = Sequence(
    "custom_game_ids",
    start=-1,
    increment=-1,
    maxvalue=-1,
    minvalue=-(2**31),
    metadata=Base.metadata,
)


class Game(Base):
    """A BoardGameGeek item, cached locally, or a game someone added that BGG doesn't list.

    BGG rows can start as stubs (name and year only, from the ranks CSV or a BGG search) and
    gain full details the first time they are looked at; `details_fetched_at` says which is
    which.

    Custom games (negative ids, see `is_custom`) are never looked up on BGG, and stay out of
    searches and import matching: people find them in each other's collections instead.
    """

    __tablename__ = "games"
    __table_args__ = (
        # Fuzzy and substring name search (pg_trgm). Alembic can create this index but not
        # compare it, so changes to it need a hand-written migration.
        Index("ix_games_name_trgm", text("lower(name) gin_trgm_ops"), postgresql_using="gin"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(512))
    year_published: Mapped[int | None] = mapped_column(Integer)
    is_expansion: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    base_game_ids: Mapped[list[int]] = mapped_column(
        ARRAY(Integer), default=list, server_default=EMPTY_ARRAY
    )

    bgg_rank: Mapped[int | None] = mapped_column(Integer)
    bgg_rating: Mapped[float | None] = mapped_column(Float)
    bgg_users_rated: Mapped[int | None] = mapped_column(Integer)

    thumbnail_url: Mapped[str | None] = mapped_column(String(1024))
    image_url: Mapped[str | None] = mapped_column(String(1024))
    min_players: Mapped[int | None] = mapped_column(Integer)
    max_players: Mapped[int | None] = mapped_column(Integer)
    min_playtime: Mapped[int | None] = mapped_column(Integer)
    max_playtime: Mapped[int | None] = mapped_column(Integer)
    playing_time: Mapped[int | None] = mapped_column(Integer)
    min_age: Mapped[int | None] = mapped_column(Integer)
    weight: Mapped[float | None] = mapped_column(Float)
    categories: Mapped[list[str]] = mapped_column(
        ARRAY(String(128)), default=list, server_default=EMPTY_ARRAY
    )
    mechanics: Mapped[list[str]] = mapped_column(
        ARRAY(String(128)), default=list, server_default=EMPTY_ARRAY
    )
    player_count_votes: Mapped[PlayerCountVotes | None] = mapped_column(JSONB)

    # Who added a custom game; they can edit it. Null for BGG games, or if they've left.
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    details_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    @property
    def is_custom(self) -> bool:
        return is_custom_id(self.id)


def is_custom_id(game_id: int) -> bool:
    """Whether this id is a game someone added (not on BGG)."""
    return game_id < 0
