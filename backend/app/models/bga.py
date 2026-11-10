"""Games on Board Game Arena, linked to the catalog's games so nothing is stored twice."""

from datetime import datetime

from sqlalchemy import ARRAY, Boolean, DateTime, ForeignKey, Integer, SmallInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

BGA_URL = "https://boardgamearena.com"


class BgaGame(Base):
    """One game BGA offers. Only what BGA says about playing it there lives here; the game
    itself (name, art, ratings, what people think of it) is the linked catalog game.

    Loaded by hand from a saved copy of BGA's game list (app.import_bga)."""

    __tablename__ = "bga_games"

    # BGA's own number for the game, as in its "start a table" link.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    # BGA's short name, as in its game page link.
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    # The catalog game; null when BGA gives no BGG id and no name matched. Two BGA games
    # can share one catalog game.
    game_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("games.id", ondelete="SET NULL"), index=True
    )
    # Only a Premium member can start a table; anyone can join one.
    premium: Mapped[bool] = mapped_column(Boolean)
    # The player counts BGA allows, which can differ from the box.
    player_counts: Mapped[list[int]] = mapped_column(ARRAY(SmallInteger))
    status: Mapped[str] = mapped_column(String(16))  # "public" or "beta"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    @property
    def game_url(self) -> str:
        return f"{BGA_URL}/gamepanel?game={self.slug}"

    @property
    def lobby_url(self) -> str:
        return f"{BGA_URL}/lobby?game={self.id}"
