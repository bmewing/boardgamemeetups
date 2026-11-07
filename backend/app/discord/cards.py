"""Meetup cards: the bot's post about a date, with Going / Maybe / Can't buttons.

A card goes up in each channel connected to the group a week before the date (the hourly
run), or when someone asks for it with /bggroup next. It's edited whenever an answer
changes, here or in the app, and when the date moves or is cancelled.

Nothing here fails the request that called it: Discord being down only leaves a card stale.
"""

import logging
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.discord.client import Discord, Edit, Message
from app.models import (
    DiscordCard,
    DiscordChannel,
    Group,
    Meetup,
    MeetupRsvp,
    MeetupStatus,
    RsvpResponse,
    User,
)
from app.notify import day

logger = logging.getLogger(__name__)

# Cards go up this long before a date.
ANNOUNCE_AHEAD = timedelta(days=7)
TEAL = 0x1D7874
CORAL = 0xDD7373
# Discord's limits on parts of a message.
FIELD_LIMIT = 1024
DESCRIPTION_LIMIT = 4096
NOTES_SHOWN = 500

BUTTON_ROW, BUTTON = 1, 2
GREEN, GREY, RED, LINK = 3, 2, 4, 5
CHOICES = (
    (RsvpResponse.YES, "Going", GREEN),
    (RsvpResponse.MAYBE, "Maybe", GREY),
    (RsvpResponse.NO, "Can't go", RED),
)
HEADINGS = {RsvpResponse.YES: "Going", RsvpResponse.MAYBE: "Maybe", RsvpResponse.NO: "Can't go"}


def rsvp_id(meetup_id: uuid.UUID, response: RsvpResponse) -> str:
    """A button's custom ID, which Discord hands back when it's clicked."""
    return f"rsvp:{meetup_id}:{response.value}"


def clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _people(answers: Sequence[tuple[User, MeetupRsvp]]) -> str:
    names = [
        f"{user.display_name} +{rsvp.guests}" if rsvp.guests else user.display_name
        for user, rsvp in answers
    ]
    return clip(", ".join(names), FIELD_LIMIT) if names else "Nobody yet"


def render(
    meetup: Meetup,
    group: Group,
    answers: Sequence[tuple[User, MeetupRsvp]],
    now: datetime | None = None,
) -> Message:
    """The card as a Discord message. Its time is a Discord timestamp, which every reader
    sees in their own time zone. Cancelled and finished dates lose their buttons."""
    now = now or datetime.now(UTC)
    cancelled = meetup.status == MeetupStatus.CANCELLED
    over = meetup.starts_at + timedelta(minutes=meetup.duration_minutes) <= now
    starts = int(meetup.starts_at.timestamp())
    lines = [f"<t:{starts}:F> (<t:{starts}:R>)"]
    if meetup.location:
        lines.append(f"At {meetup.location}")
    if meetup.notes:
        lines.append("")
        lines.append(clip(meetup.notes, NOTES_SHOWN))
    fields = []
    for response, heading in HEADINGS.items():
        given = [(user, rsvp) for user, rsvp in answers if rsvp.response == response]
        count = sum(1 + rsvp.guests for _, rsvp in given)
        fields.append({"name": f"{heading} ({count})", "value": _people(given), "inline": True})
    title = f"{group.name}: {day(meetup.local_date)}"
    embed: Message = {
        "title": clip(f"Cancelled: {title}" if cancelled else title, 256),
        "description": clip("\n".join(lines), DESCRIPTION_LIMIT),
        "color": CORAL if cancelled else TEAL,
        "fields": fields,
        "footer": {"text": "Bring guests or pick your moods in the app."},
    }
    buttons: list[Message] = []
    if not cancelled and not over:
        buttons = [
            {"type": BUTTON, "style": style, "label": label, "custom_id": rsvp_id(meetup.id, r)}
            for r, label, style in CHOICES
        ]
    app_url = get_settings().app_url
    if app_url.startswith("https://"):  # Discord only takes https links
        link = f"{app_url}/meetups/{meetup.id}"
        embed["url"] = link
        buttons.append({"type": BUTTON, "style": LINK, "label": "Open in the app", "url": link})
    return {
        "embeds": [embed],
        "components": [{"type": BUTTON_ROW, "components": buttons}] if buttons else [],
        "allowed_mentions": {"parse": []},
    }


async def card_for(session: AsyncSession, meetup_id: uuid.UUID) -> Message | None:
    row = (
        await session.execute(
            select(Meetup, Group)
            .join(Group, Group.id == Meetup.group_id)
            .where(Meetup.id == meetup_id)
        )
    ).first()
    if row is None:
        return None
    meetup, group = row
    answers = (
        await session.execute(
            select(User, MeetupRsvp)
            .join(MeetupRsvp, MeetupRsvp.user_id == User.id)
            .where(MeetupRsvp.meetup_id == meetup_id)
            .order_by(MeetupRsvp.responded_at)
        )
    ).all()
    return render(meetup, group, [(user, rsvp) for user, rsvp in answers])


async def refresh_cards(
    session: AsyncSession, discord: Discord, meetup_id: uuid.UUID, *, skip: str | None = None
) -> None:
    """Bring every card for a date up to date (but `skip`, a message being updated by
    other means). A card deleted in Discord is forgotten, so it isn't posted again."""
    if not discord.enabled:
        return
    try:
        cards = list(
            await session.scalars(
                select(DiscordCard).where(
                    DiscordCard.meetup_id == meetup_id, DiscordCard.message_id.is_not(None)
                )
            )
        )
        cards = [card for card in cards if card.message_id != skip]
        if not cards or (message := await card_for(session, meetup_id)) is None:
            return
        for card in cards:
            assert card.message_id is not None
            if await discord.edit(card.channel_id, card.message_id, message) == Edit.GONE:
                card.message_id = None
        await session.commit()
    except Exception:
        logger.exception("Couldn't update the Discord cards for meetup %s", meetup_id)
        await session.rollback()


async def posted_cards(session: AsyncSession, meetup_id: uuid.UUID) -> list[tuple[str, str]]:
    """(channel, message) for each card about a date, before it's deleted."""
    rows = await session.execute(
        select(DiscordCard.channel_id, DiscordCard.message_id).where(
            DiscordCard.meetup_id == meetup_id, DiscordCard.message_id.is_not(None)
        )
    )
    return [(channel, message) for channel, message in rows if message]


async def remove_cards(discord: Discord, cards: Sequence[tuple[str, str]]) -> None:
    for channel_id, message_id in cards:
        try:
            await discord.delete(channel_id, message_id)
        except Exception:
            logger.exception("Couldn't delete Discord card %s", message_id)


async def _claim(session: AsyncSession, meetup_id: uuid.UUID, channel_id: str) -> bool:
    claimed = await session.scalar(
        insert(DiscordCard)
        .values(meetup_id=meetup_id, channel_id=channel_id)
        .on_conflict_do_nothing()
        .returning(DiscordCard.meetup_id)
    )
    await session.commit()
    return claimed is not None


async def _post(
    session: AsyncSession, discord: Discord, meetup_id: uuid.UUID, channel_id: str
) -> str | None:
    """Post a claimed card and record it, or release the claim if that fails."""
    message = await card_for(session, meetup_id)
    message_id = await discord.post(channel_id, message) if message else None
    card = DiscordCard.meetup_id == meetup_id, DiscordCard.channel_id == channel_id
    if message_id is None:
        await session.execute(delete(DiscordCard).where(*card))
    else:
        await session.execute(update(DiscordCard).where(*card).values(message_id=message_id))
    await session.commit()
    return message_id


async def announce_due(session: AsyncSession, discord: Discord, now: datetime | None = None) -> int:
    """Post a card for each scheduled date within a week, in each channel following its
    group that doesn't have one yet. Returns how many went up."""
    if not discord.enabled:
        return 0
    now = now or datetime.now(UTC)
    due = (
        await session.execute(
            select(Meetup.id, DiscordChannel.channel_id)
            .join(DiscordChannel, DiscordChannel.group_id == Meetup.group_id)
            .outerjoin(
                DiscordCard,
                (DiscordCard.meetup_id == Meetup.id)
                & (DiscordCard.channel_id == DiscordChannel.channel_id),
            )
            .where(
                Meetup.status == MeetupStatus.SCHEDULED,
                Meetup.starts_at > now,
                Meetup.starts_at <= now + ANNOUNCE_AHEAD,
                DiscordCard.meetup_id.is_(None),
            )
            .order_by(Meetup.starts_at)
        )
    ).all()
    posted = 0
    for meetup_id, channel_id in due:
        try:
            if await _claim(session, meetup_id, channel_id) and await _post(
                session, discord, meetup_id, channel_id
            ):
                posted += 1
        except Exception:
            logger.exception("Couldn't post meetup %s to channel %s", meetup_id, channel_id)
            await session.rollback()
    return posted


async def next_date(session: AsyncSession, group_id: uuid.UUID) -> Meetup | None:
    return await session.scalar(
        select(Meetup)
        .where(
            Meetup.group_id == group_id,
            Meetup.status == MeetupStatus.SCHEDULED,
            Meetup.starts_at > func.now(),
        )
        .order_by(Meetup.starts_at)
        .limit(1)
    )


async def repost(
    session: AsyncSession, discord: Discord, meetup_id: uuid.UUID, channel_id: str
) -> bool:
    """Post a date's card in a channel now, taking down the one already there."""
    message = await card_for(session, meetup_id)
    if message is None or (message_id := await discord.post(channel_id, message)) is None:
        return False
    card = DiscordCard.meetup_id == meetup_id, DiscordCard.channel_id == channel_id
    old = await session.scalar(select(DiscordCard.message_id).where(*card))
    await session.execute(
        insert(DiscordCard)
        .values(meetup_id=meetup_id, channel_id=channel_id, message_id=message_id)
        .on_conflict_do_update(
            index_elements=[DiscordCard.meetup_id, DiscordCard.channel_id],
            set_={"message_id": message_id, "posted_at": func.now()},
        )
    )
    await session.commit()
    if old:
        await discord.delete(channel_id, old)
    return True
