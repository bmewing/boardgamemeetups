"""Find-a-time polls: an organizer offers days and hours, members tap the half hours they're
free, everyone sees the best times, and an organizer turns one into a date."""

import uuid
from datetime import date, datetime
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import AfterValidator, BaseModel, Field, StringConstraints, model_validator
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app import achievements, notify
from app.api.friends import PersonRead
from app.api.me import TimeZone
from app.auth import CurrentUser
from app.db import SessionDep
from app.email import MailerDep
from app.groups import membership, require_runner
from app.models import (
    Group,
    GroupMember,
    GroupRole,
    Meetup,
    MeetupStatus,
    PollStatus,
    TimePoll,
    TimePollResponse,
    User,
)
from app.pieces import Achievement
from app.polls import (
    MINUTES_IN_DAY,
    SLOT_MINUTES,
    best_stretches,
    clock,
    day_slots,
    slot_end,
    slot_start,
    sorted_slots,
)
from app.schedule import instant

router = APIRouter(tags=["polls"])

MAX_DAYS = 62
POLL_NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, "Poll not found")
POLL_CLOSED = HTTPException(status.HTTP_409_CONFLICT, "This poll is closed.")


def _half_hour(value: str) -> int:
    """A "HH:MM" on the hour or half hour as a minute of the day. "24:00" is allowed, as the
    midnight that ends a day."""
    try:
        hours, minutes = (int(part) for part in value.split(":"))
    except ValueError as error:
        raise ValueError("Use a time like 19:30") from error
    minute = hours * 60 + minutes
    if not 0 <= minute <= MINUTES_IN_DAY or minute % SLOT_MINUTES:
        raise ValueError("Times must be on the hour or half hour")
    return minute


Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
HalfHour = Annotated[str, AfterValidator(lambda v: clock(_half_hour(v)))]
PollDuration = Annotated[int, Field(ge=30, le=720, multiple_of=SLOT_MINUTES)]


class PollCreate(BaseModel):
    """`end_time` of "00:00" means midnight at the end of the day."""

    title: Title
    dates: Annotated[list[date], Field(min_length=1)]
    start_time: HalfHour
    end_time: HalfHour
    time_zone: TimeZone
    duration_minutes: PollDuration = 120

    @model_validator(mode="after")
    def check_window(self) -> "PollCreate":
        if len(set(self.dates)) > MAX_DAYS:
            raise ValueError(f"Offer at most {MAX_DAYS} days")
        if self.end_minute <= self.start_minute:
            raise ValueError("The window must end after it starts")
        return self

    @property
    def start_minute(self) -> int:
        return _half_hour(self.start_time)

    @property
    def end_minute(self) -> int:
        return _half_hour(self.end_time) or MINUTES_IN_DAY


class AnswerIn(BaseModel):
    """The whole answer: every slot you're free, replacing any earlier one."""

    slots: list[str] = Field(max_length=MAX_DAYS * 48)


class ScheduleIn(BaseModel):
    start: str


class DayRead(BaseModel):
    date: date
    slots: list[str]


class RespondentRead(BaseModel):
    person: PersonRead
    slots: list[str]


class BestTime(BaseModel):
    start: str
    end: str  # "HH:MM", or "24:00" if it ends at midnight
    starts_at: datetime
    available: list[PersonRead]
    missing: list[PersonRead]  # answered, but can't make all of it


class PollRead(BaseModel):
    id: uuid.UUID
    group_id: uuid.UUID
    group_name: str
    title: str
    status: PollStatus
    time_zone: str
    slot_minutes: Literal[30] = 30
    duration_minutes: int
    days: list[DayRead]
    can_manage: bool
    my_slots: list[str] | None  # null: you haven't answered
    respondents: list[RespondentRead]  # only people still in the group
    waiting: list[PersonRead]  # members who haven't answered
    best: list[BestTime]
    meetup_id: uuid.UUID | None
    created_by: PersonRead | None


class PollBrief(BaseModel):
    id: uuid.UUID
    title: str
    status: PollStatus
    first_date: date
    last_date: date
    answered: int
    members: int
    i_answered: bool
    meetup_id: uuid.UUID | None


class PollsRead(BaseModel):
    polls: list[PollBrief]


def _days(poll: TimePoll) -> list[list[str]]:
    return [
        day_slots(date.fromisoformat(day), poll.start_minute, poll.end_minute) for day in poll.dates
    ]


def _offered(poll: TimePoll) -> set[str]:
    return {slot for day in _days(poll) for slot in day}


async def _load(
    session: AsyncSession, poll_id: uuid.UUID, user: User
) -> tuple[TimePoll, Group, GroupMember]:
    """The poll and your place in its group. Polls of groups you aren't in don't exist."""
    poll = await session.get(TimePoll, poll_id)
    if poll is None:
        raise POLL_NOT_FOUND
    try:
        group, me = await membership(session, poll.group_id, user)
    except HTTPException as error:
        raise POLL_NOT_FOUND from error
    return poll, group, me


async def _organizer(
    session: AsyncSession, poll_id: uuid.UUID, user: User
) -> tuple[TimePoll, Group, GroupMember]:
    poll, group, me = await _load(session, poll_id, user)
    require_runner(me)
    return poll, group, me


async def _read(
    session: AsyncSession, poll: TimePoll, group: Group, me: GroupMember, user: User
) -> PollRead:
    people = {
        member.id: member
        for member in await session.scalars(
            select(User)
            .join(GroupMember, GroupMember.user_id == User.id)
            .where(GroupMember.group_id == group.id)
            .order_by(User.display_name, User.id)
        )
    }
    days = _days(poll)
    offered = _offered(poll)
    rows = await session.scalars(
        select(TimePollResponse).where(TimePollResponse.poll_id == poll.id)
    )
    # People who answered and then left the group no longer count.
    answers = {r.user_id: sorted_slots([s for s in r.slots if s in offered]) for r in rows}
    answers = {uid: slots for uid, slots in answers.items() if uid in people}

    best = []
    for stretch in best_stretches(days, answers, poll.duration_minutes):
        day, at = slot_start(stretch.start)
        best.append(
            BestTime(
                start=stretch.start,
                end=slot_end(stretch.slots[-1], SLOT_MINUTES),
                starts_at=instant(day, at, poll.time_zone),
                available=[PersonRead.of(people[uid]) for uid in stretch.available],
                missing=[PersonRead.of(people[uid]) for uid in stretch.missing],
            )
        )
    creator = people.get(poll.created_by_id) if poll.created_by_id else None
    return PollRead(
        id=poll.id,
        group_id=group.id,
        group_name=group.name,
        title=poll.title,
        status=poll.status,
        time_zone=poll.time_zone,
        duration_minutes=poll.duration_minutes,
        days=[
            DayRead(date=date.fromisoformat(d), slots=s)
            for d, s in zip(poll.dates, days, strict=True)
        ],
        can_manage=me.role in (GroupRole.OWNER, GroupRole.ADMIN),
        my_slots=answers.get(user.id),
        respondents=[
            RespondentRead(person=PersonRead.of(people[uid]), slots=slots)
            for uid, slots in answers.items()
        ],
        waiting=[PersonRead.of(p) for uid, p in people.items() if uid not in answers],
        best=best,
        meetup_id=poll.meetup_id,
        created_by=PersonRead.of(creator) if creator else None,
    )


@router.get("/groups/{group_id}/polls")
async def list_polls(group_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> PollsRead:
    group, _ = await membership(session, group_id, user)
    members = set(
        await session.scalars(select(GroupMember.user_id).where(GroupMember.group_id == group.id))
    )
    polls = list(
        await session.scalars(
            select(TimePoll)
            .where(TimePoll.group_id == group.id)
            .order_by(TimePoll.created_at.desc(), TimePoll.id)
        )
    )
    answered: dict[uuid.UUID, set[uuid.UUID]] = {poll.id: set() for poll in polls}
    rows = await session.execute(
        select(TimePollResponse.poll_id, TimePollResponse.user_id).where(
            TimePollResponse.poll_id.in_(answered)
        )
    )
    for poll_id, user_id in rows:
        if user_id in members:
            answered[poll_id].add(user_id)
    return PollsRead(
        polls=[
            PollBrief(
                id=poll.id,
                title=poll.title,
                status=poll.status,
                first_date=date.fromisoformat(poll.dates[0]),
                last_date=date.fromisoformat(poll.dates[-1]),
                answered=len(answered[poll.id]),
                members=len(members),
                i_answered=user.id in answered[poll.id],
                meetup_id=poll.meetup_id,
            )
            for poll in polls
        ]
    )


@router.post("/groups/{group_id}/polls", status_code=status.HTTP_201_CREATED)
async def create_poll(
    group_id: uuid.UUID,
    body: PollCreate,
    user: CurrentUser,
    session: SessionDep,
    mailer: MailerDep,
) -> PollRead:
    group, me = await membership(session, group_id, user)
    require_runner(me)
    poll = TimePoll(
        group_id=group.id,
        created_by_id=user.id,
        title=body.title,
        dates=[d.isoformat() for d in sorted(set(body.dates))],
        start_minute=body.start_minute,
        end_minute=body.end_minute,
        time_zone=body.time_zone,
        duration_minutes=body.duration_minutes,
        status=PollStatus.OPEN,
    )
    session.add(poll)
    await session.commit()
    await notify.time_poll_opened(session, mailer, group, poll, user)
    return await _read(session, poll, group, me, user)


@router.get("/polls/{poll_id}")
async def read_poll(poll_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> PollRead:
    poll, group, me = await _load(session, poll_id, user)
    return await _read(session, poll, group, me, user)


@router.put("/polls/{poll_id}/answer")
async def answer_poll(
    poll_id: uuid.UUID, body: AnswerIn, user: CurrentUser, session: SessionDep
) -> PollRead:
    poll, group, me = await _load(session, poll_id, user)
    if poll.status != PollStatus.OPEN:
        raise POLL_CLOSED
    offered = _offered(poll)
    for slot in body.slots:
        if slot not in offered:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, f"{slot} isn't one of this poll's times."
            )
    slots = sorted_slots(body.slots)
    await session.execute(
        insert(TimePollResponse)
        .values(poll_id=poll.id, user_id=user.id, slots=slots)
        .on_conflict_do_update(
            index_elements=["poll_id", "user_id"],
            set_={"slots": slots, "updated_at": func.now()},
        )
    )
    await session.commit()
    return await _read(session, poll, group, me, user)


@router.post("/polls/{poll_id}/close")
async def close_poll(poll_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> PollRead:
    poll, group, me = await _organizer(session, poll_id, user)
    poll.status = PollStatus.CLOSED
    await session.commit()
    return await _read(session, poll, group, me, user)


@router.post("/polls/{poll_id}/reopen")
async def reopen_poll(poll_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> PollRead:
    poll, group, me = await _organizer(session, poll_id, user)
    poll.status = PollStatus.OPEN
    await session.commit()
    return await _read(session, poll, group, me, user)


@router.post("/polls/{poll_id}/remind", status_code=status.HTTP_204_NO_CONTENT)
async def remind_poll(
    poll_id: uuid.UUID, user: CurrentUser, session: SessionDep, mailer: MailerDep
) -> Response:
    """Email the members who haven't answered yet."""
    poll, group, _ = await _organizer(session, poll_id, user)
    if poll.status != PollStatus.OPEN:
        raise POLL_CLOSED
    await notify.time_poll_reminder(session, mailer, group, poll, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/polls/{poll_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_poll(poll_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> Response:
    poll, _, _ = await _organizer(session, poll_id, user)
    await session.delete(poll)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/polls/{poll_id}/schedule")
async def schedule_poll(
    poll_id: uuid.UUID,
    body: ScheduleIn,
    user: CurrentUser,
    session: SessionDep,
    mailer: MailerDep,
) -> PollRead:
    """Make a date at one of the poll's times, for the poll's length, and close the poll."""
    poll, group, me = await _organizer(session, poll_id, user)
    if poll.status != PollStatus.OPEN:
        raise POLL_CLOSED
    if body.start not in _offered(poll):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"{body.start} isn't one of this poll's times."
        )
    day, at = slot_start(body.start)
    starts_at = instant(day, at, poll.time_zone)
    # Dates are kept as wall-clock times in the group's zone, which may not be the poll's.
    there = starts_at.astimezone(ZoneInfo(group.time_zone))
    meetup = Meetup(
        group_id=group.id,
        local_date=there.date(),
        local_time=there.time(),
        starts_at=starts_at,
        duration_minutes=poll.duration_minutes,
        location=group.location,
        status=MeetupStatus.SCHEDULED,
    )
    session.add(meetup)
    await session.flush()
    poll.meetup_id = meetup.id
    poll.status = PollStatus.CLOSED
    await achievements.earn(session, Achievement.SCHEDULE_MEETUP, user.id)
    await session.commit()
    await notify.time_poll_scheduled(session, mailer, group, meetup, user)
    return await _read(session, poll, group, me, user)
