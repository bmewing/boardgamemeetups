from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel

from app import catalog
from app.auth import CurrentUser
from app.bgg import BggClient, BggError
from app.db import SessionDep
from app.models import Game

router = APIRouter(prefix="/games", tags=["games"])


def get_bgg_client(request: Request) -> BggClient:
    client: BggClient = request.app.state.bgg
    return client


BggDep = Annotated[BggClient, Depends(get_bgg_client)]


class PlayerCountVote(BaseModel):
    players: str
    best: int
    recommended: int
    not_recommended: int


def _columns(game: Game) -> dict[str, Any]:
    return {column.key: getattr(game, column.key) for column in Game.__table__.columns}


def _numeric_counts(game: Game, *, best_only: bool) -> list[int]:
    """Player counts the BGG community rates best (or at least recommended) for this game."""
    counts = []
    for players, votes in (game.player_count_votes or {}).items():
        if not players.isdigit():
            continue  # e.g. "5+"
        best, rec, nope = votes["best"], votes["recommended"], votes["not_recommended"]
        if best + rec + nope == 0:
            continue
        if (best_only and best > rec and best > nope) or (not best_only and best + rec > nope):
            counts.append(int(players))
    return sorted(counts)


class GameSummary(BaseModel):
    id: int
    name: str
    year_published: int | None
    is_expansion: bool
    thumbnail_url: str | None
    min_players: int | None
    max_players: int | None
    min_playtime: int | None
    max_playtime: int | None
    weight: float | None
    bgg_rank: int | None
    best_with: list[int]

    @classmethod
    def from_game(cls, game: Game) -> GameSummary:
        return cls.model_validate(
            {**_columns(game), "best_with": _numeric_counts(game, best_only=True)}
        )


class GameDetail(GameSummary):
    image_url: str | None
    playing_time: int | None
    min_age: int | None
    bgg_rating: float | None
    bgg_users_rated: int | None
    categories: list[str]
    mechanics: list[str]
    base_game_ids: list[int]
    recommended_with: list[int]
    player_count_votes: list[PlayerCountVote]
    bgg_url: str

    @classmethod
    def from_game(cls, game: Game) -> GameDetail:
        votes = [
            PlayerCountVote(players=players, **counts)
            for players, counts in (game.player_count_votes or {}).items()
        ]
        return cls.model_validate(
            {
                **_columns(game),
                "best_with": _numeric_counts(game, best_only=True),
                "recommended_with": _numeric_counts(game, best_only=False),
                "player_count_votes": votes,
                "bgg_url": f"https://boardgamegeek.com/boardgame/{game.id}",
            }
        )


@router.get("/search")
async def search_games(
    _user: CurrentUser,
    session: SessionDep,
    bgg: BggDep,
    q: Annotated[str, Query(min_length=2, max_length=100)],
    include_expansions: bool = True,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[GameSummary]:
    games = await catalog.search_games(
        session, bgg, q, limit=limit, include_expansions=include_expansions
    )
    return [GameSummary.from_game(game) for game in games]


@router.get("/{game_id}")
async def read_game(
    game_id: int, _user: CurrentUser, session: SessionDep, bgg: BggDep
) -> GameDetail:
    try:
        game = await catalog.get_game(session, bgg, game_id)
    except BggError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "BoardGameGeek is unavailable right now"
        ) from exc
    if game is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Game not found")
    return GameDetail.from_game(game)
