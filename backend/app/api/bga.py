from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.api.games import GameSummary
from app.auth import CurrentUser
from app.bga import BgaLink, preferred
from app.db import SessionDep
from app.matching import normalize
from app.models import BgaGame, Game

router = APIRouter(prefix="/bga", tags=["bga"])


class BgaGameRead(BgaLink):
    game: GameSummary  # the catalog game it is


def _like(text: str) -> str:
    return "%" + text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


@router.get("/games")
async def search_bga_games(
    _user: CurrentUser,
    session: SessionDep,
    q: Annotated[str, Query(min_length=2, max_length=100)],
    players: Annotated[int | None, Query(ge=1, le=100)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[BgaGameRead]:
    """Games on Board Game Arena by name, for nominating at an online date. Only games
    linked to the catalog are listed, since a nomination is of a catalog game. `players`
    keeps the ones BGA seats that many at. A game BGA lists twice is shown once."""
    text = normalize(q)
    name = func.lower(BgaGame.name)
    query = (
        select(BgaGame, Game)
        .join(Game, Game.id == BgaGame.game_id)
        .where(name.like(_like(text), escape="\\"))
        .order_by(
            (name == text).desc(),
            name.startswith(text, autoescape=True).desc(),
            Game.bgg_users_rated.desc().nulls_last(),
            BgaGame.name,
        )
        .limit(limit * 2)  # room for games listed twice
    )
    if players is not None:
        query = query.where(BgaGame.player_counts.any_() == players)
    best: dict[int, tuple[BgaGame, Game]] = {}
    for bga, game in await session.execute(query):
        if game.id not in best or preferred(bga) < preferred(best[game.id][0]):
            best[game.id] = (bga, game)
    return [
        BgaGameRead(**BgaLink.of(bga).model_dump(), game=GameSummary.from_game(game))
        for bga, game in list(best.values())[:limit]
    ]
