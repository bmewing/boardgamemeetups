"""Who is friends with whom, who has blocked whom, and who may see whose games."""

import uuid
from enum import StrEnum

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CollectionVisibility, Friendship, FriendshipStatus, User, UserBlock


class Relation(StrEnum):
    """How another user stands with you."""

    SELF = "self"
    NONE = "none"
    FRIENDS = "friends"
    INCOMING = "incoming"  # they asked you
    OUTGOING = "outgoing"  # you asked them


async def friendship_between(
    session: AsyncSession, a: uuid.UUID, b: uuid.UUID
) -> Friendship | None:
    low, high = Friendship.pair(a, b)
    return await session.get(Friendship, (low, high))


async def relation(session: AsyncSession, me: uuid.UUID, other: uuid.UUID) -> Relation:
    if me == other:
        return Relation.SELF
    friendship = await friendship_between(session, me, other)
    if friendship is None:
        return Relation.NONE
    if friendship.status == FriendshipStatus.ACCEPTED:
        return Relation.FRIENDS
    return Relation.OUTGOING if friendship.requester_id == me else Relation.INCOMING


async def blocked_either_way(session: AsyncSession, a: uuid.UUID, b: uuid.UUID) -> bool:
    found = await session.scalar(
        select(UserBlock.blocker_id).where(
            or_(
                (UserBlock.blocker_id == a) & (UserBlock.blocked_id == b),
                (UserBlock.blocker_id == b) & (UserBlock.blocked_id == a),
            )
        )
    )
    return found is not None


async def has_blocked(session: AsyncSession, blocker: uuid.UUID, blocked: uuid.UUID) -> bool:
    return await session.get(UserBlock, (blocker, blocked)) is not None


def can_see_games(owner: User, viewer_relation: Relation) -> bool:
    """Whether someone may see `owner`'s game list. Notes are never shared either way.

    Groups (Phase 7) share members' games with each other whatever this says.
    """
    if viewer_relation == Relation.SELF:
        return True
    match owner.collection_visibility:
        case CollectionVisibility.PUBLIC:
            return True
        case CollectionVisibility.FRIENDS:
            return viewer_relation == Relation.FRIENDS
        case CollectionVisibility.PRIVATE:
            return False
