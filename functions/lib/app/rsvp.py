"""Saving someone's answer to a date, from the app or from a Discord button."""

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app import achievements
from app.models import (
    Group,
    Meetup,
    MeetupRsvp,
    MeetupRsvpMood,
    MeetupStatus,
    Mood,
    RsvpResponse,
    User,
)
from app.pieces import Achievement
from app.plays import drop_bringing

# Rules out every other mood.
NO_PREFERENCE = "no_preference"


async def save_answer(
    session: AsyncSession,
    meetup: Meetup,
    group: Group,
    user: User,
    response: RsvpResponse,
    guests: int,
    moods: list[str],
) -> None:
    """Replace the user's whole answer and commit. Guests and moods only go with a yes or
    maybe; a no clears them, and anything other than yes stops them bringing games."""
    if meetup.status == MeetupStatus.CANCELLED:
        raise HTTPException(status.HTTP_409_CONFLICT, "This date has been cancelled.")
    might_come = response != RsvpResponse.NO
    guests = guests if might_come else 0
    moods = list(dict.fromkeys(moods)) if might_come else []
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
        .values(meetup_id=meetup.id, user_id=user.id, response=response, guests=guests)
        .on_conflict_do_update(
            index_elements=[MeetupRsvp.meetup_id, MeetupRsvp.user_id],
            set_={"response": response, "guests": guests, "responded_at": func.now()},
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
    if response == RsvpResponse.YES:
        await achievements.earn(session, Achievement.RSVP_YES, user.id)
    else:
        await drop_bringing(session, meetup.id, user.id)
    await session.commit()


async def change_response(
    session: AsyncSession, meetup: Meetup, group: Group, user: User, response: RsvpResponse
) -> None:
    """Change only yes, maybe or no (a Discord button), keeping the guests and moods already
    given. Guests are trimmed to the group's limit if it has come down since."""
    guests = await session.scalar(
        select(MeetupRsvp.guests).where(
            MeetupRsvp.meetup_id == meetup.id, MeetupRsvp.user_id == user.id
        )
    )
    moods = await session.scalars(
        select(MeetupRsvpMood.mood_id).where(
            MeetupRsvpMood.meetup_id == meetup.id, MeetupRsvpMood.user_id == user.id
        )
    )
    await save_answer(
        session,
        meetup,
        group,
        user,
        response,
        min(guests or 0, group.plus_one_limit),
        list(moods),
    )


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
