import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, status
from pydantic import AfterValidator, BaseModel, ConfigDict, StringConstraints
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.auth import TIME_ZONES, CurrentUser
from app.db import SessionDep
from app.email import EmailKind
from app.groups import hand_over_groups
from app.models import CollectionVisibility, User
from app.pieces import Piece, PieceColor

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
BggUsername = Annotated[
    str | None,
    StringConstraints(strip_whitespace=True, max_length=64),
    AfterValidator(blank_to_none),
]


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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
    collection_visibility: CollectionVisibility
    email_opt_outs: list[EmailKind]  # kinds of email turned off
    is_admin: bool  # can open the admin portal


class UserUpdate(BaseModel):
    display_name: DisplayName | None = None
    time_zone: TimeZone | None = None
    bgg_username: BggUsername = None
    collection_visibility: CollectionVisibility | None = None
    email_opt_outs: list[EmailKind] | None = None
    piece: Piece | None = None
    piece_color: PieceColor | None = None


# Fields that may be cleared by sending null; the rest are required on the user.
CLEARABLE = {"bgg_username", "piece", "piece_color"}


@router.get("")
async def read_me(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)


NAME_TAKEN = HTTPException(status.HTTP_409_CONFLICT, "That name is taken. Try another.")


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
    return UserRead.model_validate(user)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(user: CurrentUser, session: SessionDep) -> None:
    # Removes our data only; the Kinde login itself remains until deleted there.
    await hand_over_groups(session, user)
    await session.delete(user)
    await session.commit()
