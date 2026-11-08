"""A group's dates: adding and editing them, who's coming and in what mood, the games that
fit (ranked for the people coming), and a date as a calendar file."""

import uuid
from collections import defaultdict
from datetime import date, time
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import achievements, ics, notify
from app.api.collection import GameBrief
from app.api.friends import PersonRead
from app.api.games import GameSummary
from app.api.groups import Duration, Location, MeetupBrief, PlusOneLimit, meetup_briefs
from app.api.rollups import ReasonRead, RollupRead
from app.auth import CurrentUser
from app.calendar import file_name, meetup_event
from app.db import SessionDep
from app.discord.cards import posted_cards, refresh_cards, remove_cards
from app.discord.client import DiscordDep
from app.email import MailerDep
from app.groups import TableFit, membership, player_range, require_runner, table_fit
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
from app.pieces import Achievement
from app.plays import fill_unlogged, recently_played
from app.recommend import Answer, Person, rollup, score
from app.rsvp import save_answer
from app.schedule import instant

router = APIRouter(tags=["meetups"])

Notes = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]
MoodId = Annotated[str, StringConstraints(min_length=1, max_length=32)]
MAX_RSVP_MOODS = 20
MAX_PLAYERS = 30  # the most a "what if this many came?" can ask about
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
    # The player range with the expansions people are bringing (which can widen it).
    min_players: int | None
    max_players: int
    expansions: list[GameBrief]
    rollup: RollupRead  # what the people coming think of it
    score: float  # higher suits tonight better; only the order means anything
    reasons: list[ReasonRead]  # why, best first


class MeetupGames(BaseModel):
    confirmed: int  # the headcount: members going plus their guests
    players: int  # the count the games were fitted to: the headcount, unless asked for another
    guests: int  # of those, guests
    maybes: int  # members who said maybe, plus their guests
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
    await achievements.earn(session, Achievement.SCHEDULE_MEETUP, user.id)
    await session.commit()
    return await _read(session, meetup, group, me, user)


@router.get("/meetups/{meetup_id}")
async def read_meetup(meetup_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> MeetupRead:
    meetup, group, me = await _meetup(session, meetup_id, user)
    await fill_unlogged(session, group)
    return await _read(session, meetup, group, me, user)


@router.patch("/meetups/{meetup_id}")
async def update_meetup(
    meetup_id: uuid.UUID,
    changes: MeetupUpdate,
    user: CurrentUser,
    session: SessionDep,
    mailer: MailerDep,
    discord: DiscordDep,
) -> MeetupRead:
    """Move, change or cancel one date. A scheduled date changed this way is left alone
    by later schedule changes (notes alone don't count). Members who haven't said no are
    emailed about a new day, time or place, or the date being cancelled or back on."""
    meetup, group, me = await _meetup(session, meetup_id, user)
    require_runner(me)
    before = notify.DateSnapshot.of(meetup)
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
    notify.mark_moved(meetup, before)
    await session.commit()
    result = await _read(session, meetup, group, me, user)
    people = await notify.might_come(session, group, meetup)
    after = notify.DateSnapshot.of(meetup)
    await notify.date_changed(session, mailer, meetup.id, group, user, before, after, people)
    await refresh_cards(session, discord, meetup.id)
    return result


@router.delete("/meetups/{meetup_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_meetup(
    meetup_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
    mailer: MailerDep,
    discord: DiscordDep,
) -> None:
    """Remove a date added on its own. Scheduled dates are cancelled instead, so the
    schedule doesn't bring them back. Told like a cancellation."""
    meetup, group, me = await _meetup(session, meetup_id, user)
    require_runner(me)
    if meetup.slot_date is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This date comes from the schedule; cancel it instead."
        )
    before = notify.DateSnapshot.of(meetup)
    people = await notify.might_come(session, group, meetup)
    cards = await posted_cards(session, meetup.id)
    await session.delete(meetup)
    await session.commit()
    await notify.date_changed(session, mailer, meetup_id, group, user, before, None, people)
    await remove_cards(discord, cards)


@router.put("/meetups/{meetup_id}/rsvp")
async def rsvp(
    meetup_id: uuid.UUID,
    body: RsvpIn,
    user: CurrentUser,
    session: SessionDep,
    discord: DiscordDep,
) -> MeetupRead:
    meetup, group, me = await _meetup(session, meetup_id, user)
    await save_answer(session, meetup, group, user, body.response, body.guests, body.moods)
    result = await _read(session, meetup, group, me, user)
    await refresh_cards(session, discord, meetup.id)
    return result


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
    meetup_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
    players: Annotated[int | None, Query(ge=1, le=MAX_PLAYERS)] = None,
) -> MeetupGames:
    """Games the people coming could play, best suited first: owned and marked "will bring"
    by someone who said yes, and playable by everyone going (guests included), all together
    or (if the group is willing to split) at a table that leaves nobody on their own.

    Only yes answers count toward the ranking. Maybes only give a lift to games that would
    still fit if they came too. Length is shown, never used to filter or rank.

    `players` asks "what if this many came?": the games are fitted and ranked for that many
    instead of the headcount, and the maybes are taken to be part of it. It's only for the
    person asking; nothing is saved.
    """
    meetup, group, _me = await _meetup(session, meetup_id, user)
    await fill_unlogged(session, group)
    played_lately = await recently_played(session, meetup)
    answered = await session.execute(
        select(User, MeetupRsvp.response, MeetupRsvp.guests)
        .join(MeetupRsvp, MeetupRsvp.user_id == User.id)
        .where(
            MeetupRsvp.meetup_id == meetup.id,
            MeetupRsvp.response.in_([RsvpResponse.YES, RsvpResponse.MAYBE]),
        )
        .order_by(func.lower(User.display_name))
    )
    coming: list[User] = []
    guests = maybes = 0
    for person, response, brings in answered:
        if response == RsvpResponse.YES:
            coming.append(person)
            guests += brings
        else:
            maybes += 1 + brings
    confirmed = len(coming) + guests
    # Asking for the headcount itself is the same as not asking.
    trying = players if players is not None and players != confirmed else None
    table_count = confirmed if trying is None else trying
    coming_ids = [u.id for u in coming]
    people = {u.id: PersonRead.of(u) for u in coming}
    scope = [Person(u.id, u.display_name) for u in coming]

    # Everything the people coming will bring: base games, and expansions for them.
    owned = await session.execute(
        select(UserGame.user_id, Game)
        .join(Game, Game.id == UserGame.game_id)
        .where(
            UserGame.user_id.in_(coming_ids),
            UserGame.ownership == Ownership.OWNED,
            UserGame.will_bring.is_(True),
        )
        .order_by(Game.name)
    )
    bases: dict[int, Game] = {}
    expansion_games: dict[int, Game] = {}
    bringers: dict[int, list[PersonRead]] = defaultdict(list)
    for owner_id, game in owned:
        if game.is_expansion:
            expansion_games[game.id] = game
        else:
            bases[game.id] = game
            bringers[game.id].append(people[owner_id])
    expansions: dict[int, list[Game]] = defaultdict(list)
    for expansion in expansion_games.values():
        for base_id in expansion.base_game_ids:
            if base_id in bases:
                expansions[base_id].append(expansion)

    answers: dict[int, dict[uuid.UUID, Answer]] = defaultdict(dict)
    if bases:
        rows = await session.scalars(
            select(UserGame).where(
                UserGame.user_id.in_(coming_ids), UserGame.game_id.in_(list(bases))
            )
        )
        names = {p.id: p for p in scope}
        for row in rows:
            answers[row.game_id][row.user_id] = Answer.of(row, names[row.user_id])
    tonight = list(
        await session.scalars(
            select(MeetupRsvpMood.mood_id)
            .join(
                MeetupRsvp,
                (MeetupRsvp.meetup_id == MeetupRsvpMood.meetup_id)
                & (MeetupRsvp.user_id == MeetupRsvpMood.user_id),
            )
            .where(MeetupRsvp.meetup_id == meetup.id, MeetupRsvp.response == RsvpResponse.YES)
        )
    )
    mood_names = {
        mood_id: name for mood_id, name in await session.execute(select(Mood.id, Mood.name))
    }

    fitting: list[FittingGame] = []
    unknown = 0
    for game_id, game in bases.items():
        extras = expansions[game_id]
        low, high = player_range(game, extras)
        if high is None:
            unknown += 1
            continue
        fit = table_fit(low, high, table_count, group.willing_to_split)
        if fit is None:
            continue
        # A split game is played by a table of some of them; judge it at the biggest one.
        table = table_count if fit == "together" else _biggest_table(low, high, table_count)
        roll = rollup(game, scope, answers[game_id], table)
        fits_maybes = (
            trying is None
            and maybes > 0
            and table_fit(low, high, confirmed + maybes, group.willing_to_split) is not None
        )
        points, reasons = score(
            roll,
            players=table,
            fits_maybes=fits_maybes,
            tonight_moods=tonight,
            mood_names=mood_names,
            recently_played=game_id in played_lately,
        )
        fitting.append(
            FittingGame(
                game=GameSummary.from_game(game),
                bringers=bringers[game_id],
                fit=fit,
                min_players=low,
                max_players=high,
                expansions=[_brief(e) for e in extras],
                rollup=RollupRead.of(roll, people),
                score=round(points, 2),
                reasons=[ReasonRead.of(r) for r in reasons],
            )
        )
    fitting.sort(key=lambda g: (-g.score, g.fit != "together", g.game.name.lower()))
    return MeetupGames(
        confirmed=confirmed,
        players=table_count,
        guests=guests,
        maybes=maybes,
        willing_to_split=group.willing_to_split,
        games=fitting,
        unknown_player_count=unknown,
    )


def _biggest_table(low: int | None, high: int, players: int) -> int:
    """The biggest table a split game can seat that still leaves two for another table."""
    return max(t for t in range(2, players - 1) if (low or 1) <= t <= high)


def _brief(game: Game) -> GameBrief:
    return GameBrief(
        id=game.id,
        name=game.name,
        year_published=game.year_published,
        thumbnail_url=game.thumbnail_url,
        is_expansion=game.is_expansion,
    )
