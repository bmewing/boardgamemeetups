"""Things people do around the app, and the pieces and colors they unlock.

Everyone starts with a few pieces and colors; the rest each wait on an achievement. Some
achievements unlock nothing and are just for the record. An achievement is recorded the
moment someone earns it (`earn`, called before the caller commits) and stays earned, even
if what earned it is later undone. Counted ones ("come to 5 game nights") are checked
against a running count (`earn_counted`). The frontend words and groups them in
pieces/shapes.ts.
"""

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Integer, Select, func, literal, select, union_all, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Friendship,
    FriendshipStatus,
    GroupMember,
    GroupRole,
    MeetupAttendee,
    User,
    UserAchievement,
    UserGame,
)
from app.pieces import Achievement, Piece, PieceColor

# Every piece and color not listed here is free from the start.
PIECE_UNLOCKED_BY: dict[Piece, Achievement] = {
    Piece.THIMBLE: Achievement.ADD_GAME,
    Piece.ROCKET: Achievement.IMPORT_COLLECTION,
    Piece.DUCK: Achievement.CAN_TEACH,  # rubber-duck explaining: teaching
    Piece.DOG: Achievement.MAKE_FRIEND,
    Piece.BATTLESHIP: Achievement.RECRUIT,  # growing the fleet
    Piece.ROOK: Achievement.START_GROUP,
    Piece.TOP_HAT: Achievement.SCHEDULE_MEETUP,
    Piece.WHEELBARROW: Achievement.GROUP_OF_4,  # enough hands to haul the games
    Piece.CAT: Achievement.JOIN_GROUP,
    Piece.RACE_CAR: Achievement.RSVP_YES,
    Piece.KNIGHT: Achievement.NOMINATE_PICKED,
    Piece.BOOT: Achievement.ATTEND_1,
    Piece.IRON: Achievement.ATTEND_5,  # iron will
    Piece.CROWN: Achievement.WIN_GAME,
}
COLOR_UNLOCKED_BY: dict[PieceColor, Achievement] = {
    PieceColor.PLUM: Achievement.RATE_GAMES,
    PieceColor.SKY: Achievement.STAY_IN_LOOP,
    PieceColor.LEAF: Achievement.FRIENDS_5,
    PieceColor.ORANGE: Achievement.RECRUIT_ATTENDS,
    PieceColor.SLATE: Achievement.JOINED_BY_INVITE,
}


class Counter(StrEnum):
    """Running counts that counted achievements are measured against."""

    RATED = "rated"  # games on your list you've rated
    FRIENDS = "friends"
    NIGHTS = "nights"  # game nights the play log says you came to
    GROUP_SIZE = "group_size"  # members of the biggest group you own or help run


# Counted achievements: what they count, and how many it takes.
GOALS: dict[Achievement, tuple[Counter, int]] = {
    Achievement.RATE_GAMES: (Counter.RATED, 10),
    Achievement.FRIENDS_5: (Counter.FRIENDS, 5),
    Achievement.GROUP_OF_4: (Counter.GROUP_SIZE, 4),
    Achievement.ATTEND_1: (Counter.NIGHTS, 1),
    Achievement.ATTEND_5: (Counter.NIGHTS, 5),
    Achievement.ATTEND_20: (Counter.NIGHTS, 20),
}


def _per_user(counter: Counter) -> Select[uuid.UUID, int]:
    """(user id, count) for everyone the counter has anything for."""
    match counter:
        case Counter.RATED:
            return (
                select(UserGame.user_id, func.count())
                .where(UserGame.rating.is_not(None))
                .group_by(UserGame.user_id)
            )
        case Counter.FRIENDS:
            accepted = Friendship.status == FriendshipStatus.ACCEPTED
            sides = union_all(
                select(Friendship.user_low_id.label("user_id")).where(accepted),
                select(Friendship.user_high_id.label("user_id")).where(accepted),
            ).subquery()
            return select(sides.c.user_id, func.count()).group_by(sides.c.user_id)
        case Counter.NIGHTS:
            return select(MeetupAttendee.user_id, func.count()).group_by(MeetupAttendee.user_id)
        case Counter.GROUP_SIZE:
            sizes = (
                select(GroupMember.group_id, func.count().label("size"))
                .group_by(GroupMember.group_id)
                .subquery()
            )
            return (
                select(GroupMember.user_id, func.max(sizes.c.size, type_=Integer))
                .join(sizes, sizes.c.group_id == GroupMember.group_id)
                .where(GroupMember.role.in_([GroupRole.OWNER, GroupRole.ADMIN]))
                .group_by(GroupMember.user_id)
            )


async def counts(
    session: AsyncSession, counter: Counter, user_ids: Iterable[uuid.UUID]
) -> dict[uuid.UUID, int]:
    people = list(dict.fromkeys(user_ids))
    if not people:
        return {}
    query = _per_user(counter).subquery()
    user_id, count = query.c
    rows = await session.execute(select(user_id, count).where(user_id.in_(people)))
    return {u: n for u, n in rows}


async def earn(session: AsyncSession, achievement: Achievement, *user_ids: uuid.UUID) -> None:
    """Record that these people have earned it. Already earned is fine. Doesn't commit."""
    people = list(dict.fromkeys(user_ids))
    if not people:
        return
    await session.execute(
        insert(UserAchievement)
        .values([{"user_id": u, "achievement": achievement} for u in people])
        .on_conflict_do_nothing()
    )


async def earn_counted(
    session: AsyncSession, counter: Counter, user_ids: Iterable[uuid.UUID]
) -> None:
    """Earn every achievement measured by this counter that these people have now reached.
    Counts what's been flushed so far."""
    have = await counts(session, counter, user_ids)
    for achievement, (measures, goal) in GOALS.items():
        if measures == counter:
            await earn(session, achievement, *(u for u, n in have.items() if n >= goal))


async def earn_recruit(
    session: AsyncSession, inviter_id: uuid.UUID | None, newcomer: User, invited_at: datetime
) -> None:
    """Someone accepted an invite. They get the welcome; if their account is newer than the
    invite, the inviter brought them to the app and gets the credit (once per newcomer)."""
    await earn(session, Achievement.JOINED_BY_INVITE, newcomer.id)
    if inviter_id is None or inviter_id == newcomer.id or newcomer.referred_by_id is not None:
        return
    if newcomer.created_at >= invited_at:
        newcomer.referred_by_id = inviter_id
        await earn(session, Achievement.RECRUIT, inviter_id)


async def earn_recruits_attending(session: AsyncSession, attendees: Iterable[uuid.UUID]) -> None:
    """Whoever brought any of these people to the app now has a recruit at the table."""
    people = list(dict.fromkeys(attendees))
    if not people:
        return
    referrers = await session.scalars(
        select(User.referred_by_id).where(User.id.in_(people), User.referred_by_id.is_not(None))
    )
    await earn(session, Achievement.RECRUIT_ATTENDS, *(r for r in referrers if r is not None))


@dataclass(frozen=True)
class Earned:
    achievement: Achievement
    earned_at: datetime | None  # None: not yet
    new: bool  # earned since they last looked
    progress: int | None  # counted ones only: how far along
    goal: int | None


async def achievements_of(session: AsyncSession, user_id: uuid.UUID) -> list[Earned]:
    """Every achievement, in order, and where this person stands on it."""
    rows = await session.execute(
        select(
            UserAchievement.achievement, UserAchievement.earned_at, UserAchievement.seen_at
        ).where(UserAchievement.user_id == user_id)
    )
    earned = {a: (at, seen is None) for a, at, seen in rows}
    needed = {counter for counter, _ in GOALS.values()}
    progress = {c: (await counts(session, c, [user_id])).get(user_id, 0) for c in needed}
    result = []
    for achievement in Achievement:
        at, new = earned.get(achievement, (None, False))
        counter, goal = GOALS.get(achievement, (None, None))
        result.append(
            Earned(
                achievement=achievement,
                earned_at=at,
                new=new,
                progress=min(progress[counter], goal) if counter and goal else None,
                goal=goal,
            )
        )
    return result


async def has_earned(
    session: AsyncSession, user_id: uuid.UUID, achievement: Achievement | None
) -> bool:
    if achievement is None:
        return True
    found = await session.scalar(
        select(literal(True)).where(
            UserAchievement.user_id == user_id, UserAchievement.achievement == achievement
        )
    )
    return bool(found)


async def mark_seen(session: AsyncSession, user_id: uuid.UUID) -> None:
    """They've seen what they earned, so nothing is new any more. Doesn't commit."""
    await session.execute(
        update(UserAchievement)
        .where(UserAchievement.user_id == user_id, UserAchievement.seen_at.is_(None))
        .values(seen_at=func.now())
    )
