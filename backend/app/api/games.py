import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Self

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, StringConstraints, model_validator
from sqlalchemy import select

from app import achievements, catalog
from app.auth import CurrentUser
from app.bgg import BggClient, BggError
from app.db import SessionDep
from app.models import CUSTOM_GAME_IDS, Game, Ownership, Source, UserGame
from app.pieces import Achievement

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
    bgg_rating: float | None
    bgg_rank: int | None
    best_with: list[int]
    base_game_ids: list[int]  # for an expansion, the games it expands
    is_custom: bool  # added by someone here, not on BGG

    @classmethod
    def from_game(cls, game: Game) -> Self:
        return cls.model_validate(
            {
                **_columns(game),
                "best_with": _numeric_counts(game, best_only=True),
                "is_custom": game.is_custom,
            }
        )


class GameDetail(GameSummary):
    image_url: str | None
    playing_time: int | None
    min_age: int | None
    bgg_users_rated: int | None
    categories: list[str]
    mechanics: list[str]
    recommended_with: list[int]
    player_count_votes: list[PlayerCountVote]
    bgg_url: str | None  # null for a game that isn't on BGG
    created_by_id: uuid.UUID | None  # who added a custom game, and can edit it

    @classmethod
    def from_game(cls, game: Game) -> Self:
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
                "is_custom": game.is_custom,
                "bgg_url": None
                if game.is_custom
                else f"https://boardgamegeek.com/boardgame/{game.id}",
            }
        )


GameName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Year = Annotated[int, Field(ge=1, le=2200)]
Players = Annotated[int, Field(ge=1, le=100)]
Minutes = Annotated[int, Field(ge=1, le=24 * 60 * 7)]
Age = Annotated[int, Field(ge=1, le=99)]


class CustomGameIn(BaseModel):
    """A game that isn't on BGG: one someone designed, or that BGG just doesn't list."""

    name: GameName
    year_published: Year | None = None
    min_players: Players | None = None
    max_players: Players | None = None
    min_playtime: Minutes | None = None
    max_playtime: Minutes | None = None
    min_age: Age | None = None

    @model_validator(mode="after")
    def ranges_in_order(self) -> Self:
        if self.min_players and self.max_players and self.min_players > self.max_players:
            raise ValueError("The most players can't be fewer than the fewest")
        if self.min_playtime and self.max_playtime and self.min_playtime > self.max_playtime:
            raise ValueError("The longest game can't be shorter than the shortest")
        return self

    def apply_to(self, game: Game) -> None:
        for field, value in self.model_dump().items():
            setattr(game, field, value)
        # BGG's single "playing time" is its longest; recommendations read it.
        game.playing_time = self.max_playtime or self.min_playtime


NOT_YOURS = HTTPException(
    status.HTTP_403_FORBIDDEN, "Only the person who added this game can change it."
)


@router.post("", status_code=status.HTTP_201_CREATED)
async def add_custom_game(body: CustomGameIn, user: CurrentUser, session: SessionDep) -> GameDetail:
    """Add a game that isn't on BGG. It goes in your list as owned."""
    game_id = await session.scalar(select(CUSTOM_GAME_IDS.next_value()))
    assert game_id is not None
    game = Game(id=game_id, created_by_id=user.id, details_fetched_at=datetime.now(UTC))
    body.apply_to(game)
    session.add(game)
    await session.flush()
    session.add(
        UserGame(
            user_id=user.id,
            game_id=game.id,
            ownership=Ownership.OWNED,
            source=Source.MANUAL,
            player_counts=[],
            moods=[],
        )
    )
    await achievements.earn(session, Achievement.ADD_GAME, user.id)
    await session.commit()
    await session.refresh(game)
    return GameDetail.from_game(game)


@router.put("/{game_id}")
async def update_custom_game(
    game_id: int, body: CustomGameIn, user: CurrentUser, session: SessionDep
) -> GameDetail:
    """Change a game you added. BGG's games come from BGG and can't be changed here."""
    game = await session.get(Game, game_id)
    if game is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Game not found")
    if not game.is_custom or game.created_by_id != user.id:
        raise NOT_YOURS
    body.apply_to(game)
    await session.commit()
    await session.refresh(game)
    return GameDetail.from_game(game)


@router.get("/search")
async def search_games(
    user: CurrentUser,
    session: SessionDep,
    bgg: BggDep,
    q: Annotated[str, Query(min_length=2, max_length=100)],
    include_expansions: bool = True,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[GameSummary]:
    games = await catalog.search_games(
        session, bgg, q, limit=limit, include_expansions=include_expansions, user_id=user.id
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
