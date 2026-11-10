"""Who gets told about what, and what the email says.

Each function here is called once the change it's about has been saved, and never fails
the request that caused it: an error is logged and the session rolled back to where the
change was committed. Nobody is emailed about something they did themselves.
"""

import functools
import logging
import uuid
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.bga import bga_games_for, place_of
from app.config import get_settings
from app.email import Email, EmailKind, Mailer, Message, to_address, to_user, wants
from app.friends import has_blocked
from app.models import (
    BringAssignment,
    Game,
    Group,
    GroupMember,
    Meetup,
    MeetupNomination,
    MeetupRsvp,
    MeetupStatus,
    RsvpResponse,
    User,
)
from app.schedule import today_in

logger = logging.getLogger(__name__)

# Reminders go out once a date is this close.
REMINDER_AHEAD = timedelta(hours=24)


def quietly[**P](
    send: Callable[P, Awaitable[None]],
) -> Callable[P, Awaitable[None]]:
    """Log a failure instead of raising it. The first argument must be the session."""

    @functools.wraps(send)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> None:
        try:
            await send(*args, **kwargs)
        except Exception:
            logger.exception("Couldn't send the %s emails", send.__name__)
            session = args[0]
            assert isinstance(session, AsyncSession)
            await session.rollback()

    return wrapper


async def _deliver(session: AsyncSession, mailer: Mailer, emails: Sequence[Email]) -> bool:
    # Building the emails may have given someone their first unsubscribe token.
    await session.commit()
    return await mailer.send(emails)


def _link(path: str) -> str:
    return f"{get_settings().app_url}{path}"


def clock(at: time) -> str:
    hour = at.hour % 12 or 12
    return f"{hour}:{at.minute:02d} {'am' if at.hour < 12 else 'pm'}"


def day(on: date) -> str:
    return f"{on:%A}, {on:%B} {on.day}"


def when(on: date, at: time, group: Group, reader: User) -> str:
    """ "Thursday, November 6 at 7:00 pm", naming the group's time zone when the reader is
    in another one."""
    text = f"{day(on)} at {clock(at)}"
    if reader.time_zone != group.time_zone:
        text += f" ({group.time_zone.replace('_', ' ')} time)"
    return text


def _names(names: Sequence[str]) -> str:
    if len(names) <= 2:
        return " and ".join(names)
    return ", ".join(names[:-1]) + f" and {names[-1]}"


@dataclass(frozen=True)
class DateSnapshot:
    """What people need to know about a date, to tell what changed."""

    local_date: date
    local_time: time
    location: str | None
    status: MeetupStatus

    @classmethod
    def of(cls, meetup: Meetup) -> "DateSnapshot":
        return cls(meetup.local_date, meetup.local_time, place_of(meetup), meetup.status)

    def when(self, group: Group, reader: User) -> str:
        return when(self.local_date, self.local_time, group, reader)


async def upcoming_dates(session: AsyncSession, group: Group) -> dict[uuid.UUID, DateSnapshot]:
    """The group's upcoming dates that are on, to compare before and after a change."""
    rows = await session.scalars(
        select(Meetup).where(
            Meetup.group_id == group.id,
            Meetup.local_date >= today_in(group.time_zone),
            Meetup.status == MeetupStatus.SCHEDULED,
        )
    )
    return {row.id: DateSnapshot.of(row) for row in rows}


async def _members(
    session: AsyncSession, group_id: uuid.UUID, meetup_id: uuid.UUID | None = None
) -> list[tuple[User, RsvpResponse | None]]:
    """The group's members, with their answer for a date when one is given."""
    if meetup_id is None:
        users = await session.scalars(
            select(User)
            .join(GroupMember, GroupMember.user_id == User.id)
            .where(GroupMember.group_id == group_id)
        )
        return [(user, None) for user in users]
    rows = await session.execute(
        select(User, MeetupRsvp.response)
        .join(GroupMember, GroupMember.user_id == User.id)
        .outerjoin(
            MeetupRsvp, (MeetupRsvp.user_id == User.id) & (MeetupRsvp.meetup_id == meetup_id)
        )
        .where(GroupMember.group_id == group_id)
    )
    return [(user, response) for user, response in rows]


@quietly
async def friend_request(
    session: AsyncSession, mailer: Mailer, sender: User, recipient: User
) -> None:
    if not wants(recipient, EmailKind.FRIEND_REQUEST):
        return
    message = Message(
        subject=f"{sender.display_name} wants to be friends",
        paragraphs=[
            f"{sender.display_name} asked to be your friend on Board Game Group. Friends can "
            "see each other's games and add each other to groups."
        ],
        link=("See the request", _link("/friends")),
    )
    await _deliver(session, mailer, [to_user(recipient, EmailKind.FRIEND_REQUEST, message)])


@quietly
async def group_invite(
    session: AsyncSession,
    mailer: Mailer,
    group: Group,
    inviter: User,
    address: str,
    invitee: User | None,
) -> None:
    """An invite to a group, for someone on the app or for an address nobody uses yet."""
    subject = f"{inviter.display_name} invited you to {group.name}"
    about = (
        f"{inviter.display_name} invited you to join {group.name} on Board Game Group, where "
        "the group plans its game nights: who's coming, which games to play and who brings them."
    )
    if invitee is None:
        email = to_address(
            address,
            Message(
                subject=subject,
                paragraphs=[
                    about,
                    f"Sign up with this email address ({address}) and the invite will be "
                    "waiting for you.",
                ],
                link=("Open Board Game Group", _link("/")),
            ),
        )
    else:
        if await has_blocked(session, invitee.id, inviter.id):
            return
        if not wants(invitee, EmailKind.GROUP_INVITE):
            return
        email = to_user(
            invitee,
            EmailKind.GROUP_INVITE,
            Message(
                subject=subject,
                paragraphs=[about, "Joining shares your games (never your notes) with the group."],
                link=("See the invite", _link("/groups")),
            ),
        )
    await _deliver(session, mailer, [email])


async def might_come(session: AsyncSession, group: Group, meetup: Meetup) -> list[User]:
    """Members who haven't said no to a date."""
    members = await _members(session, group.id, meetup.id)
    return [member for member, response in members if response != RsvpResponse.NO]


@quietly
async def date_changed(
    session: AsyncSession,
    mailer: Mailer,
    meetup_id: uuid.UUID,
    group: Group,
    changer: User,
    before: DateSnapshot,
    after: DateSnapshot | None,
    people: list[User],
) -> None:
    """A date moved, changed place, or was cancelled, removed (`after` is None) or put back
    on: told to `people`, the members who hadn't said no. Notes and length don't count."""
    if after == before:
        return
    today = today_in(group.time_zone)
    if before.local_date < today and (after is None or after.local_date < today):
        return
    cancelled = after is None or after.status == MeetupStatus.CANCELLED
    if cancelled and before.status == MeetupStatus.CANCELLED:
        return
    restored = before.status == MeetupStatus.CANCELLED

    emails = []
    for member in people:
        if member.id == changer.id or not wants(member, EmailKind.DATE_CHANGED):
            continue
        items: list[str] = []
        paragraphs: list[str] = []
        link = ("Open the date", _link(f"/meetups/{meetup_id}"))
        if after is None or cancelled:
            subject = f"Cancelled: {group.name} on {day(before.local_date)}"
            paragraphs.append(
                f"{changer.display_name} cancelled {group.name}'s date on "
                f"{before.when(group, member)}."
            )
            if after is None:
                link = ("Open the group", _link(f"/groups/{group.id}"))
        elif restored:
            subject = f"Back on: {group.name} on {day(after.local_date)}"
            paragraphs.append(
                f"{changer.display_name} put {group.name}'s date on "
                f"{after.when(group, member)} back on."
            )
        else:
            subject = f"Changed: {group.name} on {day(after.local_date)}"
            paragraphs.append(f"{changer.display_name} changed {group.name}'s date:")
            now = after.when(group, member)
            if (before.local_date, before.local_time) != (after.local_date, after.local_time):
                items.append(f"Now {now} (was {before.when(group, member)})")
            else:
                items.append(f"Still {now}")
            if before.location != after.location:
                items.append(
                    f"Now at {after.location or 'a place to be decided'}"
                    f" (was at {before.location or 'no place set'})"
                )
            elif after.location:
                items.append(f"Still at {after.location}")
        message = Message(subject=subject, paragraphs=paragraphs, items=items, link=link)
        emails.append(to_user(member, EmailKind.DATE_CHANGED, message))
    await _deliver(session, mailer, emails)


@quietly
async def schedule_changed(
    session: AsyncSession,
    mailer: Mailer,
    group: Group,
    changer: User,
    before: dict[uuid.UUID, DateSnapshot],
) -> None:
    """One summary of the upcoming dates a schedule change added, dropped or moved."""
    after = await upcoming_dates(session, group)
    added = [after[i] for i in after.keys() - before.keys()]
    dropped = [before[i] for i in before.keys() - after.keys()]
    moved = [(before[i], after[i]) for i in before.keys() & after.keys() if before[i] != after[i]]
    if not (added or dropped or moved):
        return

    emails = []
    for member, _ in await _members(session, group.id):
        if member.id == changer.id or not wants(member, EmailKind.DATE_CHANGED):
            continue
        lines: list[tuple[date, time, str]] = []
        for snap in added:
            lines.append((snap.local_date, snap.local_time, f"New: {snap.when(group, member)}"))
        for snap in dropped:
            lines.append((snap.local_date, snap.local_time, f"Dropped: {snap.when(group, member)}"))
        for old, new in moved:
            text = f"Moved: {new.when(group, member)}"
            if new.location != old.location:
                text += f" at {new.location or 'a place to be decided'}"
            lines.append(
                (new.local_date, new.local_time, f"{text} (was {_was(old, new, group, member)})")
            )
        lines.sort()
        message = Message(
            subject=f"{group.name}'s dates have changed",
            paragraphs=[f"{changer.display_name} changed how {group.name} meets. Coming up:"],
            items=[text for _, _, text in lines],
            link=("Open the group", _link(f"/groups/{group.id}")),
        )
        emails.append(to_user(member, EmailKind.DATE_CHANGED, message))
    await _deliver(session, mailer, emails)


def _was(old: DateSnapshot, new: DateSnapshot, group: Group, reader: User) -> str:
    parts = []
    if (old.local_date, old.local_time) != (new.local_date, new.local_time):
        parts.append(old.when(group, reader))
    if old.location != new.location:
        parts.append(f"at {old.location or 'no place set'}")
    return " ".join(parts)


@quietly
async def pick_locked(
    session: AsyncSession, mailer: Mailer, meetup: Meetup, group: Group, locker: User
) -> None:
    """The games picked for a date, to members who said yes or maybe. Anyone bringing one
    hears it here too. For an online date, each game comes with its BGA link instead."""
    games = list(
        await session.scalars(
            select(Game)
            .join(MeetupNomination, MeetupNomination.game_id == Game.id)
            .where(MeetupNomination.meetup_id == meetup.id, MeetupNomination.picked.is_(True))
            .order_by(Game.name)
        )
    )
    if not games:
        return
    bringers = {
        game_id: user_id
        for game_id, user_id in await session.execute(
            select(BringAssignment.game_id, BringAssignment.user_id).where(
                BringAssignment.meetup_id == meetup.id
            )
        )
    }
    on_bga = await bga_games_for(session, [g.id for g in games]) if meetup.is_online else {}
    members = await _members(session, group.id, meetup.id)
    names = {member.id: member.display_name for member, _ in members}

    emails = []
    for member, response in members:
        if member.id == locker.id or response not in (RsvpResponse.YES, RsvpResponse.MAYBE):
            continue
        mine = [game.name for game in games if bringers.get(game.id) == member.id]
        if not (
            wants(member, EmailKind.PICK_LOCKED) or (mine and wants(member, EmailKind.BRINGING))
        ):
            continue
        items = []
        for game in games:
            bringer = bringers.get(game.id)
            if meetup.is_online:
                bga = on_bga.get(game.id)
                items.append(f"{game.name}: {bga.game_url}" if bga else game.name)
            elif bringer == member.id:
                items.append(f"{game.name}: you're bringing it")
            elif bringer in names:
                items.append(f"{game.name}: {names[bringer]} is bringing it")
            else:
                items.append(f"{game.name}: nobody has said they'll bring it yet")
        after = []
        if meetup.is_online:
            after.append(f"It's on {place_of(meetup)}.")
        if mine:
            after.append(
                f"You're bringing {_names(mine)}. If you can't, say so on the date's page so "
                "someone else can."
            )
        message = Message(
            subject=f"Picked for {group.name}: {_names([game.name for game in games])}",
            paragraphs=[
                f"{locker.display_name} locked in the games for "
                f"{when(meetup.local_date, meetup.local_time, group, member)}:"
            ],
            items=items,
            link=("Open the date", _link(f"/meetups/{meetup.id}")),
            after=after,
        )
        kind = EmailKind.PICK_LOCKED if wants(member, EmailKind.PICK_LOCKED) else EmailKind.BRINGING
        emails.append(to_user(member, kind, message))
    await _deliver(session, mailer, emails)


@quietly
async def bringing(
    session: AsyncSession,
    mailer: Mailer,
    meetup: Meetup,
    group: Group,
    game: Game,
    bringer: User,
    assigner: User,
) -> None:
    """Someone was handed a game to bring. Claiming one yourself sends nothing."""
    if bringer.id == assigner.id or not wants(bringer, EmailKind.BRINGING):
        return
    message = Message(
        subject=f"You're bringing {game.name} to {group.name}",
        paragraphs=[
            f"{assigner.display_name} asked you to bring {game.name} to {group.name} on "
            f"{when(meetup.local_date, meetup.local_time, group, bringer)}."
        ],
        link=("Open the date", _link(f"/meetups/{meetup.id}")),
        after=["Can't bring it? Say so on the date's page so someone else can."],
    )
    await _deliver(session, mailer, [to_user(bringer, EmailKind.BRINGING, message)])


async def send_due_reminders(
    session: AsyncSession, mailer: Mailer, now: datetime | None = None
) -> int:
    """Remind members who haven't answered, or said maybe, about dates starting within a
    day. Each date is claimed before its emails go out, so two runs at once can't both send
    them, and released again if sending fails. Returns how many dates were reminded."""
    now = now or datetime.now(UTC)
    claimed = list(
        await session.scalars(
            update(Meetup)
            .where(
                Meetup.status == MeetupStatus.SCHEDULED,
                Meetup.reminder_sent_at.is_(None),
                Meetup.starts_at > now,
                Meetup.starts_at <= now + REMINDER_AHEAD,
            )
            .values(reminder_sent_at=now)
            .returning(Meetup.id)
        )
    )
    await session.commit()
    sent = 0
    for meetup_id in claimed:
        try:
            ok = await _remind(session, mailer, meetup_id)
        except Exception:
            logger.exception("Couldn't send the reminders for meetup %s", meetup_id)
            await session.rollback()
            ok = False
        if ok:
            sent += 1
        else:
            await session.execute(
                update(Meetup).where(Meetup.id == meetup_id).values(reminder_sent_at=None)
            )
            await session.commit()
    return sent


async def _remind(session: AsyncSession, mailer: Mailer, meetup_id: uuid.UUID) -> bool:
    row = (
        await session.execute(
            select(Meetup, Group)
            .join(Group, Group.id == Meetup.group_id)
            .where(Meetup.id == meetup_id)
        )
    ).first()
    if row is None:
        return True
    meetup, group = row
    members = await _members(session, group.id, meetup.id)
    yes = sum(1 for _, response in members if response == RsvpResponse.YES)
    emails = []
    for member, response in members:
        if response not in (None, RsvpResponse.MAYBE):
            continue
        if not wants(member, EmailKind.RSVP_REMINDER):
            continue
        at = when(meetup.local_date, meetup.local_time, group, member)
        first = (
            f"{group.name} meets {at}, and you said maybe. Can you say yes or no now, so "
            "everyone knows who's coming?"
            if response == RsvpResponse.MAYBE
            else f"{group.name} meets {at}, and you haven't said whether you're coming."
        )
        details = [f"{yes} {'person has' if yes == 1 else 'people have'} said yes so far."]
        if place := place_of(meetup):
            details.insert(0, f"At {place}.")
        message = Message(
            subject=f"Coming to {group.name} on {day(meetup.local_date)}?",
            paragraphs=[first, " ".join(details)],
            link=("Answer", _link(f"/meetups/{meetup.id}")),
        )
        emails.append(to_user(member, EmailKind.RSVP_REMINDER, message))
    return await _deliver(session, mailer, emails)


def mark_moved(meetup: Meetup, before: DateSnapshot) -> None:
    """A date that moves gets its reminder again at the new time."""
    if (before.local_date, before.local_time, before.status) != (
        meetup.local_date,
        meetup.local_time,
        meetup.status,
    ):
        meetup.reminder_sent_at = None
