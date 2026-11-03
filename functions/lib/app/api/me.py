import uuid
from typing import Annotated
from zoneinfo import available_timezones

from fastapi import APIRouter, status
from pydantic import AfterValidator, BaseModel, ConfigDict, StringConstraints

from app.auth import CurrentUser
from app.db import SessionDep
from app.models import CollectionVisibility

router = APIRouter(prefix="/me", tags=["me"])

TIME_ZONES = frozenset(available_timezones())


def known_time_zone(value: str) -> str:
    if value not in TIME_ZONES:
        raise ValueError("Unknown time zone")
    return value


def blank_to_none(value: str | None) -> str | None:
    return value or None


DisplayName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
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
    time_zone: str
    bgg_username: str | None
    collection_visibility: CollectionVisibility


class UserUpdate(BaseModel):
    display_name: DisplayName | None = None
    time_zone: TimeZone | None = None
    bgg_username: BggUsername = None
    collection_visibility: CollectionVisibility | None = None


@router.get("")
async def read_me(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)


@router.patch("")
async def update_me(changes: UserUpdate, user: CurrentUser, session: SessionDep) -> UserRead:
    for field, value in changes.model_dump(exclude_unset=True).items():
        # bgg_username may be cleared; the other fields are required on the user.
        if value is not None or field == "bgg_username":
            setattr(user, field, value)
    await session.commit()
    await session.refresh(user)
    return UserRead.model_validate(user)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(user: CurrentUser, session: SessionDep) -> None:
    # Removes our data only; the Kinde login itself remains until deleted there.
    await session.delete(user)
    await session.commit()
