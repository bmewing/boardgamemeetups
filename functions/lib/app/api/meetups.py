"""A group's dates: adding and editing them, who's coming and in what mood, the games that
fit, and a date as a calendar file."""

import uuid
from collections import defaultdict
from datetime import date, time
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app import ics
from app.api.friends import PersonRead
from app.api.games import GameSummary
from app.api.groups import Duration, Location, MeetupBrief, PlusOneLimit, meetup_briefs
from app.auth import CurrentUser
from app.calendar import file_name, meetup_event
from app.db import SessionDep
from app.groups import TableFit, membership, require_runner, table_fit
from app.models import (
    Game,
    Group,
    GroupMember,
    GroupRole,
    Meetup,
    MeetupRsvp,
    MeetupRsvpMood,
    MeetupStatus,
    Mood,
    Ownership,
    RsvpResponse,
    User,
    UserGame,
)
from app.schedule import instant

router = APIRouter(tags=["meetups"])

Notes = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]
MoodId = Annotated[str, StringConstraints(min_length=1, max_length=32)]
# Rules out every other mood.
NO_PREFERENCE = "no_preference"
MAX_RSVP_MOODS = 20
CALENDAR_FILE: dict[int | str, dict[str, Any]] = {
    200: {"content": {"text/calendar": {"schema": {"type": "string"}}}}
}
MEETUP_NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, "Meetup not found")
# Changing any of these makes a scheduled date "edited", so the schedule leaves it alone.
SCHEDULE_FIELDS = {"local_date", "local_time", "duration_minutes", "location", "status"}


class MeetupCreate(BaseModel):
    """A date of its own. Time, length and place default to the group's."""

    local_date: date
    local_time: time | None = None
    duration_minutes: Duration | None = None
    location: Location | None = None
    notes: Notes | None = None


class MeetupUpdate(BaseModel):
    local_date: date | None = None
    local_time: time | None = None
    duration_minutes: Duration | None = None
    location: Location | None = None
    notes: Notes | None = None
    status: MeetupStatus | None = None


class GroupBrief(BaseModel):
    id: uuid.UUID
    name: str
    time_zone: str
    willing_to_split: bool
    plus_one_limit: int


class RsvpRead(BaseModel):
    person: PersonRead
    response: RsvpResponse
    guests: int
    moods: list[str]


class MeetupRead(MeetupBrief):
    notes: str | None
    group: GroupBrief
    my_role: GroupRole
    rsvps: list[RsvpRead]
    no_answer: list[PersonRead]  # members who haven't said yet
    my_guests: int
    my_moods: list[str]


class RsvpIn(BaseModel):
    """Your whole answer. Guests and moods only go with a yes or maybe; a no clears them."""

    response: RsvpResponse
    guests: PlusOneLimit = 0
    moods: Annotated[list[MoodId], Field(max_length=MAX_RSVP_MOODS)] = Field(default_factory=list)


class FittingGame(BaseModel):
    game: GameSummary
    bringers: list[PersonRead]  # people coming who own it and will bring it
    # One table of everyone, or a table of some of them while the rest play something else.
    fit: TableFit


class MeetupGames(BaseModel):
    confirmed: int  # the headcount: members going plus their guests
    guests: int  # of those, guests
    willing_to_split: bool
    games: list[FittingGame]
    unknown_player_count: int  # games left out because BGG hasn't said how many they seat


async def _meetup(
    session: AsyncSession, meetup_id: uuid.UUID, user: User
) -> tuple[Meetup, Group, GroupMember]:
    meetup = await session.get(Meetup, meetup_id)
    if meetup is None:
        raise MEETUP_NOT_FOUND
    try:
        group, me = await membership(session, meetup.group_id, user)
    except HTTPException as exc:
        raise MEETUP_NOT_FOUND from exc
    return meetup, group, me


async def _read(
    session: AsyncSession, meetup: Meetup, group: Group, me: GroupMember, user: User
) -> MeetupRead:
    brief = (await meetup_briefs(session, [meetup], user))[0]
    members = await session.execute(
        select(User, MeetupRsvp)
        .join(GroupMember, GroupMember.user_id == User.id)
        .outerjoin(
            MeetupRsvp, (MeetupRsvp.user_id == User.id) & (MeetupRsvp.meetup_id == meetup.id)
        )
        .where(GroupMember.group_id == group.id)
        .order_by(func.lower(User.display_name))
    )
    moods: dict[uuid.UUID, list[str]] = defaultdict(list)
    mood_rows = await session.execute(
        select(MeetupRsvpMood.user_id, MeetupRsvpMood.mood_id)
        .join(Mood, Mood.id == MeetupRsvpMood.mood_id)
        .where(MeetupRsvpMood.meetup_id == meetup.id)
        .order_by(Mood.sort_order)
    )
    for user_id, mood_id in mood_rows:
        moods[user_id].append(mood_id)
    rsvps: list[RsvpRead] = []
    no_answer: list[PersonRead] = []
    my_guests = 0
    for person, answer in members:
        if answer is None:
            no_answer.append(PersonRead.of(person))
            continue
        rsvps.append(
            RsvpRead(
                person=PersonRead.of(person),
                response=answer.response,
                guests=answer.guests,
                moods=moods[person.id],
            )
        )
        if person.id == user.id:
            my_guests = answer.guests
    return MeetupRead(
        **brief.model_dump(),
        notes=meetup.notes,
        group=GroupBrief(
            id=group.id,
            name=group.name,
            time_zone=group.time_zone,
            willing_to_split=group.willing_to_split,
            plus_one_limit=group.plus_one_limit,
        ),
        my_role=me.role,
        rsvps=rsvps,
        no_answer=no_answer,
        my_guests=my_guests,
        my_moods=moods[user.id],
    )


@router.post("/groups/{group_id}/meetups", status_code=status.HTTP_201_CREATED)
async def add_meetup(
    group_id: uuid.UUID, body: MeetupCreate, user: CurrentUser, session: SessionDep
) -> MeetupRead:
    group, me = await membership(session, group_id, user)
    require_runner(me)
    local_time = body.local_time or group.start_time
    meetup = Meetup(
        group_id=group.id,
        local_date=body.local_date,
        local_time=local_time,
        starts_at=instant(body.local_date, local_time, group.time_zone),
        duration_minutes=body.duration_minutes or group.duration_minutes,
        location=body.location or group.location,
        notes=body.notes or None,
        status=MeetupStatus.SCHEDULED,
    )
    session.add(meetup)
    await session.commit()
    return await _read(session, meetup, group, me, user)


@router.get("/meetups/{meetup_id}")
async def read_meetup(meetup_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> MeetupRead:
    meetup, group, me = await _meetup(session, meetup_id, user)
    return await _read(session, meetup, group, me, user)


@router.patch("/meetups/{meetup_id}")
async def update_meetup(
    meetup_id: uuid.UUID, changes: MeetupUpdate, user: CurrentUser, session: SessionDep
) -> MeetupRead:
    """Move, change or cancel one date. A scheduled date changed this way is left alone
    by later schedule changes (notes alone don't count)."""
    meetup, group, me = await _meetup(session, meetup_id, user)
    require_runner(me)
    sent = changes.model_fields_set
    for field in ("local_date", "local_time", "duration_minutes", "status"):
        value = getattr(changes, field)
        if field in sent and value is not None:
            setattr(meetup, field, value)
    if "location" in sent:
        meetup.location = changes.location or None
    if "notes" in sent:
        meetup.notes = changes.notes or None
    if sent & SCHEDULE_FIELDS and meetup.slot_date is not None:
        meetup.is_overridden = True
    meetup.starts_at = instant(meetup.local_date, meetup.local_time, group.time_zone)
    await session.commit()
    return await _read(session, meetup, group, me, user)


@router.delete("/meetups/{meetup_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_meetup(meetup_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> None:
    """Remove a date added on its own. Scheduled dates are cancelled instead, so the
    schedule doesn't bring them back."""
    meetup, _group, me = await _meetup(session, meetup_id, user)
    require_runner(me)
    if meetup.slot_date is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This date comes from the schedule; cancel it instead."
        )
    await session.delete(meetup)
    await session.commit()


@router.put("/meetups/{meetup_id}/rsvp")
async def rsvp(
    meetup_id: uuid.UUID, body: RsvpIn, user: CurrentUser, session: SessionDep
) -> MeetupRead:
    meetup, group, me = await _meetup(session, meetup_id, user)
    if meetup.status == MeetupStatus.CANCELLED:
        raise HTTPException(status.HTTP_409_CONFLICT, "This date has been cancelled.")
    might_come = body.response != RsvpResponse.NO
    guests = body.guests if might_come else 0
    moods = list(dict.fromkeys(body.moods)) if might_come else []
    if guests > group.plus_one_limit:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"This group allows up to {group.plus_one_limit} guests each."
            if group.plus_one_limit
            else "This group doesn't allow guests.",
        )
    await _check_moods(session, moods)
    await session.execute(
        insert(MeetupRsvp)
        .values(meetup_id=meetup.id, user_id=user.id, response=body.response, guests=guests)
        .on_conflict_do_update(
            index_elements=[MeetupRsvp.meetup_id, MeetupRsvp.user_id],
            set_={"response": body.response, "guests": guests, "responded_at": func.now()},
        )
    )
    await session.execute(
        delete(MeetupRsvpMood).where(
            MeetupRsvpMood.meetup_id == meetup.id, MeetupRsvpMood.user_id == user.id
        )
    )
    if moods:
        await session.execute(
            insert(MeetupRsvpMood).values(
                [{"meetup_id": meetup.id, "user_id": user.id, "mood_id": m} for m in moods]
            )
        )
    await session.commit()
    return await _read(session, meetup, group, me, user)


async def _check_moods(session: AsyncSession, mood_ids: list[str]) -> None:
    """Any mood on the list will do for a date, including ones that can't go on a game."""
    if NO_PREFERENCE in mood_ids and len(mood_ids) > 1:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "No preference can't go with other moods."
        )
    known = set(await session.scalars(select(Mood.id).where(Mood.id.in_(mood_ids))))
    if unknown := sorted(set(mood_ids) - known):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"Unknown moods: {', '.join(unknown)}"
        )


@router.get("/meetups/{meetup_id}/calendar.ics", response_class=Response, responses=CALENDAR_FILE)
async def meetup_calendar_file(
    meetup_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> Response:
    """This date as a calendar file, to add to any calendar app."""
    meetup, group, _me = await _meetup(session, meetup_id, user)
    return Response(
        ics.calendar([meetup_event(meetup, group)]),
        media_type="text/calendar",
        headers={"Content-Disposition": f'attachment; filename="{file_name(meetup, group)}"'},
    )


@router.get("/meetups/{meetup_id}/games")
async def list_meetup_games(
    meetup_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> MeetupGames:
    """Games the people coming could play: owned and marked "will bring" by someone who said
    yes, and playable by everyone going (guests included), all together or (if the group is
    willing to split) at a table that leaves nobody on their own."""
    meetup, group, _me = await _meetup(session, meetup_id, user)
    going = (MeetupRsvp.meetup_id == meetup.id) & (MeetupRsvp.response == RsvpResponse.YES)
    coming = select(MeetupRsvp.user_id).where(going)
    members, guests = (
        await session.execute(
            select(func.count(), func.coalesce(func.sum(MeetupRsvp.guests), 0)).where(going)
        )
    ).one()
    confirmed = members + guests
    rows = await session.execute(
        select(Game, User)
        .join(UserGame, UserGame.game_id == Game.id)
        .join(User, User.id == UserGame.user_id)
        .where(
            UserGame.user_id.in_(coming),
            UserGame.ownership == Ownership.OWNED,
            UserGame.will_bring.is_(True),
            Game.is_expansion.is_(False),
        )
        .order_by(Game.name, func.lower(User.display_name))
    )
    games: dict[int, Game] = {}
    bringers: dict[int, list[PersonRead]] = defaultdict(list)
    for game, person in rows:
        games[game.id] = game
        bringers[game.id].append(PersonRead.of(person))

    fitting: list[FittingGame] = []
    unknown = 0
    for game_id, game in games.items():
        if game.max_players is None:
            unknown += 1
            continue
        fit = table_fit(game.min_players, game.max_players, confirmed, group.willing_to_split)
        if fit is not None:
            fitting.append(
                FittingGame(game=GameSummary.from_game(game), bringers=bringers[game_id], fit=fit)
            )
    # Games everyone can play together come first.
    fitting.sort(key=lambda g: (g.fit != "together", g.game.name.lower()))
    return MeetupGames(
        confirmed=confirmed,
        guests=guests,
        willing_to_split=group.willing_to_split,
        games=fitting,
        unknown_player_count=unknown,
    )
