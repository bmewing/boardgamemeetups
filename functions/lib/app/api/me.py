import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, status
from pydantic import AfterValidator, BaseModel, StringConstraints
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import achievements
from app.auth import TIME_ZONES, CurrentUser
from app.db import SessionDep
from app.email import EmailKind
from app.groups import hand_over_groups
from app.models import CollectionVisibility, User
from app.pieces import Achievement, Piece, PieceColor

router = APIRouter(prefix="/me", tags=["me"])


def known_time_zone(value: str) -> str:
    if value not in TIME_ZONES:
        raise ValueError("Unknown time zone")
    return value


def blank_to_none(value: str | None) -> str | None:
    return value or None


def single_spaces(value: str) -> str:
    return " ".join(value.split())


# Display names double as usernames: unique, ignoring case, with single spaces.
DisplayName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=80),
    AfterValidator(single_spaces),
]
TimeZone = Annotated[str, AfterValidator(known_time_zone)]
# BGG's and BGA's usernames alike.
BggUsername = Annotated[
    str | None,
    StringConstraints(strip_whitespace=True, max_length=64),
    AfterValidator(blank_to_none),
]


class AchievementRead(BaseModel):
    achievement: Achievement
    earned_at: datetime | None  # null: not earned yet
    new: bool  # earned since they last looked
    progress: int | None  # counted ones only: how far along, up to the goal
    goal: int | None


class PieceRead(BaseModel):
    piece: Piece
    unlocked_by: Achievement | None  # null: everyone has it from the start
    unlocked: bool


class ColorRead(BaseModel):
    color: PieceColor
    unlocked_by: Achievement | None  # null: everyone has it from the start
    unlocked: bool


class UserRead(BaseModel):
    id: uuid.UUID
    email: str | None
    display_name: str
    avatar_url: str | None
    piece: Piece | None  # null: hasn't picked (shown as a meeple)
    piece_color: PieceColor | None
    time_zone: str
    discord_username: str | None  # the Discord account linked through the bot
    bgg_username: str | None
    bgg_pulled_at: datetime | None
    bga_username: str | None  # shown to the people at online dates
    bga_premium: bool
    collection_visibility: CollectionVisibility
    email_opt_outs: list[EmailKind]  # kinds of email turned off
    is_admin: bool  # can open the admin portal
    achievements: list[AchievementRead]  # every one, in the backend's order
    pieces: list[PieceRead]  # every piece, in the backend's order, and which they can pick
    colors: list[ColorRead]

    @classmethod
    async def of(cls, session: AsyncSession, user: User) -> "UserRead":
        standing = await achievements.achievements_of(session, user.id)
        earned = {e.achievement for e in standing if e.earned_at is not None}
        return cls(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            avatar_url=user.avatar_url,
            piece=user.piece,
            piece_color=user.piece_color,
            time_zone=user.time_zone,
            discord_username=user.discord_username,
            bgg_username=user.bgg_username,
            bgg_pulled_at=user.bgg_pulled_at,
            bga_username=user.bga_username,
            bga_premium=user.bga_premium,
            collection_visibility=user.collection_visibility,
            email_opt_outs=[EmailKind(kind) for kind in user.email_opt_outs],
            is_admin=user.is_admin,
            achievements=[
                AchievementRead(
                    achievement=e.achievement,
                    earned_at=e.earned_at,
                    new=e.new,
                    progress=e.progress,
                    goal=e.goal,
                )
                for e in standing
            ],
            pieces=[
                PieceRead(
                    piece=piece,
                    unlocked_by=(needs := achievements.PIECE_UNLOCKED_BY.get(piece)),
                    unlocked=needs is None or needs in earned,
                )
                for piece in Piece
            ],
            colors=[
                ColorRead(
                    color=color,
                    unlocked_by=(needs := achievements.COLOR_UNLOCKED_BY.get(color)),
                    unlocked=needs is None or needs in earned,
                )
                for color in PieceColor
            ],
        )


class UserUpdate(BaseModel):
    display_name: DisplayName | None = None
    time_zone: TimeZone | None = None
    bgg_username: BggUsername = None
    bga_username: BggUsername = None
    bga_premium: bool | None = None
    collection_visibility: CollectionVisibility | None = None
    email_opt_outs: list[EmailKind] | None = None
    piece: Piece | None = None
    piece_color: PieceColor | None = None


# Fields that may be cleared by sending null; the rest are required on the user.
CLEARABLE = {"bgg_username", "bga_username", "piece", "piece_color"}


@router.get("")
async def read_me(user: CurrentUser, session: SessionDep) -> UserRead:
    return await UserRead.of(session, user)


NAME_TAKEN = HTTPException(status.HTTP_409_CONFLICT, "That name is taken. Try another.")
PIECE_LOCKED = HTTPException(status.HTTP_403_FORBIDDEN, "You haven't unlocked that piece yet.")
COLOR_LOCKED = HTTPException(status.HTTP_403_FORBIDDEN, "You haven't unlocked that color yet.")


@router.patch("")
async def update_me(changes: UserUpdate, user: CurrentUser, session: SessionDep) -> UserRead:
    if changes.display_name and changes.display_name.lower() != user.display_name.lower():
        clash = await session.scalar(
            select(User.id).where(
                func.lower(User.display_name) == changes.display_name.lower(), User.id != user.id
            )
        )
        if clash is not None:
            raise NAME_TAKEN
    # A piece or color someone already has stays theirs, even one that has since been locked.
    if (
        changes.piece is not None
        and changes.piece != user.piece
        and not await achievements.has_earned(
            session, user.id, achievements.PIECE_UNLOCKED_BY.get(changes.piece)
        )
    ):
        raise PIECE_LOCKED
    if (
        changes.piece_color is not None
        and changes.piece_color != user.piece_color
        and not await achievements.has_earned(
            session, user.id, achievements.COLOR_UNLOCKED_BY.get(changes.piece_color)
        )
    ):
        raise COLOR_LOCKED
    for field, value in changes.model_dump(exclude_unset=True).items():
        if field == "email_opt_outs" and value is not None:
            user.email_opt_outs = sorted(set(value))
        elif value is not None or field in CLEARABLE:
            setattr(user, field, value)
    try:
        await session.commit()
    except IntegrityError as exc:  # taken in the moment since we looked
        await session.rollback()
        raise NAME_TAKEN from exc
    await session.refresh(user)
    return await UserRead.of(session, user)


@router.post("/achievements/seen")
async def saw_achievements(user: CurrentUser, session: SessionDep) -> UserRead:
    """They've seen what they earned, so it stops being marked new."""
    await achievements.mark_seen(session, user.id)
    await session.commit()
    return await UserRead.of(session, user)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(user: CurrentUser, session: SessionDep) -> None:
    # Removes our data only; the Kinde login itself remains until deleted there.
    await hand_over_groups(session, user)
    await session.delete(user)
    await session.commit()
