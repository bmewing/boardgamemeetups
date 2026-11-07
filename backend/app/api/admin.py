"""The admin portal: site-wide numbers, and managing accounts. Admins only."""

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Path, Query, status
from pydantic import BaseModel, StringConstraints
from sqlalchemy import ColumnElement, func, or_, select

from app.auth import CurrentAdmin
from app.db import SessionDep
from app.groups import hand_over_groups
from app.models import (
    Friendship,
    FriendshipStatus,
    Game,
    Group,
    GroupMember,
    Meetup,
    MeetupStatus,
    Ownership,
    Play,
    User,
    UserGame,
)
from app.pieces import Piece, PieceColor

router = APIRouter(prefix="/admin", tags=["admin"])

UserId = Annotated[uuid.UUID, Path()]
SIGNUP_WEEKS = 12
PAGE_SIZE = 50

USER_NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
NOT_YOURSELF = HTTPException(
    status.HTTP_400_BAD_REQUEST, "You can't do that to your own account here."
)
IS_ADMIN = HTTPException(
    status.HTTP_409_CONFLICT, "They're an admin. Take away their admin role in Kinde first."
)


class WeekCount(BaseModel):
    week_start: date  # a Monday, in UTC
    count: int


class UserStats(BaseModel):
    total: int
    new_7d: int
    new_30d: int
    active_7d: int  # used the app in the last 7 days
    active_30d: int
    banned: int
    admins: int


class ActivityStats(BaseModel):
    groups: int
    meetups_upcoming: int
    meetups_past: int
    plays_logged: int
    friendships: int
    games_owned: int  # copies across everyone's collections
    catalog_games: int  # games known to the app, from BGG


class StatsRead(BaseModel):
    users: UserStats
    activity: ActivityStats
    signups_by_week: list[WeekCount]  # oldest first, the current week last


class AdminUserRead(BaseModel):
    id: uuid.UUID
    display_name: str
    email: str | None
    avatar_url: str | None
    piece: Piece | None
    piece_color: PieceColor | None
    is_admin: bool
    banned_at: datetime | None
    ban_reason: str | None
    created_at: datetime
    last_seen_at: datetime | None
    games_owned: int
    groups: int


class AdminUserPage(BaseModel):
    users: list[AdminUserRead]
    total: int  # matching the search, across all pages


class BanRequest(BaseModel):
    reason: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] = ""


async def _scalar_count(session: SessionDep, *where: ColumnElement[bool], of: type) -> int:
    return await session.scalar(select(func.count()).select_from(of).where(*where)) or 0


def week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


@router.get("/stats")
async def read_stats(admin: CurrentAdmin, session: SessionDep) -> StatsRead:
    now = datetime.now(UTC)
    week_ago, month_ago = now - timedelta(days=7), now - timedelta(days=30)

    users = (
        await session.execute(
            select(
                func.count(),
                func.count().filter(User.created_at >= week_ago),
                func.count().filter(User.created_at >= month_ago),
                func.count().filter(User.last_seen_at >= week_ago),
                func.count().filter(User.last_seen_at >= month_ago),
                func.count().filter(User.banned_at.is_not(None)),
                func.count().filter(User.is_admin),
            ).select_from(User)
        )
    ).one()

    first_week = week_start(now.date()) - timedelta(weeks=SIGNUP_WEEKS - 1)
    week = func.date_trunc("week", func.timezone("UTC", User.created_at)).label("week")
    signups = {
        row.week.date(): row.n
        for row in await session.execute(
            select(week, func.count().label("n"))
            .where(User.created_at >= datetime.combine(first_week, datetime.min.time(), UTC))
            .group_by(week)
        )
    }

    count = _scalar_count
    return StatsRead(
        users=UserStats(
            total=users[0],
            new_7d=users[1],
            new_30d=users[2],
            active_7d=users[3],
            active_30d=users[4],
            banned=users[5],
            admins=users[6],
        ),
        activity=ActivityStats(
            groups=await count(session, of=Group),
            meetups_upcoming=await count(
                session, Meetup.starts_at >= now, Meetup.status == MeetupStatus.SCHEDULED, of=Meetup
            ),
            meetups_past=await count(
                session, Meetup.starts_at < now, Meetup.status == MeetupStatus.SCHEDULED, of=Meetup
            ),
            plays_logged=await count(session, of=Play),
            friendships=await count(
                session, Friendship.status == FriendshipStatus.ACCEPTED, of=Friendship
            ),
            games_owned=await count(session, UserGame.ownership == Ownership.OWNED, of=UserGame),
            catalog_games=await count(session, of=Game),
        ),
        signups_by_week=[
            WeekCount(week_start=day, count=signups.get(day, 0))
            for day in (first_week + timedelta(weeks=n) for n in range(SIGNUP_WEEKS))
        ],
    )


GAMES_OWNED = (
    select(func.count())
    .where(UserGame.user_id == User.id, UserGame.ownership == Ownership.OWNED)
    .correlate(User)
    .scalar_subquery()
)
GROUPS = (
    select(func.count()).where(GroupMember.user_id == User.id).correlate(User).scalar_subquery()
)


def _read(user: User, games_owned: int, groups: int) -> AdminUserRead:
    return AdminUserRead(
        id=user.id,
        display_name=user.display_name,
        email=user.email,
        avatar_url=user.avatar_url,
        piece=user.piece,
        piece_color=user.piece_color,
        is_admin=user.is_admin,
        banned_at=user.banned_at,
        ban_reason=user.ban_reason,
        created_at=user.created_at,
        last_seen_at=user.last_seen_at,
        games_owned=games_owned,
        groups=groups,
    )


@router.get("/users")
async def list_users(
    admin: CurrentAdmin,
    session: SessionDep,
    q: Annotated[str, Query(max_length=320)] = "",
    show: Literal["all", "banned", "admins"] = "all",
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = PAGE_SIZE,
) -> AdminUserPage:
    """Everyone, newest first. `q` matches part of a name or email."""
    where: list[ColumnElement[bool]] = []
    if text := q.strip().lower():
        pattern = "%" + text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        where.append(
            or_(
                func.lower(User.display_name).like(pattern, escape="\\"),
                func.lower(User.email).like(pattern, escape="\\"),
            )
        )
    if show == "banned":
        where.append(User.banned_at.is_not(None))
    elif show == "admins":
        where.append(User.is_admin.is_(True))

    total = await _scalar_count(session, *where, of=User)
    rows = await session.execute(
        select(User, GAMES_OWNED, GROUPS)
        .where(*where)
        .order_by(User.created_at.desc(), User.id)
        .offset(offset)
        .limit(limit)
    )
    return AdminUserPage(users=[_read(*row) for row in rows], total=total)


async def _target(session: SessionDep, admin: User, user_id: uuid.UUID) -> User:
    """The account an admin is acting on: never their own."""
    if user_id == admin.id:
        raise NOT_YOURSELF
    user = await session.get(User, user_id)
    if user is None:
        raise USER_NOT_FOUND
    return user


async def _reread(session: SessionDep, user: User) -> AdminUserRead:
    row = (await session.execute(select(GAMES_OWNED, GROUPS).where(User.id == user.id))).one()
    return _read(user, row[0], row[1])


@router.put("/users/{user_id}/ban")
async def ban_user(
    user_id: UserId, ban: BanRequest, admin: CurrentAdmin, session: SessionDep
) -> AdminUserRead:
    """Refuse every request the account makes from now on. Its data stays, so a ban can be
    lifted; banning again just updates the reason."""
    user = await _target(session, admin, user_id)
    if user.is_admin:
        raise IS_ADMIN
    if user.banned_at is None:
        user.banned_at = datetime.now(UTC)
    user.ban_reason = ban.reason or None
    await session.commit()
    return await _reread(session, user)


@router.delete("/users/{user_id}/ban")
async def unban_user(user_id: UserId, admin: CurrentAdmin, session: SessionDep) -> AdminUserRead:
    user = await _target(session, admin, user_id)
    user.banned_at = None
    user.ban_reason = None
    await session.commit()
    return await _reread(session, user)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: UserId, admin: CurrentAdmin, session: SessionDep) -> None:
    """Delete the account and its data, as if they'd deleted it themselves. Their Kinde login
    remains, so signing in again starts a fresh, empty account; ban instead to keep them out."""
    user = await _target(session, admin, user_id)
    if user.is_admin:
        raise IS_ADMIN
    await hand_over_groups(session, user)
    await session.delete(user)
    await session.commit()
