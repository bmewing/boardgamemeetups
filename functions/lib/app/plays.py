"""What was played at a group's dates: play counts, the one-week fill-in, and what was
played lately (which the recommendations avoid)."""

import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app import achievements
from app.models import (
    BringAssignment,
    Game,
    Group,
    GroupMember,
    Meetup,
    MeetupAttendee,
    MeetupNomination,
    MeetupRsvp,
    MeetupStatus,
    Play,
    PlayPlayer,
    RsvpResponse,
    Source,
    UserGame,
)
from app.pieces import Achievement

COOP_MECHANIC = "Cooperative Game"
# A date with a locked pick that nobody logs is taken as played as picked after this long.
ASSUME_AFTER = timedelta(days=7)
# Games played at this many of the group's latest logged dates count as played lately.
RECENT_DATES = 2


@dataclass(frozen=True)
class PlayLine:
    """One game in a date's log."""

    game_id: int
    coop: bool
    coop_won: bool | None = None  # co-op only; null when not recorded
    players: Sequence[uuid.UUID] = ()
    winners: Sequence[uuid.UUID] = field(default_factory=tuple)  # competitive only


def coop_by_default(game: Game) -> bool:
    """BGG's mechanics say whether a game is co-op; whoever logs a play can change it."""
    return COOP_MECHANIC in (game.mechanics or [])


async def going(session: AsyncSession, meetup_id: uuid.UUID) -> tuple[list[uuid.UUID], int]:
    """The members who said yes to a date, and how many guests they're bringing."""
    rows = await session.execute(
        select(MeetupRsvp.user_id, MeetupRsvp.guests).where(
            MeetupRsvp.meetup_id == meetup_id, MeetupRsvp.response == RsvpResponse.YES
        )
    )
    members, guests = [], 0
    for user_id, brings in rows:
        members.append(user_id)
        guests += brings
    return members, guests


async def _count(session: AsyncSession, pairs: Iterable[tuple[uuid.UUID, int]], step: int) -> None:
    """Add `step` (1 or -1) to each person's play count for a game, adding a row for a game
    they hadn't recorded. Counts never go below zero."""
    for user_id, game_id in pairs:
        if step > 0:
            await session.execute(
                insert(UserGame)
                .values(user_id=user_id, game_id=game_id, plays=step, source=Source.MANUAL)
                .on_conflict_do_update(
                    index_elements=[UserGame.user_id, UserGame.game_id],
                    set_={"plays": UserGame.plays + step, "updated_at": func.now()},
                )
            )
        else:
            await session.execute(
                update(UserGame)
                .where(UserGame.user_id == user_id, UserGame.game_id == game_id)
                .values(plays=func.greatest(UserGame.plays + step, 0))
            )


async def played_pairs(session: AsyncSession, meetup_id: uuid.UUID) -> list[tuple[uuid.UUID, int]]:
    rows = await session.execute(
        select(PlayPlayer.user_id, Play.game_id)
        .join(Play, Play.id == PlayPlayer.play_id)
        .where(Play.meetup_id == meetup_id)
    )
    return [(user_id, game_id) for user_id, game_id in rows]


async def save_log(
    session: AsyncSession,
    meetup: Meetup,
    attendees: Sequence[uuid.UUID],
    plays: Sequence[PlayLine],
    *,
    assumed: bool = False,
) -> None:
    """Replace a date's log. Play counts follow: the old log's plays come off, the new
    one's go on."""
    await _count(session, await played_pairs(session, meetup.id), -1)
    await session.execute(delete(Play).where(Play.meetup_id == meetup.id))
    await session.execute(delete(MeetupAttendee).where(MeetupAttendee.meetup_id == meetup.id))
    session.add_all(
        MeetupAttendee(meetup_id=meetup.id, user_id=u) for u in dict.fromkeys(attendees)
    )
    new_pairs: list[tuple[uuid.UUID, int]] = []
    for position, line in enumerate(plays):
        play = Play(
            meetup_id=meetup.id,
            game_id=line.game_id,
            position=position,
            coop=line.coop,
            coop_won=line.coop_won,
        )
        session.add(play)
        await session.flush()
        for user_id in dict.fromkeys(line.players):
            won = not line.coop and user_id in line.winners
            session.add(PlayPlayer(play_id=play.id, user_id=user_id, won=won))
            new_pairs.append((user_id, line.game_id))
    await session.flush()
    await _count(session, new_pairs, 1)
    await _earn_from_log(session, attendees, plays)
    meetup.logged_at = datetime.now(UTC)
    meetup.log_assumed = assumed


async def _earn_from_log(
    session: AsyncSession, attendees: Sequence[uuid.UUID], plays: Sequence[PlayLine]
) -> None:
    """Whoever won, or has now come to enough nights, earns it, and so does whoever brought
    them to the app. Won counts the same way the log does: a player marked as a winner, or
    everyone at a co-op table that won."""
    winners = [
        u
        for line in plays
        for u in line.players
        if (line.coop_won if line.coop else u in line.winners)
    ]
    coop_winners = [u for line in plays if line.coop and line.coop_won for u in line.players]
    await achievements.earn(session, Achievement.WIN_GAME, *winners)
    await achievements.earn(session, Achievement.COOP_WIN, *coop_winners)
    await achievements.earn_counted(session, achievements.Counter.NIGHTS, attendees)
    await achievements.earn_recruits_attending(session, attendees)


async def fill_unlogged(session: AsyncSession, group: Group) -> None:
    """A week after a date with a locked pick, if nobody has logged it, take it as played as
    picked by the members who said yes, with no result. Safe to run on every page view."""
    due = list(
        await session.scalars(
            select(Meetup).where(
                Meetup.group_id == group.id,
                Meetup.status == MeetupStatus.SCHEDULED,
                Meetup.picks_locked_at.is_not(None),
                Meetup.logged_at.is_(None),
                Meetup.starts_at < datetime.now(UTC) - ASSUME_AFTER,
            )
        )
    )
    if not due:
        return
    for meetup in due:
        members = set(
            await session.scalars(
                select(GroupMember.user_id).where(GroupMember.group_id == group.id)
            )
        )
        yes = [u for u in (await going(session, meetup.id))[0] if u in members]
        picked = await session.scalars(
            select(Game)
            .join(MeetupNomination, MeetupNomination.game_id == Game.id)
            .where(MeetupNomination.meetup_id == meetup.id, MeetupNomination.picked.is_(True))
            .order_by(Game.name)
        )
        plays = [PlayLine(g.id, coop_by_default(g), players=yes) for g in picked]
        await save_log(session, meetup, yes, plays, assumed=True)
    await session.commit()


async def recently_played(session: AsyncSession, meetup: Meetup) -> set[int]:
    """Games played at the group's latest logged dates before this one."""
    latest = (
        select(Meetup.id)
        .where(
            Meetup.group_id == meetup.group_id,
            Meetup.logged_at.is_not(None),
            Meetup.starts_at < meetup.starts_at,
        )
        .order_by(Meetup.starts_at.desc())
        .limit(RECENT_DATES)
    )
    return set(await session.scalars(select(Play.game_id).where(Play.meetup_id.in_(latest))))


async def drop_bringing(session: AsyncSession, meetup_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Someone no longer going stops bringing games; those games then need a new bringer."""
    await session.execute(
        delete(BringAssignment).where(
            BringAssignment.meetup_id == meetup_id, BringAssignment.user_id == user_id
        )
    )
