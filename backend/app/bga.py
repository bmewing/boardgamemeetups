"""Board Game Arena: which catalog games can be played there, and links to play them."""

from collections.abc import Iterable

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.groups import TableFit
from app.models import BgaGame, Meetup

# Where an online date happens, for calendars and emails, in place of a place.
BGA_PLACE = "Board Game Arena"


class BgaLink(BaseModel):
    """A catalog game as BGA offers it."""

    id: int
    slug: str
    name: str
    premium: bool  # only a Premium member can start a table; anyone can join one
    player_counts: list[int]  # what BGA allows, which can differ from the box
    status: str  # "public" or "beta"
    game_url: str  # BGA's page for the game
    lobby_url: str  # where to start a table of it

    @classmethod
    def of(cls, bga: BgaGame) -> "BgaLink":
        return cls(
            id=bga.id,
            slug=bga.slug,
            name=bga.name,
            premium=bga.premium,
            player_counts=bga.player_counts,
            status=bga.status,
            game_url=bga.game_url,
            lobby_url=bga.lobby_url,
        )


def preferred(bga: BgaGame) -> tuple[bool, bool, int]:
    """When BGA has a catalog game twice, the released, free one comes first."""
    return (bga.status != "public", bga.premium, bga.id)


async def bga_games_for(session: AsyncSession, game_ids: Iterable[int]) -> dict[int, BgaGame]:
    """The BGA game for each of these catalog games that's on BGA."""
    ids = set(game_ids)
    if not ids:
        return {}
    found: dict[int, BgaGame] = {}
    for bga in await session.scalars(select(BgaGame).where(BgaGame.game_id.in_(ids))):
        assert bga.game_id is not None
        best = found.get(bga.game_id)
        if best is None or preferred(bga) < preferred(best):
            found[bga.game_id] = bga
    return found


async def links_for(session: AsyncSession, game_ids: Iterable[int]) -> dict[int, BgaLink]:
    return {
        game_id: BgaLink.of(bga)
        for game_id, bga in (await bga_games_for(session, game_ids)).items()
    }


def counts_fit(counts: list[int], players: int, willing_to_split: bool) -> TableFit | None:
    """`groups.table_fit` for BGA's player counts, which can skip numbers (2 or 4, not 3)."""
    if players < 1 or not counts:
        return None
    if players in counts:
        return "together"
    if willing_to_split and any(t in counts for t in range(2, players - 1)):
        return "split"
    return None


def biggest_table(counts: list[int], players: int) -> int:
    """The biggest table BGA seats that still leaves two for another table."""
    return max(t for t in counts if 2 <= t < players - 1)


def place_of(meetup: Meetup) -> str | None:
    """Where a date happens, for emails, calendars and Discord: the place, or for an online
    date Board Game Arena and its table link."""
    if meetup.is_online:
        return f"{BGA_PLACE}: {meetup.online_url}" if meetup.online_url else BGA_PLACE
    return meetup.location
