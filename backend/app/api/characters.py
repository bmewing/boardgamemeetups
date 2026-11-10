"""People's RPG characters, and the parties they make up in RPG groups."""

import uuid
from datetime import datetime
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, status
from pydantic import AfterValidator, BaseModel, Field, StringConstraints
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.friends import PersonRead
from app.api.rpg_systems import RpgSystemSummary, SystemAnswers
from app.auth import CurrentUser
from app.db import SessionDep
from app.groups import membership, require_rpg
from app.models import (
    Character,
    CharacterStatus,
    Group,
    GroupMember,
    RpgSystem,
    User,
    UserRpgSystem,
)

router = APIRouter(tags=["rpg"])

CHARACTER_NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, "Character not found")


def _web_address(value: str) -> str:
    """Only http(s) links, so a portrait or sheet link can't run script in the page. Blank
    clears the link."""
    if not value:
        return value
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ValueError("Use a web address starting with http:// or https://")
    return value


Text120 = Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)]
WebAddress = Annotated[
    str,
    StringConstraints(strip_whitespace=True, max_length=1024),
    AfterValidator(_web_address),
]


class GroupBrief(BaseModel):
    id: uuid.UUID
    name: str


class CharacterRead(BaseModel):
    id: uuid.UUID
    owner: PersonRead
    system: RpgSystemSummary
    name: str
    class_role: str | None
    level: int | None
    ancestry: str | None
    pronouns: str | None
    status: CharacterStatus
    notes: str | None  # backstory and the like; the party sees it too
    portrait_url: str | None
    sheet_url: str | None
    group: GroupBrief | None  # the party it plays in
    created_at: datetime
    updated_at: datetime


class CharacterFields(BaseModel):
    class_role: Text120 | None = None
    level: Annotated[int, Field(ge=0, le=1000)] | None = None
    ancestry: Text120 | None = None
    pronouns: Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)] | None = None
    status: CharacterStatus | None = None
    notes: Annotated[str, StringConstraints(strip_whitespace=True, max_length=10_000)] | None = None
    portrait_url: WebAddress | None = None
    sheet_url: WebAddress | None = None


CharacterName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)
]


class CharacterCreate(CharacterFields):
    name: CharacterName
    system_id: int
    group_id: uuid.UUID | None = None  # join a party straight away


class CharacterUpdate(CharacterFields):
    """Fields to change; anything left out keeps its value. A null group leaves the party."""

    name: CharacterName | None = None
    system_id: int | None = None
    group_id: uuid.UUID | None = None


async def _read(session: AsyncSession, character: Character) -> CharacterRead:
    owner = await session.get(User, character.user_id)
    system = await session.get(RpgSystem, character.system_id)
    group = await session.get(Group, character.group_id) if character.group_id else None
    assert owner is not None and system is not None
    return CharacterRead(
        id=character.id,
        owner=PersonRead.of(owner),
        system=RpgSystemSummary.of(system),
        name=character.name,
        class_role=character.class_role,
        level=character.level,
        ancestry=character.ancestry,
        pronouns=character.pronouns,
        status=character.status,
        notes=character.notes,
        portrait_url=character.portrait_url,
        sheet_url=character.sheet_url,
        group=GroupBrief(id=group.id, name=group.name) if group else None,
        created_at=character.created_at,
        updated_at=character.updated_at,
    )


async def _check_system(session: AsyncSession, system_id: int) -> None:
    if await session.get(RpgSystem, system_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Pick a system")


async def _check_party(session: AsyncSession, group_id: uuid.UUID, user: User) -> None:
    """You can only put a character in an RPG group you're in."""
    group, _me = await membership(session, group_id, user)
    require_rpg(group)


def _blank_to_none(updates: dict[str, object]) -> dict[str, object]:
    return {k: (None if v == "" else v) for k, v in updates.items()}


@router.get("/me/characters")
async def list_my_characters(user: CurrentUser, session: SessionDep) -> list[CharacterRead]:
    characters = await session.scalars(
        select(Character).where(Character.user_id == user.id).order_by(Character.name)
    )
    return [await _read(session, c) for c in characters]


@router.post("/me/characters", status_code=status.HTTP_201_CREATED)
async def create_character(
    body: CharacterCreate, user: CurrentUser, session: SessionDep
) -> CharacterRead:
    await _check_system(session, body.system_id)
    if body.group_id is not None:
        await _check_party(session, body.group_id, user)
    fields = _blank_to_none(body.model_dump(exclude={"status"}))
    character = Character(user_id=user.id, status=body.status or CharacterStatus.ACTIVE, **fields)
    session.add(character)
    await session.commit()
    await session.refresh(character)
    return await _read(session, character)


async def _visible(session: AsyncSession, character_id: uuid.UUID, user: User) -> Character:
    """Yours, or in the party of a group you're in. Anyone else's looks like it isn't there."""
    character = await session.get(Character, character_id)
    if character is None:
        raise CHARACTER_NOT_FOUND
    if character.user_id == user.id:
        return character
    if character.group_id is not None:
        in_group = await session.get(GroupMember, (character.group_id, user.id))
        if in_group is not None:
            return character
    raise CHARACTER_NOT_FOUND


async def _mine(session: AsyncSession, character_id: uuid.UUID, user: User) -> Character:
    character = await _visible(session, character_id, user)
    if character.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only its player can change a character.")
    return character


@router.get("/characters/{character_id}")
async def read_character(
    character_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> CharacterRead:
    return await _read(session, await _visible(session, character_id, user))


@router.patch("/characters/{character_id}")
async def update_character(
    character_id: uuid.UUID, changes: CharacterUpdate, user: CurrentUser, session: SessionDep
) -> CharacterRead:
    character = await _mine(session, character_id, user)
    updates = _blank_to_none(changes.model_dump(exclude_unset=True))
    for required in ("name", "system_id", "status"):
        if required in updates and updates[required] is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, f"A character needs a {required}"
            )
    if changes.system_id is not None:
        await _check_system(session, changes.system_id)
    if changes.group_id is not None and changes.group_id != character.group_id:
        await _check_party(session, changes.group_id, user)
    for name, value in updates.items():
        setattr(character, name, value)
    await session.commit()
    await session.refresh(character)
    return await _read(session, character)


@router.delete("/characters/{character_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_character(character_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> None:
    await session.delete(await _mine(session, character_id, user))
    await session.commit()


class PartyMember(BaseModel):
    person: PersonRead
    is_gm: bool
    # What they say about the group's system; null if they haven't said or there's none.
    answers: SystemAnswers | None


class PartyRead(BaseModel):
    system: RpgSystemSummary | None
    characters: list[CharacterRead]  # every member's characters in this group, active first
    members: list[PartyMember]


STATUS_ORDER = {CharacterStatus.ACTIVE: 0, CharacterStatus.RETIRED: 1, CharacterStatus.DEAD: 2}


@router.get("/groups/{group_id}/party")
async def read_party(group_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> PartyRead:
    group, _me = await membership(session, group_id, user)
    require_rpg(group)
    system = await session.get(RpgSystem, group.rpg_system_id) if group.rpg_system_id else None
    characters = list(
        await session.scalars(
            select(Character).where(Character.group_id == group.id).order_by(Character.name)
        )
    )
    characters.sort(key=lambda c: STATUS_ORDER[c.status])
    members = await session.execute(
        select(GroupMember, User)
        .join(User, User.id == GroupMember.user_id)
        .where(GroupMember.group_id == group.id)
        .order_by(GroupMember.is_gm.desc(), GroupMember.joined_at)
    )
    answers: dict[uuid.UUID, UserRpgSystem] = {}
    if system is not None:
        rows = await session.scalars(
            select(UserRpgSystem).where(
                UserRpgSystem.system_id == system.id,
                UserRpgSystem.user_id.in_(
                    select(GroupMember.user_id).where(GroupMember.group_id == group.id)
                ),
            )
        )
        answers = {row.user_id: row for row in rows}

    def answer_of(user_id: uuid.UUID) -> SystemAnswers | None:
        row = answers.get(user_id)
        if row is None:
            return None
        return SystemAnswers(knows=row.knows, can_gm=row.can_gm, want_to_play=row.want_to_play)

    return PartyRead(
        system=RpgSystemSummary.of(system) if system else None,
        characters=[await _read(session, c) for c in characters],
        members=[
            PartyMember(
                person=PersonRead.of(person), is_gm=member.is_gm, answers=answer_of(person.id)
            )
            for member, person in members
        ],
    )
