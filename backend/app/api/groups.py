"""Groups: making them, inviting people, roles, the schedule, and the group's games."""

import uuid
from collections import defaultdict
from datetime import date, datetime, time
from typing import Annotated

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import ColumnElement, and_, delete, exists, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.collection import GameBrief
from app.api.friends import PersonPick, PersonRead, SharedAnswers, find_person
from app.api.games import GameSummary
from app.api.me import TimeZone
from app.api.rollups import RollupRead
from app.auth import CurrentUser
from app.db import SessionDep
from app.friends import has_blocked
from app.groups import membership, require_owner, require_runner
from app.models import (
    Game,
    Group,
    GroupInvite,
    GroupMember,
    GroupRole,
    Meetup,
    MeetupRsvp,
    MeetupStatus,
    Ownership,
    RsvpResponse,
    User,
    UserBlock,
    UserGame,
)
from app.recommend import Answer, Person, rollup
from app.schedule import SCHEDULE, Schedule, move_to_time_zone, sync_meetups, today_in

router = APIRouter(tags=["groups"])

GroupName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]
Location = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]
Duration = Annotated[int, Field(ge=15, le=24 * 60)]
PlusOneLimit = Annotated[int, Field(ge=0, le=10)]
RECENT_DATES = 3


class MeetupBrief(BaseModel):
    id: uuid.UUID
    local_date: date
    local_time: time
    starts_at: datetime
    duration_minutes: int
    location: str | None
    status: MeetupStatus
    scheduled: bool  # came from the group's schedule
    edited: bool  # changed by hand, so schedule changes leave it alone
    yes: int
    maybe: int
    no: int
    headcount: int  # members going plus the guests they're bringing
    my_response: RsvpResponse | None


class GroupSummary(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    my_role: GroupRole
    member_count: int
    next_meetup: MeetupBrief | None


class GroupInviteForMe(BaseModel):
    id: uuid.UUID
    group_id: uuid.UUID
    group_name: str
    group_description: str | None
    member_count: int
    invited_by: PersonRead | None
    created_at: datetime


class GroupsRead(BaseModel):
    groups: list[GroupSummary]
    invites: list[GroupInviteForMe]


class MemberRead(BaseModel):
    person: PersonRead
    role: GroupRole
    joined_at: datetime


class GroupInviteRead(BaseModel):
    """Who's invited: the person if they're on the app, otherwise the email typed in. A
    person's email is never shown, even when that's what the invite was sent to."""

    id: uuid.UUID
    person: PersonRead | None
    email: str | None
    invited_by: PersonRead | None
    created_at: datetime


class GroupRead(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    time_zone: str
    willing_to_split: bool
    schedule: Schedule | None
    start_time: time
    duration_minutes: int
    location: str | None
    plus_one_limit: int
    my_role: GroupRole
    members: list[MemberRead]
    invites: list[GroupInviteRead]  # waiting for an answer; only the owner and admins see them
    upcoming: list[MeetupBrief]
    recent: list[MeetupBrief]


class GroupCreate(BaseModel):
    name: GroupName
    description: Description | None = None
    willing_to_split: bool = False
    # Left out: the creator's own time zone.
    time_zone: TimeZone | None = None


class GroupUpdate(BaseModel):
    """Fields to change; anything left out keeps its value. A null schedule turns it off."""

    name: GroupName | None = None
    description: Description | None = None
    time_zone: TimeZone | None = None
    willing_to_split: bool | None = None
    schedule: Schedule | None = None
    start_time: time | None = None
    duration_minutes: Duration | None = None
    location: Location | None = None
    # Lowering it trims guests already on upcoming dates down to the new limit.
    plus_one_limit: PlusOneLimit | None = None


class InviteResult(BaseModel):
    invite: GroupInviteRead
    # False: nobody signs in with that email yet; the invite waits until someone does.
    on_app: bool


class MemberUpdate(BaseModel):
    """`owner` hands the group over; the current owner becomes an admin."""

    role: GroupRole


class MemberAnswers(SharedAnswers):
    person: PersonRead


class GroupGameRead(BaseModel):
    game: GameSummary
    owners: list[PersonRead]  # members who own it
    expansions: list[GameBrief]  # expansions for it that members own
    answers: list[MemberAnswers]  # every member who has answered anything about it
    rollup: RollupRead  # every member's answers combined


def _brief(game: Game) -> GameBrief:
    return GameBrief(
        id=game.id,
        name=game.name,
        year_published=game.year_published,
        thumbnail_url=game.thumbnail_url,
        is_expansion=game.is_expansion,
    )


async def meetup_briefs(
    session: AsyncSession, meetups: list[Meetup], user: User
) -> list[MeetupBrief]:
    ids = [m.id for m in meetups]
    counts: dict[uuid.UUID, dict[RsvpResponse, int]] = defaultdict(dict)
    guests_going: dict[uuid.UUID, int] = defaultdict(int)
    mine: dict[uuid.UUID, RsvpResponse] = {}
    if ids:
        tallies = await session.execute(
            select(
                MeetupRsvp.meetup_id,
                MeetupRsvp.response,
                func.count(),
                func.coalesce(func.sum(MeetupRsvp.guests), 0),
            )
            .where(MeetupRsvp.meetup_id.in_(ids))
            .group_by(MeetupRsvp.meetup_id, MeetupRsvp.response)
        )
        for meetup_id, response, count, guests in tallies:
            counts[meetup_id][response] = count
            if response == RsvpResponse.YES:
                guests_going[meetup_id] = int(guests)
        own = await session.execute(
            select(MeetupRsvp.meetup_id, MeetupRsvp.response).where(
                MeetupRsvp.meetup_id.in_(ids), MeetupRsvp.user_id == user.id
            )
        )
        mine = {meetup_id: response for meetup_id, response in own}
    return [
        MeetupBrief(
            id=m.id,
            local_date=m.local_date,
            local_time=m.local_time,
            starts_at=m.starts_at,
            duration_minutes=m.duration_minutes,
            location=m.location,
            status=m.status,
            scheduled=m.slot_date is not None,
            edited=m.is_overridden,
            yes=counts[m.id].get(RsvpResponse.YES, 0),
            maybe=counts[m.id].get(RsvpResponse.MAYBE, 0),
            no=counts[m.id].get(RsvpResponse.NO, 0),
            headcount=counts[m.id].get(RsvpResponse.YES, 0) + guests_going[m.id],
            my_response=mine.get(m.id),
        )
        for m in meetups
    ]


async def _trim_guests(session: AsyncSession, group: Group) -> None:
    """Bring guests on upcoming dates down to the group's plus-one limit. Past dates keep
    who actually came."""
    upcoming = select(Meetup.id).where(
        Meetup.group_id == group.id, Meetup.local_date >= today_in(group.time_zone)
    )
    await session.execute(
        update(MeetupRsvp)
        .where(MeetupRsvp.meetup_id.in_(upcoming), MeetupRsvp.guests > group.plus_one_limit)
        .values(guests=group.plus_one_limit)
    )


def _invites_for(user: User) -> ColumnElement[bool]:
    """Invites to the user's email, leaving out ones from people they've blocked."""
    blocked_inviter = exists().where(
        UserBlock.blocker_id == user.id, UserBlock.blocked_id == GroupInvite.invited_by_id
    )
    return and_(GroupInvite.email == func.lower(user.email or ""), ~blocked_inviter)


@router.get("/groups")
async def list_groups(user: CurrentUser, session: SessionDep) -> GroupsRead:
    member_count = (
        select(func.count())
        .where(GroupMember.group_id == Group.id)
        .correlate(Group)
        .scalar_subquery()
    )
    rows = await session.execute(
        select(Group, GroupMember.role, member_count)
        .join(GroupMember, GroupMember.group_id == Group.id)
        .where(GroupMember.user_id == user.id)
        .order_by(func.lower(Group.name))
    )
    groups = []
    for group, role, count in rows:
        today = today_in(group.time_zone)
        next_meetup = await session.scalar(
            select(Meetup)
            .where(
                Meetup.group_id == group.id,
                Meetup.local_date >= today,
                Meetup.status == MeetupStatus.SCHEDULED,
            )
            .order_by(Meetup.starts_at)
            .limit(1)
        )
        briefs = await meetup_briefs(session, [next_meetup] if next_meetup else [], user)
        groups.append(
            GroupSummary(
                id=group.id,
                name=group.name,
                description=group.description,
                my_role=role,
                member_count=count,
                next_meetup=briefs[0] if briefs else None,
            )
        )

    invites = []
    if user.email:
        invite_rows = await session.execute(
            select(GroupInvite, Group, User, member_count)
            .join(Group, Group.id == GroupInvite.group_id)
            .outerjoin(User, User.id == GroupInvite.invited_by_id)
            .where(_invites_for(user))
            .order_by(GroupInvite.created_at)
        )
        for invite, group, inviter, count in invite_rows:
            invites.append(
                GroupInviteForMe(
                    id=invite.id,
                    group_id=group.id,
                    group_name=group.name,
                    group_description=group.description,
                    member_count=count,
                    invited_by=PersonRead.of(inviter) if inviter else None,
                    created_at=invite.created_at,
                )
            )
    return GroupsRead(groups=groups, invites=invites)


@router.post("/groups", status_code=status.HTTP_201_CREATED)
async def create_group(body: GroupCreate, user: CurrentUser, session: SessionDep) -> GroupRead:
    group = Group(
        name=body.name,
        description=body.description or None,
        willing_to_split=body.willing_to_split,
        time_zone=body.time_zone or user.time_zone,
    )
    session.add(group)
    await session.flush()
    session.add(GroupMember(group_id=group.id, user_id=user.id, role=GroupRole.OWNER))
    await session.commit()
    return await read_group(group.id, user, session)


@router.get("/groups/{group_id}")
async def read_group(group_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> GroupRead:
    """The group, its members and dates. Opening it tops up the scheduled dates."""
    group, me = await membership(session, group_id, user)
    await sync_meetups(session, group)
    today = today_in(group.time_zone)

    members = await session.execute(
        select(GroupMember, User)
        .join(User, User.id == GroupMember.user_id)
        .where(GroupMember.group_id == group.id)
        .order_by(GroupMember.joined_at)
    )
    invites: list[GroupInviteRead] = []
    if me.role in (GroupRole.OWNER, GroupRole.ADMIN):
        pending = await session.scalars(
            select(GroupInvite)
            .where(GroupInvite.group_id == group.id)
            .order_by(GroupInvite.created_at)
        )
        invites = [await _invite_read(session, invite, user) for invite in pending]
    upcoming = list(
        await session.scalars(
            select(Meetup)
            .where(Meetup.group_id == group.id, Meetup.local_date >= today)
            .order_by(Meetup.starts_at)
        )
    )
    recent = list(
        await session.scalars(
            select(Meetup)
            .where(Meetup.group_id == group.id, Meetup.local_date < today)
            .order_by(Meetup.starts_at.desc())
            .limit(RECENT_DATES)
        )
    )
    return GroupRead(
        id=group.id,
        name=group.name,
        description=group.description,
        time_zone=group.time_zone,
        willing_to_split=group.willing_to_split,
        schedule=SCHEDULE.validate_python(group.schedule) if group.schedule else None,
        start_time=group.start_time,
        duration_minutes=group.duration_minutes,
        location=group.location,
        plus_one_limit=group.plus_one_limit,
        my_role=me.role,
        members=[
            MemberRead(person=PersonRead.of(person), role=member.role, joined_at=member.joined_at)
            for member, person in members
        ],
        invites=invites,
        upcoming=await meetup_briefs(session, upcoming, user),
        recent=await meetup_briefs(session, recent, user),
    )


@router.patch("/groups/{group_id}")
async def update_group(
    group_id: uuid.UUID, changes: GroupUpdate, user: CurrentUser, session: SessionDep
) -> GroupRead:
    """Change the group's details or schedule. Untouched future dates follow along."""
    group, me = await membership(session, group_id, user)
    require_runner(me)
    sent = changes.model_fields_set
    for field in ("name", "time_zone", "willing_to_split", "start_time", "duration_minutes"):
        value = getattr(changes, field)
        if field in sent and value is not None:
            setattr(group, field, value)
    if "description" in sent:
        group.description = changes.description or None
    if "location" in sent:
        group.location = changes.location or None
    if "schedule" in sent:
        group.schedule = changes.schedule.model_dump(mode="json") if changes.schedule else None
    if "time_zone" in sent and changes.time_zone:
        await move_to_time_zone(session, group, today_in(group.time_zone))
    if "plus_one_limit" in sent and changes.plus_one_limit is not None:
        group.plus_one_limit = changes.plus_one_limit
        await _trim_guests(session, group)
    await session.commit()
    return await read_group(group.id, user, session)


@router.delete("/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(group_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> None:
    group, me = await membership(session, group_id, user)
    require_owner(me)
    await session.delete(group)
    await session.commit()


@router.post("/groups/{group_id}/invites", status_code=status.HTTP_201_CREATED)
async def invite_to_group(
    group_id: uuid.UUID, body: PersonPick, user: CurrentUser, session: SessionDep
) -> InviteResult:
    """Invite someone picked from the search, or any email address. They join only if they
    accept. Someone who has blocked you looks the same as nobody using that email, and
    never sees the invite."""
    group, me = await membership(session, group_id, user)
    require_runner(me)
    invitee = await find_person(session, body)
    if body.user_id is not None and (
        invitee is None or invitee.email is None or await has_blocked(session, invitee.id, user.id)
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Person not found")
    if invitee is not None:
        already = await session.get(GroupMember, (group.id, invitee.id))
        if already is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "They're already in this group.")
    email = (body.email or (invitee.email if invitee else None) or "").lower()
    await session.execute(
        insert(GroupInvite)
        .values(id=uuid.uuid4(), group_id=group.id, email=email, invited_by_id=user.id)
        .on_conflict_do_nothing(index_elements=[GroupInvite.group_id, GroupInvite.email])
    )
    await session.commit()
    invite = await session.scalar(
        select(GroupInvite).where(GroupInvite.group_id == group.id, GroupInvite.email == email)
    )
    assert invite is not None
    on_app = invitee is not None and not await has_blocked(session, invitee.id, user.id)
    return InviteResult(invite=await _invite_read(session, invite, user), on_app=on_app)


async def _invite_read(session: AsyncSession, invite: GroupInvite, viewer: User) -> GroupInviteRead:
    invitee = await session.scalar(
        select(User).where(func.lower(User.email) == invite.email).limit(1)
    )
    shown = invitee is not None and not await has_blocked(session, invitee.id, viewer.id)
    inviter = await session.get(User, invite.invited_by_id) if invite.invited_by_id else None
    return GroupInviteRead(
        id=invite.id,
        person=PersonRead.of(invitee) if shown and invitee else None,
        email=None if shown else invite.email,
        invited_by=PersonRead.of(inviter) if inviter else None,
        created_at=invite.created_at,
    )


@router.delete("/groups/{group_id}/invites/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_group_invite(
    group_id: uuid.UUID, invite_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> None:
    group, me = await membership(session, group_id, user)
    require_runner(me)
    await session.execute(
        delete(GroupInvite).where(GroupInvite.id == invite_id, GroupInvite.group_id == group.id)
    )
    await session.commit()


async def _my_invite(session: AsyncSession, invite_id: uuid.UUID, user: User) -> GroupInvite:
    invite = await session.scalar(
        select(GroupInvite).where(GroupInvite.id == invite_id, _invites_for(user))
    )
    if invite is None or not user.email:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invite not found")
    return invite


@router.post("/group-invites/{invite_id}/accept")
async def accept_group_invite(
    invite_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> GroupRead:
    """Join the group. From now on its members see your games (never your notes)."""
    invite = await _my_invite(session, invite_id, user)
    group_id = invite.group_id
    await session.execute(
        insert(GroupMember)
        .values(group_id=group_id, user_id=user.id, role=GroupRole.MEMBER)
        .on_conflict_do_nothing()
    )
    await session.delete(invite)
    await session.commit()
    return await read_group(group_id, user, session)


@router.post("/group-invites/{invite_id}/decline", status_code=status.HTTP_204_NO_CONTENT)
async def decline_group_invite(
    invite_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> None:
    invite = await _my_invite(session, invite_id, user)
    await session.delete(invite)
    await session.commit()


async def _member(session: AsyncSession, group_id: uuid.UUID, user_id: uuid.UUID) -> GroupMember:
    member = await session.get(GroupMember, (group_id, user_id))
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not a member of this group")
    return member


@router.patch("/groups/{group_id}/members/{user_id}")
async def change_member_role(
    group_id: uuid.UUID,
    user_id: uuid.UUID,
    body: MemberUpdate,
    user: CurrentUser,
    session: SessionDep,
) -> GroupRead:
    """Only the owner makes admins, turns them back into members, or hands the group over."""
    group, me = await membership(session, group_id, user)
    require_owner(me)
    target = await _member(session, group.id, user_id)
    if target.user_id == user.id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Hand the group to someone else to change your role."
        )
    if body.role == GroupRole.OWNER:
        me.role = GroupRole.ADMIN
        await session.flush()  # one owner at a time
    target.role = body.role
    await session.commit()
    return await read_group(group.id, user, session)


@router.delete("/groups/{group_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    group_id: uuid.UUID, user_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> None:
    """Leave (your own id), or remove someone. Admins can remove members, not other admins;
    the owner can remove anyone. Their answers for dates still to come go with them."""
    group, me = await membership(session, group_id, user)
    target = await _member(session, group.id, user_id)
    leaving = target.user_id == user.id
    if leaving and me.role == GroupRole.OWNER:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Hand the group to someone else before you leave."
        )
    may_remove = me.role == GroupRole.OWNER or (
        me.role == GroupRole.ADMIN and target.role == GroupRole.MEMBER
    )
    if not leaving and not may_remove:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can't remove this member.")

    today = today_in(group.time_zone)
    upcoming = select(Meetup.id).where(Meetup.group_id == group.id, Meetup.local_date >= today)
    await session.execute(
        delete(MeetupRsvp).where(
            MeetupRsvp.user_id == target.user_id, MeetupRsvp.meetup_id.in_(upcoming)
        )
    )
    await session.delete(target)
    await session.commit()


@router.get("/groups/{group_id}/games")
async def list_group_games(
    group_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> list[GroupGameRead]:
    """Every game a member owns, with who owns it, what each member has said about it, and
    all of that combined (members with no answers count as new to it).

    Expansions are listed under their base game when a member owns that too.
    """
    group, _me = await membership(session, group_id, user)
    members = list(
        await session.scalars(
            select(User)
            .join(GroupMember, GroupMember.user_id == User.id)
            .where(GroupMember.group_id == group.id)
            .order_by(func.lower(User.display_name))
        )
    )
    people = {m.id: PersonRead.of(m) for m in members}
    scope = [Person(m.id, m.display_name) for m in members]
    names = {p.id: p for p in scope}
    rows = await session.execute(
        select(UserGame, Game, User)
        .join(Game, Game.id == UserGame.game_id)
        .join(User, User.id == UserGame.user_id)
        .join(GroupMember, GroupMember.user_id == UserGame.user_id)
        .where(GroupMember.group_id == group.id)
        .order_by(Game.name, func.lower(User.display_name))
    )
    games: dict[int, Game] = {}
    owners: dict[int, list[PersonRead]] = defaultdict(list)
    answers: dict[int, list[MemberAnswers]] = defaultdict(list)
    combined: dict[int, dict[uuid.UUID, Answer]] = defaultdict(dict)
    for row, game, person in rows:
        games[game.id] = game
        combined[game.id][person.id] = Answer.of(row, names[person.id])
        answers[game.id].append(
            MemberAnswers(person=PersonRead.of(person), **SharedAnswers.fields_of(row))
        )
        if row.ownership == Ownership.OWNED:
            owners[game.id].append(PersonRead.of(person))

    owned = {game_id for game_id in owners}
    expansions: dict[int, list[GameBrief]] = defaultdict(list)
    listed: list[int] = []
    for game_id in owned:
        game = games[game_id]
        bases = [b for b in game.base_game_ids if b in owned] if game.is_expansion else []
        if bases:
            for base in bases:
                expansions[base].append(_brief(game))
        else:
            listed.append(game_id)
    listed.sort(key=lambda game_id: games[game_id].name.lower())
    return [
        GroupGameRead(
            game=GameSummary.from_game(games[game_id]),
            owners=owners[game_id],
            expansions=sorted(expansions[game_id], key=lambda e: e.name.lower()),
            answers=answers[game_id],
            rollup=RollupRead.of(rollup(games[game_id], scope, combined[game_id]), people),
        )
        for game_id in listed
    ]
