"""A user's game data, and bringing in data from BGG or a file without surprises.

Every import runs in two steps. `diff_import` compares what the source says with what the
user already has and lists each field that would change, marked as filling a blank or
overwriting an answer. The user picks which changes to keep, and `apply_changes` writes
those, but only where the value is still what the preview showed.
"""

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import Field, StringConstraints, TypeAdapter
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bgg import CollectionEntry
from app.models import Game, Ownership, PlaytimeFeel, RemovedGame, Source, User, UserGame

# The UserGame columns a user (or an import) can set, with what each must hold.
WishlistPriority = Annotated[int, Field(ge=1, le=5)]
Rating = Annotated[float, Field(ge=1, le=10)]
WeightVote = Annotated[int, Field(ge=1, le=5)]
TeachMinutes = Annotated[int, Field(gt=0, le=24 * 60)]
Plays = Annotated[int, Field(ge=0)]
Notes = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]

FIELD_TYPES: dict[str, Any] = {
    "ownership": Ownership | None,
    "wishlist_priority": WishlistPriority | None,
    "want_to_play": bool,
    "rating": Rating | None,
    "weight_vote": WeightVote | None,
    "playtime_feel": PlaytimeFeel | None,
    "can_teach": bool | None,
    "teach_minutes": TeachMinutes | None,
    "plays": Plays,
    "will_bring": bool,
    "notes": Notes | None,
}
FieldName = Literal[
    "ownership",
    "wishlist_priority",
    "want_to_play",
    "rating",
    "weight_vote",
    "playtime_feel",
    "can_teach",
    "teach_minutes",
    "plays",
    "will_bring",
    "notes",
]
FIELD_ADAPTERS = {name: TypeAdapter(kind) for name, kind in FIELD_TYPES.items()}

# What a field holds when nobody has answered it. Matching the default counts as blank.
DEFAULTS: dict[str, Any] = {
    **dict.fromkeys(FIELD_TYPES),
    "want_to_play": False,
    "plays": 0,
    "will_bring": True,
}

# BGG is the record of what you own and want, so these follow it, blanks included. Opinions
# (rating, notes) only ever take values BGG actually has, and play counts only go up.
BGG_STATUS_FIELDS = frozenset({"ownership", "wishlist_priority", "want_to_play"})
COUNT_FIELDS = frozenset({"plays"})


def validate_field(name: str, value: Any) -> Any:
    return FIELD_ADAPTERS[name].validate_python(value)


def current_value(row: UserGame | None, name: str) -> Any:
    if row is None:
        return DEFAULTS[name]
    value = getattr(row, name)
    # Unflushed rows haven't had their column defaults applied yet.
    return DEFAULTS[name] if value is None else value


def _plain(value: Any) -> Any:
    return value.value if isinstance(value, StrEnum) else value


class ChangeKind(StrEnum):
    FILL = "fill"  # the user had no answer
    OVERWRITE = "overwrite"  # replaces an answer the user has
    NOT_ON_SOURCE = "not_on_source"  # e.g. owned here, but not in the BGG collection


@dataclass
class FieldChange:
    field: str
    current: Any
    incoming: Any
    kind: ChangeKind


@dataclass
class GameDiff:
    game_id: int
    is_new: bool  # the user has no row for this game yet
    on_source: bool
    changes: list[FieldChange] = field(default_factory=list)


def diff_import(
    rows: Mapping[int, UserGame],
    incoming: Mapping[int, Mapping[str, Any]],
    *,
    mirrored: frozenset[str] = frozenset(),
) -> list[GameDiff]:
    """List what importing `incoming` (game id -> field values) would change.

    A blank incoming value never clears an answer, except in `mirrored` fields, where the
    source is the record. For those, games the user has but the source lacks are proposed
    to be cleared too, marked NOT_ON_SOURCE.
    """
    diffs: list[GameDiff] = []
    for game_id, values in incoming.items():
        row = rows.get(game_id)
        diff = GameDiff(game_id, is_new=row is None, on_source=True)
        for name, value in values.items():
            current = current_value(row, name)
            if value == current:
                continue
            if value == DEFAULTS[name] and name not in mirrored:
                continue
            if name in COUNT_FIELDS and value < current:
                continue
            kind = ChangeKind.FILL if current == DEFAULTS[name] else ChangeKind.OVERWRITE
            diff.changes.append(FieldChange(name, _plain(current), _plain(value), kind))
        if diff.changes:
            diffs.append(diff)

    for game_id, row in rows.items():
        if game_id in incoming:
            continue
        changes = [
            FieldChange(name, _plain(current), DEFAULTS[name], ChangeKind.NOT_ON_SOURCE)
            for name in sorted(mirrored)
            if (current := current_value(row, name)) != DEFAULTS[name]
        ]
        if changes:
            diffs.append(GameDiff(game_id, is_new=False, on_source=False, changes=changes))
    return diffs


def bgg_values(entry: CollectionEntry) -> dict[str, Any]:
    """The user_games fields a BGG collection entry speaks for."""
    if entry.own:
        ownership: Ownership | None = Ownership.OWNED
    elif entry.preordered:
        ownership = Ownership.PREORDERED
    elif entry.prevowned:
        ownership = Ownership.PREVIOUSLY_OWNED
    else:
        ownership = None
    return {
        "ownership": ownership,
        "wishlist_priority": entry.wishlist_priority,
        "want_to_play": entry.want_to_play,
        "rating": entry.rating,
        "plays": entry.plays,
        "notes": entry.comment,
    }


async def forget_removals(
    session: AsyncSession, user_id: uuid.UUID, game_ids: Sequence[int]
) -> None:
    """The user added these games back, so imports may offer them ticked again."""
    if game_ids:
        await session.execute(
            delete(RemovedGame).where(
                RemovedGame.user_id == user_id, RemovedGame.game_id.in_(game_ids)
            )
        )


async def user_rows(session: AsyncSession, user_id: uuid.UUID) -> dict[int, UserGame]:
    rows = await session.scalars(select(UserGame).where(UserGame.user_id == user_id))
    return {row.game_id: row for row in rows}


@dataclass
class ChangeRequest:
    game_id: int
    field: str
    expected: Any  # the value the user saw in the preview
    value: Any


@dataclass
class Skipped:
    game_id: int
    field: str | None
    reason: str


@dataclass
class ApplyResult:
    applied: int = 0
    skipped: list[Skipped] = field(default_factory=list)


async def apply_changes(
    session: AsyncSession, user: User, changes: Sequence[ChangeRequest], *, source: Source
) -> ApplyResult:
    """Write the changes the user accepted, skipping any whose value moved since the preview."""
    result = ApplyResult()
    by_game: dict[int, list[ChangeRequest]] = {}
    for change in changes:
        by_game.setdefault(change.game_id, []).append(change)
    if not by_game:
        return result

    known = set(await session.scalars(select(Game.id).where(Game.id.in_(by_game))))
    rows = {
        row.game_id: row
        for row in await session.scalars(
            select(UserGame)
            .where(UserGame.user_id == user.id, UserGame.game_id.in_(by_game))
            .with_for_update()
        )
    }
    touched: list[int] = []
    for game_id, game_changes in by_game.items():
        if game_id not in known:
            result.skipped.append(Skipped(game_id, None, "unknown game"))
            continue
        row = rows.get(game_id)
        updates: dict[str, Any] = {}
        for change in game_changes:
            if _plain(current_value(row, change.field)) != _plain(change.expected):
                result.skipped.append(Skipped(game_id, change.field, "changed since preview"))
                continue
            updates[change.field] = change.value
        if not updates:
            continue
        merged = {name: current_value(row, name) for name in FIELD_TYPES} | updates
        if merged["can_teach"] and merged["teach_minutes"] is None:
            result.skipped.append(Skipped(game_id, "can_teach", "teach time is required"))
            continue
        if row is None:
            row = UserGame(user_id=user.id, game_id=game_id, source=source, **merged)
            session.add(row)
        else:
            for name, value in updates.items():
                setattr(row, name, value)
        result.applied += len(updates)
        touched.append(game_id)

    await forget_removals(session, user.id, touched)
    if source is Source.BGG:
        user.bgg_pulled_at = datetime.now(UTC)
    await session.commit()
    return result
