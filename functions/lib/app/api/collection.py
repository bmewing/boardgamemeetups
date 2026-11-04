"""The signed-in user's games: listing, editing, and importing from BGG with a preview."""

from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal, Self

from fastapi import APIRouter, HTTPException, Path, Query, Request, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import any_, delete, func, literal, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app import base_games, catalog, collection
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
from app.file_import import (
    MAX_ROWS,
    FileError,
    FileKind,
    ImportColumn,
    WholeFile,
    bgg_export_entries,
    bgg_export_rows,
    inspect_table,
    parse_rows,
    read_table,
)
from app.matching import MatchStatus, RowMatch, match_rows
from app.models import (
    Game,
    Mood,
    Ownership,
    PlayerCountVote,
    PlaytimeFeel,
    RemovedGame,
    Source,
    User,
    UserGame,
    UserGameMood,
    UserGamePlayerCount,
)

router = APIRouter(tags=["collection"])

GameId = Annotated[int, Path(ge=1)]
MoodId = Annotated[str, Field(min_length=1, max_length=32)]
# Well past any real game; only there to bound a request.
MAX_PLAYERS = 100
MAX_MOODS = 50
# Sent as whole lists and stored in their own tables, not as UserGame columns.
LIST_FIELDS = ("player_counts", "moods")


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
    can_teach: bool | None  # null: not answered (owners count as teachers)
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


class PlayerCountIn(BaseModel):
    players: Annotated[int, Field(ge=1, le=MAX_PLAYERS)]
    vote: PlayerCountVote


class UserGameUpdate(BaseModel):
    """Fields to change; anything left out keeps its value. Null clears a field.

    `player_counts` and `moods` replace the whole list when sent: a count or mood left out
    is blank, and an empty list clears them all.
    """

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
    player_counts: Annotated[list[PlayerCountIn], Field(max_length=MAX_PLAYERS)] | None = None
    moods: Annotated[list[MoodId], Field(max_length=MAX_MOODS)] | None = None

    @model_validator(mode="after")
    def booleans_counts_and_lists_cannot_be_null(self) -> Self:
        for name in ("want_to_play", "can_teach", "plays", "will_bring", *LIST_FIELDS):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} can't be null")
        return self

    @model_validator(mode="after")
    def one_vote_per_player_count(self) -> Self:
        counts = [pc.players for pc in self.player_counts or []]
        if len(counts) != len(set(counts)):
            raise ValueError("Each player count can only have one vote")
        return self


class DetailsProgress(BaseModel):
    filled: int
    remaining: int


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


class BaseGameSuggestion(BaseModel):
    game: GameSummary
    expansions: list[GameBrief]  # your owned expansions for it
    ownership: Ownership | None  # e.g. previously owned, if it's in your list
    on_wishlist: bool


class BaseGameChoice(BaseModel):
    """An expansion of yours that fits several base games, none of which you own."""

    expansion: GameBrief
    options: list[GameSummary]  # the best known first
    option_count: int


class MissingBaseGamesRead(BaseModel):
    suggestions: list[BaseGameSuggestion]
    choices: list[BaseGameChoice]
    unchecked: int  # owned expansions whose base games aren't known yet: ask again
    hidden: int  # left out because you removed those games here


class FieldChangeRead(BaseModel):
    field: FieldName
    current: Any
    incoming: Any
    kind: ChangeKind


class GameDiffRead(BaseModel):
    game: GameBrief
    is_new: bool
    on_source: bool
    # You removed this game here before; it's offered unticked.
    removed_before: bool
    changes: list[FieldChangeRead]


class ImportCounts(BaseModel):
    games_on_source: int
    new_games: int  # not counting games you removed before
    fills: int  # not counting games you removed before
    overwrites: int
    not_on_source: int
    removed_before: int


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


async def _check_taggable(session: AsyncSession, mood_ids: list[str]) -> None:
    taggable = set(
        await session.scalars(select(Mood.id).where(Mood.id.in_(mood_ids), Mood.taggable.is_(True)))
    )
    if wrong := sorted(set(mood_ids) - taggable):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"These moods can't be put on a game: {', '.join(wrong)}",
        )


def _replace_player_counts(
    current: list[UserGamePlayerCount], wanted: list[PlayerCountIn]
) -> list[UserGamePlayerCount]:
    """The new list, reusing rows for counts kept so their keys aren't deleted and re-added."""
    by_players = {pc.players: pc for pc in current}
    result = []
    for pc in wanted:
        row = by_players.get(pc.players) or UserGamePlayerCount(players=pc.players)
        row.vote = pc.vote
        result.append(row)
    return result


def _replace_moods(current: list[UserGameMood], wanted: list[str]) -> list[UserGameMood]:
    by_id = {m.mood_id: m for m in current}
    # dict.fromkeys drops repeats and keeps the order.
    return [by_id.get(i) or UserGameMood(mood_id=i) for i in dict.fromkeys(wanted)]


@router.put("/me/games/{game_id}")
async def update_my_game(
    game_id: GameId, changes: UserGameUpdate, user: CurrentUser, session: SessionDep
) -> UserGameRead:
    """Add a game to your list or change what you've recorded about it."""
    game = await session.get(Game, game_id)
    if game is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Game not found")
    row = await session.get(UserGame, (user.id, game_id))
    updates = changes.model_dump(exclude_unset=True, exclude=set(LIST_FIELDS))
    merged = {name: collection.current_value(row, name) for name in collection.FIELD_TYPES}
    merged |= updates
    if merged["can_teach"] and merged["teach_minutes"] is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Say how long the teach takes to mark it"
        )
    if changes.moods:
        await _check_taggable(session, changes.moods)
    if row is None:
        # Empty lists set up front, or reading them after the flush below would lazy-load.
        row = UserGame(
            user_id=user.id,
            game_id=game_id,
            source=Source.MANUAL,
            player_counts=[],
            moods=[],
            **merged,
        )
        session.add(row)
        await collection.forget_removals(session, user.id, [game_id])
    else:
        for name, value in updates.items():
            setattr(row, name, value)
    if changes.player_counts is not None:
        row.player_counts = _replace_player_counts(row.player_counts, changes.player_counts)
    if changes.moods is not None:
        row.moods = _replace_moods(row.moods, changes.moods)
    if not updates and changes.model_fields_set & set(LIST_FIELDS):
        # Only the lists changed, so the row's own onupdate wouldn't fire.
        row.updated_at = func.now()
    await session.commit()
    await session.refresh(row)
    return UserGameRead.build(row, game)


@router.delete("/me/games/{game_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_my_game(
    game_id: GameId,
    user: CurrentUser,
    session: SessionDep,
    expansions: Annotated[list[int], Query(max_length=200)] = [],  # noqa: B006
) -> None:
    """Forget everything you've recorded about a game, and optionally some of its expansions.

    Only games that are expansions of this one are removed from `expansions`; other ids are
    ignored, so a mistaken id can't take an unrelated game with it. Removed games are
    remembered, so a later import offers them unticked instead of adding them back. A game
    that isn't in the list can be removed too: it's then left out of suggestions.
    """
    removed = await session.scalars(
        delete(UserGame)
        .where(
            UserGame.user_id == user.id,
            (UserGame.game_id == game_id)
            | UserGame.game_id.in_(
                select(Game.id).where(
                    Game.id.in_(expansions),
                    Game.is_expansion.is_(True),
                    literal(game_id) == any_(Game.base_game_ids),
                )
            ),
        )
        .returning(UserGame.game_id)
    )
    ids = set(removed)
    # Also for a game that isn't in the list ("not interested" in a suggestion), so it isn't
    # suggested or imported again.
    if await session.get(Game, game_id) is not None:
        ids.add(game_id)
    if ids:
        await session.execute(
            insert(RemovedGame)
            .values([{"user_id": user.id, "game_id": i} for i in ids])
            .on_conflict_do_nothing()
        )
    await session.commit()


# Two BGG requests (20 games each), ~5s apart: well inside the function's time limit.
DETAILS_PER_CALL = 40


@router.post("/me/games/missing-base-games")
async def find_missing_base_games(
    user: CurrentUser, session: SessionDep, bgg: BggDep
) -> MissingBaseGamesRead:
    """Base games of expansions you own, where you don't own the base game.

    Looks up base games on BGG for a batch of expansions that haven't been checked yet;
    while `unchecked` is above zero, calling again checks more.
    """
    found = await base_games.find_missing_base_games(session, bgg, user.id)
    return MissingBaseGamesRead(
        suggestions=[
            BaseGameSuggestion(
                game=GameSummary.from_game(s.game),
                expansions=[_brief(e) for e in s.expansions],
                ownership=s.row.ownership if s.row else None,
                on_wishlist=bool(s.row and s.row.wishlist_priority is not None),
            )
            for s in found.suggestions
        ],
        choices=[
            BaseGameChoice(
                expansion=_brief(c.expansion),
                options=[GameSummary.from_game(g) for g in c.options],
                option_count=c.option_count,
            )
            for c in found.choices
        ],
        unchecked=found.unchecked,
        hidden=found.hidden,
    )


@router.post("/me/games/fill-details")
async def fill_my_game_details(
    user: CurrentUser, session: SessionDep, bgg: BggDep
) -> DetailsProgress:
    """Fetch BGG details (weight, best counts…) for some of your games that lack them.

    A BGG collection only gives a game's basics, so the collection page calls this until
    nothing remains. If BGG is down, nothing is filled and the caller should stop.
    """
    missing = (
        select(Game)
        .join(UserGame, UserGame.game_id == Game.id)
        .where(UserGame.user_id == user.id, Game.details_fetched_at.is_(None))
    )
    games = list(await session.scalars(missing.order_by(Game.id).limit(DETAILS_PER_CALL)))
    await catalog.refresh_details(session, bgg, games, only_missing=True)
    filled = sum(game.details_fetched_at is not None for game in games)
    remaining = await session.scalar(select(func.count()).select_from(missing.subquery()))
    return DetailsProgress(filled=filled, remaining=remaining or 0)


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

    return await _build_preview(
        session,
        user,
        {entry.id: collection.bgg_values(entry) for entry in entries},
        mirrored=collection.BGG_STATUS_FIELDS,
        source=Source.BGG,
    )


async def _build_preview(
    session: AsyncSession,
    user: User,
    incoming: Mapping[int, Mapping[str, Any]],
    *,
    mirrored: frozenset[str],
    source: Source,
) -> ImportPreview:
    """List what importing `incoming` (game id -> values) would change for this user."""
    rows = await collection.user_rows(session, user.id)
    diffs = collection.diff_import(rows, incoming, mirrored=mirrored)
    games = {
        game.id: game
        for game in await session.scalars(
            select(Game).where(Game.id.in_([d.game_id for d in diffs]))
        )
    }
    removed = set(
        await session.scalars(select(RemovedGame.game_id).where(RemovedGame.user_id == user.id))
    )
    was_removed = {d.game_id for d in diffs if d.is_new and d.game_id in removed}
    kinds = [
        change.kind for diff in diffs if diff.game_id not in was_removed for change in diff.changes
    ]
    return ImportPreview(
        source=source,
        bgg_username=user.bgg_username if source is Source.BGG else None,
        games=[
            GameDiffRead(
                game=GameBrief.model_validate(games[d.game_id], from_attributes=True),
                is_new=d.is_new,
                on_source=d.on_source,
                removed_before=d.game_id in was_removed,
                changes=[
                    FieldChangeRead.model_validate(change, from_attributes=True)
                    for change in d.changes
                ],
            )
            for d in sorted(diffs, key=lambda d: games[d.game_id].name.lower())
        ],
        counts=ImportCounts(
            games_on_source=len(incoming),
            new_games=sum(d.is_new and d.game_id not in was_removed for d in diffs),
            fills=kinds.count(ChangeKind.FILL),
            overwrites=kinds.count(ChangeKind.OVERWRITE),
            not_on_source=sum(not d.on_source for d in diffs),
            removed_before=len(was_removed),
        ),
    )


# Uploads arrive as the request body; DigitalOcean caps function requests at about 1 MB.
MAX_UPLOAD_BYTES = 1_000_000


class CandidateRead(BaseModel):
    game: GameBrief
    score: float


class FileRowRead(BaseModel):
    line: int
    name: str | None
    year: int | None
    bgg_id: int | None
    values: dict[str, Any]
    problems: list[str]
    status: MatchStatus
    confidence: float
    match: GameBrief | None
    candidates: list[CandidateRead]


class FileColumnsRead(BaseModel):
    kind: FileKind
    has_header: bool
    headers: list[str]
    samples: list[list[str]]
    # A guess at each column's meaning (null: ignore it). Empty for a BGG export.
    suggested: list[ImportColumn | None]
    row_count: int


class FileImportRead(BaseModel):
    kind: FileKind
    filename: str
    rows: list[FileRowRead]


class FileGameIn(BaseModel):
    game_id: int
    values: UserGameUpdate


class FilePreviewIn(BaseModel):
    # A BGG export is a whole collection, like a pull, so ownership and wishlist follow it.
    whole_bgg_collection: bool = False
    games: Annotated[list[FileGameIn], Field(max_length=MAX_ROWS)]


def _brief(game: Game) -> GameBrief:
    return GameBrief.model_validate(game, from_attributes=True)


def _row_read(match: RowMatch) -> FileRowRead:
    row = match.row
    return FileRowRead(
        line=row.line,
        name=row.name,
        year=row.year,
        bgg_id=row.bgg_id,
        values={k: v.value if isinstance(v, StrEnum) else v for k, v in row.values.items()},
        problems=row.problems,
        status=match.status,
        confidence=match.confidence,
        match=_brief(match.game) if match.game else None,
        candidates=[CandidateRead(game=_brief(c.game), score=c.score) for c in match.candidates],
    )


FILE_BODY = {
    "requestBody": {
        "required": True,
        "content": {"application/octet-stream": {"schema": {"type": "string", "format": "binary"}}},
    }
}
Filename = Annotated[str, Query(min_length=1, max_length=255)]


async def _read_upload(request: Request, filename: str) -> list[list[str]]:
    data = await request.body()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Files can be up to 1 MB")
    try:
        return read_table(data, filename)
    except FileError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc


@router.post("/me/games/file-import/columns", openapi_extra=FILE_BODY)
async def read_import_columns(
    request: Request, filename: Filename, _user: CurrentUser
) -> FileColumnsRead:
    """Show an uploaded file's columns, with samples and a guess at what each holds.

    Send the file itself (CSV, Excel or text) as the request body. Nothing is stored.
    """
    layout = inspect_table(await _read_upload(request, filename))
    return FileColumnsRead(
        kind=layout.kind,
        has_header=layout.has_header,
        headers=layout.headers,
        samples=layout.samples,
        suggested=layout.suggested,
        row_count=layout.row_count,
    )


@router.post("/me/games/file-import", openapi_extra=FILE_BODY)
async def read_import_file(
    request: Request,
    filename: Filename,
    user: CurrentUser,
    session: SessionDep,
    bgg: BggDep,
    # One per file column, in order: what it holds, or "" to ignore it. Not needed for a
    # BGG export, whose columns are known.
    columns: Annotated[list[str], Query(max_length=200)] = [],  # noqa: B006
    # Where the games go when no column holds ownership or wishlist.
    whole_file: WholeFile | None = None,
) -> FileImportRead:
    """Read an uploaded file with the chosen columns and match its rows to games.

    Send the same file as the request body. Nothing of yours is written; games new to the
    catalog are recorded there.
    """
    table = await _read_upload(request, filename)
    layout = inspect_table(table)
    if layout.kind is FileKind.BGG_EXPORT:
        entries = bgg_export_entries(table)
        await catalog.upsert_collection_games(session, entries)
        await session.commit()
        rows = bgg_export_rows(entries)
    else:
        try:
            chosen = [ImportColumn(c) if c else None for c in columns]
            rows = parse_rows(table, layout, chosen, whole_file)
        except ValueError as exc:  # FileError, or an unknown column name
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    matches = await match_rows(session, bgg, rows)
    return FileImportRead(
        kind=layout.kind,
        filename=filename,
        rows=[_row_read(m) for m in matches],
    )


@router.post("/me/games/file-import/preview")
async def preview_file_import(
    body: FilePreviewIn, user: CurrentUser, session: SessionDep
) -> ImportPreview:
    """List what importing the matched rows of a file would change. Writes nothing.

    A game listed twice keeps the values of its last row. A blank cell never clears an
    answer you gave, unless the file is a whole BGG collection.
    """
    incoming: dict[int, dict[str, Any]] = {}
    for game in body.games:
        incoming.setdefault(game.game_id, {}).update(game.values.model_dump(exclude_unset=True))
    known = set(await session.scalars(select(Game.id).where(Game.id.in_(incoming))))
    return await _build_preview(
        session,
        user,
        {game_id: values for game_id, values in incoming.items() if game_id in known},
        mirrored=collection.BGG_STATUS_FIELDS if body.whole_bgg_collection else frozenset(),
        source=Source.FILE,
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
