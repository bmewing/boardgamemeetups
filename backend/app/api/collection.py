"""The signed-in user's games: listing, editing, and importing from BGG with a preview."""

from datetime import datetime
from typing import Annotated, Any, Literal, Self

from fastapi import APIRouter, HTTPException, Path, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select

from app import catalog, collection
from app.api.games import BggDep, GameSummary
from app.auth import CurrentUser
from app.bgg import BggError, BggStillPreparing, BggUnknownUser
from app.collection import (
    ChangeKind,
    ChangeRequest,
    FieldName,
    Notes,
    Plays,
    Rating,
    TeachMinutes,
    WeightVote,
    WishlistPriority,
)
from app.db import SessionDep
from app.models import (
    Game,
    Mood,
    Ownership,
    PlayerCountVote,
    PlaytimeFeel,
    Source,
    UserGame,
)

router = APIRouter(tags=["collection"])

GameId = Annotated[int, Path(ge=1)]


class PlayerCountRead(BaseModel):
    players: int
    vote: PlayerCountVote


class UserGameRead(BaseModel):
    game: GameSummary
    ownership: Ownership | None
    wishlist_priority: int | None
    want_to_play: bool
    rating: float | None
    weight_vote: int | None
    playtime_feel: PlaytimeFeel | None
    can_teach: bool
    teach_minutes: int | None
    plays: int
    will_bring: bool
    notes: str | None
    player_counts: list[PlayerCountRead]
    moods: list[str]
    source: Source
    updated_at: datetime

    @classmethod
    def build(cls, row: UserGame, game: Game) -> Self:
        return cls(
            game=GameSummary.from_game(game),
            **{name: getattr(row, name) for name in collection.FIELD_TYPES},
            player_counts=[
                PlayerCountRead(players=pc.players, vote=pc.vote)
                for pc in sorted(row.player_counts, key=lambda pc: pc.players)
            ],
            moods=sorted(mood.mood_id for mood in row.moods),
            source=row.source,
            updated_at=row.updated_at,
        )


class UserGameUpdate(BaseModel):
    """Fields to change; anything left out keeps its value. Null clears a field."""

    ownership: Ownership | None = None
    wishlist_priority: WishlistPriority | None = None
    want_to_play: bool | None = None
    rating: Rating | None = None
    weight_vote: WeightVote | None = None
    playtime_feel: PlaytimeFeel | None = None
    can_teach: bool | None = None
    teach_minutes: TeachMinutes | None = None
    plays: Plays | None = None
    will_bring: bool | None = None
    notes: Notes | None = None

    @model_validator(mode="after")
    def booleans_and_counts_cannot_be_null(self) -> Self:
        for name in ("want_to_play", "can_teach", "plays", "will_bring"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} can't be null")
        return self


class MoodRead(BaseModel):
    id: str
    name: str
    description: str
    taggable: bool


class GameBrief(BaseModel):
    id: int
    name: str
    year_published: int | None
    thumbnail_url: str | None
    is_expansion: bool


class FieldChangeRead(BaseModel):
    field: FieldName
    current: Any
    incoming: Any
    kind: ChangeKind


class GameDiffRead(BaseModel):
    game: GameBrief
    is_new: bool
    on_source: bool
    changes: list[FieldChangeRead]


class ImportCounts(BaseModel):
    games_on_source: int
    new_games: int
    fills: int
    overwrites: int
    not_on_source: int


class ImportPreview(BaseModel):
    source: Source
    bgg_username: str | None
    games: list[GameDiffRead]
    counts: ImportCounts


class ChangeIn(BaseModel):
    game_id: int
    field: FieldName
    expected: Any
    value: Any

    @model_validator(mode="after")
    def value_fits_field(self) -> Self:
        self.value = collection.validate_field(self.field, self.value)
        return self


class ImportApply(BaseModel):
    source: Literal[Source.BGG, Source.FILE]
    changes: Annotated[list[ChangeIn], Field(max_length=50_000)]


class SkippedRead(BaseModel):
    game_id: int
    field: str | None
    reason: str


class ImportResult(BaseModel):
    applied: int
    skipped: list[SkippedRead]


@router.get("/moods")
async def list_moods(_user: CurrentUser, session: SessionDep) -> list[MoodRead]:
    moods = await session.scalars(select(Mood).order_by(Mood.sort_order))
    return [
        MoodRead(id=m.id, name=m.name, description=m.description, taggable=m.taggable)
        for m in moods
    ]


@router.get("/me/games")
async def list_my_games(user: CurrentUser, session: SessionDep) -> list[UserGameRead]:
    rows = await session.execute(
        select(UserGame, Game)
        .join(Game, Game.id == UserGame.game_id)
        .where(UserGame.user_id == user.id)
        .order_by(Game.name)
    )
    return [UserGameRead.build(row, game) for row, game in rows]


@router.put("/me/games/{game_id}")
async def update_my_game(
    game_id: GameId, changes: UserGameUpdate, user: CurrentUser, session: SessionDep
) -> UserGameRead:
    """Add a game to your list or change what you've recorded about it."""
    game = await session.get(Game, game_id)
    if game is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Game not found")
    row = await session.get(UserGame, (user.id, game_id))
    updates = changes.model_dump(exclude_unset=True)
    merged = {name: collection.current_value(row, name) for name in collection.FIELD_TYPES}
    merged |= updates
    if merged["can_teach"] and merged["teach_minutes"] is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Say how long the teach takes to mark it"
        )
    if row is None:
        row = UserGame(user_id=user.id, game_id=game_id, source=Source.MANUAL, **merged)
        session.add(row)
    else:
        for name, value in updates.items():
            setattr(row, name, value)
    await session.commit()
    await session.refresh(row)
    return UserGameRead.build(row, game)


@router.delete("/me/games/{game_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_my_game(game_id: GameId, user: CurrentUser, session: SessionDep) -> None:
    """Forget everything you've recorded about a game."""
    row = await session.get(UserGame, (user.id, game_id))
    if row is not None:
        await session.delete(row)
        await session.commit()


@router.post("/me/games/bgg-pull")
async def preview_bgg_pull(user: CurrentUser, session: SessionDep, bgg: BggDep) -> ImportPreview:
    """Fetch your BGG collection and list what pulling it would change. Writes nothing of yours."""
    if not user.bgg_username:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Add your BGG username to your profile")
    try:
        entries = await bgg.collection(user.bgg_username)
    except BggUnknownUser as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"BGG has no user named {user.bgg_username}"
        ) from exc
    except BggStillPreparing as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "BGG is still preparing your collection; try again in a minute",
            headers={"Retry-After": "60"},
        ) from exc
    except BggError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "BoardGameGeek is unavailable right now"
        ) from exc

    # The catalog is shared, so recording these games isn't a change to the user's data.
    await catalog.upsert_collection_games(session, entries)
    await session.commit()

    rows = await collection.user_rows(session, user.id)
    diffs = collection.diff_import(
        rows,
        {entry.id: collection.bgg_values(entry) for entry in entries},
        mirrored=collection.BGG_STATUS_FIELDS,
    )
    games = {
        game.id: game
        for game in await session.scalars(
            select(Game).where(Game.id.in_([d.game_id for d in diffs]))
        )
    }
    kinds = [change.kind for diff in diffs for change in diff.changes]
    return ImportPreview(
        source=Source.BGG,
        bgg_username=user.bgg_username,
        games=[
            GameDiffRead(
                game=GameBrief.model_validate(games[d.game_id], from_attributes=True),
                is_new=d.is_new,
                on_source=d.on_source,
                changes=[
                    FieldChangeRead.model_validate(change, from_attributes=True)
                    for change in d.changes
                ],
            )
            for d in sorted(diffs, key=lambda d: games[d.game_id].name.lower())
        ],
        counts=ImportCounts(
            games_on_source=len(entries),
            new_games=sum(d.is_new for d in diffs),
            fills=kinds.count(ChangeKind.FILL),
            overwrites=kinds.count(ChangeKind.OVERWRITE),
            not_on_source=sum(not d.on_source for d in diffs),
        ),
    )


@router.post("/me/games/import")
async def apply_import(body: ImportApply, user: CurrentUser, session: SessionDep) -> ImportResult:
    """Apply the changes you kept from a preview."""
    result = await collection.apply_changes(
        session,
        user,
        [ChangeRequest(c.game_id, c.field, c.expected, c.value) for c in body.changes],
        source=Source(body.source),
    )
    return ImportResult(
        applied=result.applied,
        skipped=[
            SkippedRead(game_id=s.game_id, field=s.field, reason=s.reason) for s in result.skipped
        ],
    )
