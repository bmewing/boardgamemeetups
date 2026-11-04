"""Who can do what in a group, handing groups on, and which games fit a headcount."""

import uuid
from typing import Literal

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Group, GroupMember, GroupRole, User

GROUP_NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, "Group not found")
RUNS_GROUP = (GroupRole.OWNER, GroupRole.ADMIN)
TableFit = Literal["together", "split"]


async def membership(
    session: AsyncSession, group_id: uuid.UUID, user: User
) -> tuple[Group, GroupMember]:
    """The group and your place in it. Groups you aren't in look like they don't exist."""
    row = (
        await session.execute(
            select(Group, GroupMember)
            .join(GroupMember, GroupMember.group_id == Group.id)
            .where(Group.id == group_id, GroupMember.user_id == user.id)
        )
    ).first()
    if row is None:
        raise GROUP_NOT_FOUND
    group, member = row
    return group, member


def require_runner(member: GroupMember) -> None:
    """Owners and admins run the group: its details, schedule, dates and invites."""
    if member.role not in RUNS_GROUP:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the owner and admins can do that.")


def require_owner(member: GroupMember) -> None:
    if member.role != GroupRole.OWNER:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the group's owner can do that.")


async def hand_over_groups(session: AsyncSession, user: User) -> None:
    """Before an account is deleted: pass each group it owns to the longest-serving admin,
    else the longest-serving member, and delete groups nobody else is in."""
    owned = await session.scalars(
        select(GroupMember).where(
            GroupMember.user_id == user.id, GroupMember.role == GroupRole.OWNER
        )
    )
    for ownership in list(owned):
        group_id = ownership.group_id
        await session.delete(ownership)
        await session.flush()
        heir = await session.scalar(
            select(GroupMember)
            .where(GroupMember.group_id == group_id)
            .order_by(
                (GroupMember.role == GroupRole.ADMIN).desc(),
                GroupMember.joined_at,
                GroupMember.user_id,
            )
            .limit(1)
        )
        if heir is None:
            await session.execute(delete(Group).where(Group.id == group_id))
        else:
            heir.role = GroupRole.OWNER
            await session.flush()


def seats(min_players: int, max_players: int, players: int) -> bool:
    return min_players <= players <= max_players


def table_fit(
    min_players: int | None, max_players: int | None, confirmed: int, willing_to_split: bool
) -> TableFit | None:
    """How a game fits the people coming: "together" (one table of everyone), "split" (a
    table of some of them, leaving at least 2 for another table), or None if it doesn't.

    With 5 coming and willing to split, a game fits at tables of 2, 3 or 5, never 4: that
    would leave someone on their own. Games with no known player count never fit.
    """
    if max_players is None or confirmed < 1:
        return None
    low = min_players or 1
    if seats(low, max_players, confirmed):
        return "together"
    if willing_to_split and any(seats(low, max_players, t) for t in range(2, confirmed - 1)):
        return "split"
    return None
