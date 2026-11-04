"""Meetups as calendar events, for the one-date download and the calendar feed."""

import re
from datetime import timedelta

from app import ics
from app.config import get_settings
from app.models import Group, Meetup, MeetupStatus, RsvpResponse

ANSWERS = {
    RsvpResponse.YES: "You're going.",
    RsvpResponse.MAYBE: "You said maybe.",
    RsvpResponse.NO: "You said you can't go.",
}
NO_ANSWER = "You haven't said whether you're coming."


def meetup_url(meetup: Meetup) -> str | None:
    app_url = get_settings().app_url
    return f"{app_url}/meetups/{meetup.id}" if app_url else None


def meetup_event(
    meetup: Meetup, group: Group, *, response: RsvpResponse | None = None, feed: bool = False
) -> ics.Event:
    """The date as an event. In a feed it also says what you've answered, so a glance at
    your calendar shows the dates you still need to answer."""
    cancelled = meetup.status == MeetupStatus.CANCELLED
    url = meetup_url(meetup)
    answer = (ANSWERS[response] if response else NO_ANSWER) if feed else None
    notes = [part for part in (answer, meetup.notes, url) if part]
    return ics.Event(
        uid=f"{meetup.id}@boardgamemeetups",
        starts_at=meetup.starts_at,
        duration=timedelta(minutes=meetup.duration_minutes),
        summary=f"Cancelled: {group.name}" if cancelled else group.name,
        updated_at=meetup.updated_at,
        # Seconds since it was made: goes up whenever the date changes.
        sequence=max(0, int((meetup.updated_at - meetup.created_at).total_seconds())),
        location=meetup.location,
        description="\n\n".join(notes) or None,
        url=url,
        cancelled=cancelled,
    )


def file_name(meetup: Meetup, group: Group) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", group.name.lower()).strip("-") or "meetup"
    return f"{slug}-{meetup.local_date.isoformat()}.ics"
