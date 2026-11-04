"""A group's recurring schedule, and keeping its next dates in step with it.

Dates are worked out as local dates in the group's time zone, then paired with the local
start time, so a 7 pm meetup stays 7 pm on both sides of a daylight-saving change.
"""

import uuid
from datetime import date, datetime, time, timedelta
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from dateutil import rrule
from pydantic import BaseModel, Field, TypeAdapter
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Group, Meetup, MeetupStatus

# How many scheduled dates ahead exist as meetups.
DATES_AHEAD = 8

Weekday = Annotated[int, Field(ge=0, le=6, description="0 is Monday, 6 is Sunday")]
WEEKDAYS = (rrule.MO, rrule.TU, rrule.WE, rrule.TH, rrule.FR, rrule.SA, rrule.SU)


class EveryNWeeks(BaseModel):
    kind: Literal["weekly"] = "weekly"
    every_weeks: Annotated[int, Field(ge=1, le=12)] = 1
    weekday: Weekday
    # Counting starts here, so "every 2 weeks" knows which weeks are on.
    starts_on: date


class NthWeekdayOfMonth(BaseModel):
    kind: Literal["monthly_weekday"] = "monthly_weekday"
    # 1st to 4th, or -1 for the last one in the month.
    nth: Literal[1, 2, 3, 4, -1]
    weekday: Weekday
    starts_on: date


class DayOfMonth(BaseModel):
    """Day X of each month. Months without that day (say the 31st) are skipped."""

    kind: Literal["monthly_day"] = "monthly_day"
    day: Annotated[int, Field(ge=1, le=31)]
    starts_on: date


Schedule = Annotated[EveryNWeeks | NthWeekdayOfMonth | DayOfMonth, Field(discriminator="kind")]
SCHEDULE = TypeAdapter[EveryNWeeks | NthWeekdayOfMonth | DayOfMonth](Schedule)


def _rule(schedule: EveryNWeeks | NthWeekdayOfMonth | DayOfMonth) -> rrule.rrule:
    start = datetime.combine(schedule.starts_on, time())
    match schedule:
        case EveryNWeeks():
            # Count weeks from the first matching weekday, so "every 2 weeks from Sunday the
            # 1st, on Thursdays" starts on the 5th rather than skipping to the 12th.
            first = start + timedelta(days=(schedule.weekday - start.weekday()) % 7)
            return rrule.rrule(
                rrule.WEEKLY,
                dtstart=first,
                interval=schedule.every_weeks,
                byweekday=WEEKDAYS[schedule.weekday],
            )
        case NthWeekdayOfMonth():
            return rrule.rrule(
                rrule.MONTHLY, dtstart=start, byweekday=WEEKDAYS[schedule.weekday](schedule.nth)
            )
        case DayOfMonth():
            return rrule.rrule(rrule.MONTHLY, dtstart=start, bymonthday=schedule.day)


def next_dates(
    schedule: EveryNWeeks | NthWeekdayOfMonth | DayOfMonth, on_or_after: date, count: int
) -> list[date]:
    after = datetime.combine(on_or_after, time())
    return [moment.date() for moment in _rule(schedule).xafter(after, count=count, inc=True)]


def instant(local_date: date, local_time: time, time_zone: str) -> datetime:
    return datetime.combine(local_date, local_time, tzinfo=ZoneInfo(time_zone))


def today_in(time_zone: str) -> date:
    return datetime.now(ZoneInfo(time_zone)).date()


def _defaults(group: Group, day: date) -> dict[str, object]:
    return {
        "local_date": day,
        "local_time": group.start_time,
        "starts_at": instant(day, group.start_time, group.time_zone),
        "duration_minutes": group.duration_minutes,
        "location": group.location,
    }


async def sync_meetups(session: AsyncSession, group: Group, today: date | None = None) -> None:
    """Keep the next scheduled dates in step with the group's schedule and defaults.

    Untouched future dates that still fit take the group's current time and place; ones
    that no longer fit go; missing ones are added. Dates edited by hand (including cancelled
    ones), one-off dates and past dates are left alone. Safe to run on every page view.
    """
    today = today or today_in(group.time_zone)
    wanted = (
        next_dates(SCHEDULE.validate_python(group.schedule), today, DATES_AHEAD)
        if group.schedule
        else []
    )
    wanted_set = set(wanted)

    rows = await session.scalars(
        select(Meetup).where(
            Meetup.group_id == group.id,
            Meetup.slot_date.is_not(None),
            Meetup.slot_date >= today,
        )
    )
    taken: set[date] = set()
    stale: list[uuid.UUID] = []
    for row in rows:
        assert row.slot_date is not None
        if row.is_overridden or row.status == MeetupStatus.CANCELLED:
            taken.add(row.slot_date)
        elif row.slot_date in wanted_set:
            taken.add(row.slot_date)
            for field, value in _defaults(group, row.slot_date).items():
                if getattr(row, field) != value:
                    setattr(row, field, value)
        else:
            stale.append(row.id)
    if stale:
        await session.execute(delete(Meetup).where(Meetup.id.in_(stale)))

    missing = [day for day in wanted if day not in taken]
    if missing:
        # Two page views at once may both add a date; the second insert does nothing.
        await session.execute(
            insert(Meetup)
            .values(
                [
                    {
                        "id": uuid.uuid4(),
                        "group_id": group.id,
                        "slot_date": day,
                        "status": MeetupStatus.SCHEDULED,
                        **_defaults(group, day),
                    }
                    for day in missing
                ]
            )
            .on_conflict_do_nothing(
                index_elements=[Meetup.group_id, Meetup.slot_date],
                index_where=Meetup.slot_date.is_not(None),
            )
        )
    await session.commit()


async def move_to_time_zone(session: AsyncSession, group: Group, today: date) -> None:
    """After the group's time zone changes, keep future dates at the same local time."""
    rows = await session.scalars(
        select(Meetup).where(Meetup.group_id == group.id, Meetup.local_date >= today)
    )
    for row in rows:
        row.starts_at = instant(row.local_date, row.local_time, group.time_zone)
