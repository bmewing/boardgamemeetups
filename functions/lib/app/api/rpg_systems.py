"""RPG systems (from RPGGeek, or added here) and what each person says about them."""

import uuid
from datetime import UTC, datetime
from typing import Annotated, Self

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, StringConstraints
from sqlalchemy import select

from app import rpg_catalog
from app.api.games import BggDep
from app.auth import CurrentUser
from app.bgg import BggError
from app.db import SessionDep
from app.models import CUSTOM_RPG_SYSTEM_IDS, RpgSystem, UserRpgSystem

router = APIRouter(tags=["rpg"])

# A system's description is only shown in full on its own page.
SUMMARY_DESCRIPTION = 300


class RpgSystemSummary(BaseModel):
    id: int
    name: str
    thumbnail_url: str | None
    is_custom: bool  # added by someone here, not on RPGGeek

    @classmethod
    def of(cls, system: RpgSystem) -> Self:
        return cls(
            id=system.id,
            name=system.name,
            thumbnail_url=system.thumbnail_url,
            is_custom=system.is_custom,
        )


class RpgSystemDetail(RpgSystemSummary):
    description: str | None
    image_url: str | None
    rpggeek_url: str | None  # null for a system that isn't on RPGGeek
    created_by_id: uuid.UUID | None  # who added a custom system, and can edit it

    @classmethod
    def of(cls, system: RpgSystem) -> Self:
        return cls(
            id=system.id,
            name=system.name,
            thumbnail_url=system.thumbnail_url,
            is_custom=system.is_custom,
            description=system.description,
            image_url=system.image_url,
            rpggeek_url=None if system.is_custom else f"https://rpggeek.com/rpg/{system.id}",
            created_by_id=system.created_by_id,
        )


SystemName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
SystemDescription = Annotated[str, StringConstraints(strip_whitespace=True, max_length=5000)]


class CustomSystemIn(BaseModel):
    """A system that isn't on RPGGeek: a homebrew, or one RPGGeek just doesn't list."""

    name: SystemName
    description: SystemDescription | None = None


NOT_YOURS = HTTPException(
    status.HTTP_403_FORBIDDEN, "Only the person who added this system can change it."
)
SYSTEM_NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, "System not found")


@router.get("/rpg-systems/search")
async def search_systems(
    user: CurrentUser,
    session: SessionDep,
    bgg: BggDep,
    q: Annotated[str, Query(min_length=2, max_length=100)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[RpgSystemSummary]:
    systems = await rpg_catalog.search_systems(session, bgg, q, limit=limit, user_id=user.id)
    return [RpgSystemSummary.of(system) for system in systems]


@router.post("/rpg-systems", status_code=status.HTTP_201_CREATED)
async def add_custom_system(
    body: CustomSystemIn, user: CurrentUser, session: SessionDep
) -> RpgSystemDetail:
    """Add a system that isn't on RPGGeek. It goes in your systems as one you know."""
    system_id = await session.scalar(select(CUSTOM_RPG_SYSTEM_IDS.next_value()))
    assert system_id is not None
    system = RpgSystem(
        id=system_id,
        name=body.name,
        description=body.description or None,
        created_by_id=user.id,
        details_fetched_at=datetime.now(UTC),
    )
    session.add(system)
    await session.flush()
    session.add(UserRpgSystem(user_id=user.id, system_id=system.id, knows=True))
    await session.commit()
    await session.refresh(system)
    return RpgSystemDetail.of(system)


@router.put("/rpg-systems/{system_id}")
async def update_custom_system(
    system_id: int, body: CustomSystemIn, user: CurrentUser, session: SessionDep
) -> RpgSystemDetail:
    """Change a system you added. RPGGeek's systems come from RPGGeek."""
    system = await session.get(RpgSystem, system_id)
    if system is None:
        raise SYSTEM_NOT_FOUND
    if not system.is_custom or system.created_by_id != user.id:
        raise NOT_YOURS
    system.name = body.name
    system.description = body.description or None
    await session.commit()
    await session.refresh(system)
    return RpgSystemDetail.of(system)


@router.get("/rpg-systems/{system_id}")
async def read_system(
    system_id: int, _user: CurrentUser, session: SessionDep, bgg: BggDep
) -> RpgSystemDetail:
    try:
        system = await rpg_catalog.get_system(session, bgg, system_id)
    except BggError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "RPGGeek is unavailable right now"
        ) from exc
    if system is None:
        raise SYSTEM_NOT_FOUND
    return RpgSystemDetail.of(system)


class SystemAnswers(BaseModel):
    """What someone says about a system. Shared with their groups."""

    knows: bool
    can_gm: bool
    want_to_play: bool


class MySystemRead(SystemAnswers):
    system: RpgSystemSummary
    notes: str | None  # private to you
    updated_at: datetime


class MySystemUpdate(BaseModel):
    """Fields to change; anything left out keeps its value."""

    knows: bool | None = None
    can_gm: bool | None = None
    want_to_play: bool | None = None
    notes: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None = None


def _my_system(row: UserRpgSystem, system: RpgSystem) -> MySystemRead:
    return MySystemRead(
        system=RpgSystemSummary.of(system),
        knows=row.knows,
        can_gm=row.can_gm,
        want_to_play=row.want_to_play,
        notes=row.notes,
        updated_at=row.updated_at,
    )


@router.get("/me/rpg-systems")
async def list_my_systems(user: CurrentUser, session: SessionDep) -> list[MySystemRead]:
    rows = await session.execute(
        select(UserRpgSystem, RpgSystem)
        .join(RpgSystem, RpgSystem.id == UserRpgSystem.system_id)
        .where(UserRpgSystem.user_id == user.id)
        .order_by(RpgSystem.name)
    )
    return [_my_system(row, system) for row, system in rows]


@router.put("/me/rpg-systems/{system_id}")
async def update_my_system(
    system_id: int, changes: MySystemUpdate, user: CurrentUser, session: SessionDep
) -> MySystemRead:
    """Add a system to your list or change what you've said about it."""
    system = await session.get(RpgSystem, system_id)
    if system is None:
        raise SYSTEM_NOT_FOUND
    updates = changes.model_dump(exclude_unset=True)
    # A null answer means "no"; only notes can be blank.
    for flag in ("knows", "can_gm", "want_to_play"):
        if flag in updates and updates[flag] is None:
            updates[flag] = False
    if "notes" in updates:
        updates["notes"] = updates["notes"] or None
    row = await session.get(UserRpgSystem, (user.id, system_id))
    if row is None:
        row = UserRpgSystem(
            user_id=user.id,
            system_id=system_id,
            **{"knows": False, "can_gm": False, "want_to_play": False, **updates},
        )
        session.add(row)
    else:
        for name, value in updates.items():
            setattr(row, name, value)
    # Running a game means knowing it.
    if row.can_gm:
        row.knows = True
    await session.commit()
    await session.refresh(row)
    return _my_system(row, system)


@router.delete("/me/rpg-systems/{system_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_my_system(system_id: int, user: CurrentUser, session: SessionDep) -> None:
    row = await session.get(UserRpgSystem, (user.id, system_id))
    if row is not None:
        await session.delete(row)
        await session.commit()
