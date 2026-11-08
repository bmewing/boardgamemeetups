"""Your calendar feed: a secret link to subscribe to from any calendar app.

The feed itself needs no sign-in, since calendar apps can't sign in; the token in the link
is the key. Only one link works at a time, and making a new one turns the old one off.
"""

import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Path, Response, status
from pydantic import BaseModel
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app import achievements, ics
from app.auth import CurrentUser
from app.calendar import meetup_event
from app.db import SessionDep
from app.models import (
    CalendarFeed,
    Group,
    GroupMember,
    Meetup,
    MeetupRsvp,
    RsvpResponse,
    User,
)
from app.pieces import Achievement
from app.plays import fill_unlogged
from app.schedule import sync_meetups

router = APIRouter(tags=["calendar"])

FEED_NAME = "Board game meetups"
# Past dates stay in the feed this long, so last week's game night doesn't vanish.
KEEP_PAST = timedelta(days=30)
FEED_GONE = HTTPException(status.HTTP_404_NOT_FOUND, "This calendar link has been turned off.")
CALENDAR_FILE: dict[int | str, dict[str, Any]] = {
    200: {"content": {"text/calendar": {"schema": {"type": "string"}}}}
}
FeedToken = Annotated[str, Path(min_length=1, max_length=64)]


class CalendarFeedRead(BaseModel):
    token: str
    created_at: datetime


async def _live_feed(session: AsyncSession, user: User) -> CalendarFeed | None:
    feed: CalendarFeed | None = await session.scalar(
        select(CalendarFeed)
        .where(CalendarFeed.user_id == user.id, CalendarFeed.revoked_at.is_(None))
        .order_by(CalendarFeed.created_at.desc())
        .limit(1)
    )
    return feed


async def _turn_off(session: AsyncSession, user: User) -> None:
    await session.execute(
        update(CalendarFeed)
        .where(CalendarFeed.user_id == user.id, CalendarFeed.revoked_at.is_(None))
        .values(revoked_at=func.now())
    )


@router.get("/me/calendar-feed")
async def read_calendar_feed(user: CurrentUser, session: SessionDep) -> CalendarFeedRead | None:
    """Your feed's link, or null if you haven't made one (or turned it off)."""
    feed = await _live_feed(session, user)
    return CalendarFeedRead(token=feed.token, created_at=feed.created_at) if feed else None


@router.post("/me/calendar-feed", status_code=status.HTTP_201_CREATED)
async def make_calendar_feed(user: CurrentUser, session: SessionDep) -> CalendarFeedRead:
    """A new link. Any link you had stops working, so calendars subscribed to it go quiet."""
    await _turn_off(session, user)
    feed = CalendarFeed(token=secrets.token_urlsafe(24), user_id=user.id)
    session.add(feed)
    await achievements.earn(session, Achievement.STAY_IN_LOOP, user.id)
    await session.commit()
    await session.refresh(feed)
    return CalendarFeedRead(token=feed.token, created_at=feed.created_at)


@router.delete("/me/calendar-feed", status_code=status.HTTP_204_NO_CONTENT)
async def turn_off_calendar_feed(user: CurrentUser, session: SessionDep) -> None:
    await _turn_off(session, user)
    await session.commit()


@router.get("/calendar/{token}.ics", response_class=Response, responses=CALENDAR_FILE)
async def calendar_feed(token: FeedToken, session: SessionDep) -> Response:
    """Every date in your groups that you might go to: ones you said yes or maybe to, and
    ones you haven't answered. Cancelled dates stay in, marked cancelled, so calendar apps
    take them off. No sign-in: the token is the key."""
    owner = await session.scalar(
        select(User)
        .join(CalendarFeed, CalendarFeed.user_id == User.id)
        .where(CalendarFeed.token == token, CalendarFeed.revoked_at.is_(None))
    )
    if owner is None:
        raise FEED_GONE

    groups = list(
        await session.scalars(
            select(Group)
            .join(GroupMember, GroupMember.group_id == Group.id)
            .where(GroupMember.user_id == owner.id)
        )
    )
    # Otherwise the dates ahead are only topped up when someone opens the group's page.
    for group in groups:
        await sync_meetups(session, group)
        await fill_unlogged(session, group)

    rows = await session.execute(
        select(Meetup, Group, MeetupRsvp.response)
        .join(Group, Group.id == Meetup.group_id)
        .outerjoin(
            MeetupRsvp,
            and_(MeetupRsvp.meetup_id == Meetup.id, MeetupRsvp.user_id == owner.id),
        )
        .where(
            Meetup.group_id.in_([g.id for g in groups]),
            Meetup.starts_at >= datetime.now(UTC) - KEEP_PAST,
            or_(MeetupRsvp.response.is_(None), MeetupRsvp.response != RsvpResponse.NO),
        )
        .order_by(Meetup.starts_at)
    )
    events = [
        meetup_event(meetup, group, response=response, feed=True)
        for meetup, group, response in rows
    ]
    return Response(
        ics.calendar(events, name=FEED_NAME, feed=True),
        media_type="text/calendar",
        headers={"Content-Disposition": 'inline; filename="board-game-meetups.ics"'},
    )
