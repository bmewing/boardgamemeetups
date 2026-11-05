"""Friends: requests by email, invite links, blocks, and seeing a person's games."""

import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Self

from fastapi import APIRouter, HTTPException, Path, Query, status
from pydantic import BaseModel, StringConstraints, model_validator
from sqlalchemy import Select, case, delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app import collection, notify
from app.api.collection import PlayerCountRead
from app.api.games import GameSummary
from app.auth import CurrentUser
from app.db import SessionDep
from app.email import MailerDep
from app.friends import (
    Relation,
    blocked_either_way,
    can_see_games,
    friendship_between,
    has_blocked,
    relation,
)
from app.models import (
    Friendship,
    FriendshipStatus,
    Game,
    InviteLink,
    Ownership,
    PlaytimeFeel,
    User,
    UserBlock,
    UserGame,
)

router = APIRouter(tags=["friends"])

INVITE_LIFETIME = timedelta(days=30)
MAX_ACTIVE_INVITE_LINKS = 20

UserId = Annotated[uuid.UUID, Path()]
Email = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=3, max_length=320, pattern=r"^\S+@\S+$"),
]

INVITE_GONE = HTTPException(
    status.HTTP_404_NOT_FOUND, "This invite link has expired or been turned off."
)
NOBODY_THERE = HTTPException(status.HTTP_404_NOT_FOUND, "No one here uses that email yet.")
PERSON_NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, "Person not found")


class PersonRead(BaseModel):
    id: uuid.UUID
    display_name: str
    avatar_url: str | None

    @classmethod
    def of(cls, user: User) -> Self:
        return cls(id=user.id, display_name=user.display_name, avatar_url=user.avatar_url)


class FriendRead(BaseModel):
    person: PersonRead
    since: datetime  # when they became friends, or when the request was sent


class FriendsRead(BaseModel):
    friends: list[FriendRead]
    incoming: list[FriendRead]  # requests waiting for your answer
    outgoing: list[FriendRead]  # your requests they haven't answered


class PersonPick(BaseModel):
    """Someone picked from the search (`user_id`), or an email typed in full."""

    user_id: uuid.UUID | None = None
    email: Email | None = None

    @model_validator(mode="after")
    def exactly_one(self) -> Self:
        if (self.user_id is None) == (self.email is None):
            raise ValueError("Send either user_id or email")
        return self


class PersonMatch(BaseModel):
    person: PersonRead
    relation: Relation


class RelationRead(BaseModel):
    person: PersonRead
    relation: Relation


class PersonProfile(BaseModel):
    person: PersonRead
    relation: Relation
    games_visible: bool


class SharedAnswers(BaseModel):
    """Someone's answers about a game, as others see them: everything but their notes."""

    ownership: Ownership | None
    wishlist_priority: int | None
    want_to_play: bool
    rating: float | None
    weight_vote: int | None
    playtime_feel: PlaytimeFeel | None
    can_teach: bool | None  # null: not answered (owners count as teachers)
    teach_minutes: int | None
    plays: int
    will_bring: bool
    player_counts: list[PlayerCountRead]
    moods: list[str]

    @staticmethod
    def fields_of(row: UserGame) -> dict[str, Any]:
        shared = {name: getattr(row, name) for name in collection.FIELD_TYPES if name != "notes"}
        return {
            **shared,
            "player_counts": [
                PlayerCountRead(players=pc.players, vote=pc.vote)
                for pc in sorted(row.player_counts, key=lambda pc: pc.players)
            ],
            "moods": sorted(mood.mood_id for mood in row.moods),
        }


class SharedGameRead(SharedAnswers):
    game: GameSummary

    @classmethod
    def build(cls, row: UserGame, game: Game) -> Self:
        return cls(game=GameSummary.from_game(game), **cls.fields_of(row))


class InviteLinkRead(BaseModel):
    id: uuid.UUID
    token: str
    created_at: datetime
    expires_at: datetime
    use_count: int


class InvitePreview(BaseModel):
    inviter: PersonRead


async def _get_person(session: AsyncSession, user_id: uuid.UUID) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise PERSON_NOT_FOUND
    return user


async def _people_by_relation(
    session: AsyncSession, me: uuid.UUID
) -> list[tuple[Friendship, User]]:
    other_id = case(
        (Friendship.user_low_id == me, Friendship.user_high_id), else_=Friendship.user_low_id
    )
    rows = await session.execute(
        select(Friendship, User)
        .join(User, User.id == other_id)
        .where(or_(Friendship.user_low_id == me, Friendship.user_high_id == me))
        .order_by(func.lower(User.display_name))
    )
    return [(friendship, user) for friendship, user in rows]


async def find_person(session: AsyncSession, pick: PersonPick) -> User | None:
    if pick.user_id is not None:
        return await session.get(User, pick.user_id)
    assert pick.email is not None
    return await session.scalar(
        select(User).where(func.lower(User.email) == pick.email.lower()).limit(1)
    )


@router.get("/friends")
async def list_friends(user: CurrentUser, session: SessionDep) -> FriendsRead:
    result = FriendsRead(friends=[], incoming=[], outgoing=[])
    for friendship, other in await _people_by_relation(session, user.id):
        if friendship.status == FriendshipStatus.ACCEPTED:
            since = friendship.accepted_at or friendship.created_at
            result.friends.append(FriendRead(person=PersonRead.of(other), since=since))
        elif friendship.requester_id == user.id:
            result.outgoing.append(
                FriendRead(person=PersonRead.of(other), since=friendship.created_at)
            )
        else:
            result.incoming.append(
                FriendRead(person=PersonRead.of(other), since=friendship.created_at)
            )
    return result


@router.post("/friends/requests")
async def send_friend_request(
    body: PersonPick, user: CurrentUser, session: SessionDep, mailer: MailerDep
) -> RelationRead:
    """Ask someone to be friends: picked from the search, or by exact email (any case).

    If they already asked you, this accepts. Someone who has blocked you looks the same as
    nobody having that email.
    """
    other = await find_person(session, body)
    if other is None or await has_blocked(session, other.id, user.id):
        raise NOBODY_THERE if body.email else PERSON_NOT_FOUND
    if other.id == user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "That's you.")
    if await has_blocked(session, user.id, other.id):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "You've blocked this person. Unblock them first."
        )

    current = await relation(session, user.id, other.id)
    if current == Relation.INCOMING:
        await _accept(session, user.id, other.id)
        current = Relation.FRIENDS
    elif current == Relation.NONE:
        low, high = Friendship.pair(user.id, other.id)
        await session.execute(
            insert(Friendship)
            .values(
                user_low_id=low,
                user_high_id=high,
                requester_id=user.id,
                status=FriendshipStatus.PENDING,
            )
            .on_conflict_do_nothing(
                index_elements=[Friendship.user_low_id, Friendship.user_high_id]
            )
        )
        await session.commit()
        # A request from them may have landed at the same moment; report what's stored.
        current = await relation(session, user.id, other.id)
        if current == Relation.OUTGOING:
            result = RelationRead(person=PersonRead.of(other), relation=current)
            await notify.friend_request(session, mailer, user, other)
            return result
    return RelationRead(person=PersonRead.of(other), relation=current)


async def _accept(session: AsyncSession, me: uuid.UUID, other: uuid.UUID) -> None:
    low, high = Friendship.pair(me, other)
    result = await session.execute(
        update(Friendship)
        .where(
            Friendship.user_low_id == low,
            Friendship.user_high_id == high,
            Friendship.requester_id == other,
            Friendship.status == FriendshipStatus.PENDING,
        )
        .values(status=FriendshipStatus.ACCEPTED, accepted_at=func.now())
    )
    if result.rowcount == 0:  # type: ignore[attr-defined]
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No friend request from this person")
    await session.commit()


@router.post("/friends/{user_id}/accept")
async def accept_friend_request(
    user_id: UserId, user: CurrentUser, session: SessionDep
) -> RelationRead:
    other = await _get_person(session, user_id)
    await _accept(session, user.id, other.id)
    return RelationRead(person=PersonRead.of(other), relation=Relation.FRIENDS)


@router.post("/friends/{user_id}/decline", status_code=status.HTTP_204_NO_CONTENT)
async def decline_friend_request(user_id: UserId, user: CurrentUser, session: SessionDep) -> None:
    """Drop their request. They aren't told; to them it still looks unanswered until they
    look again, and they can ask again later (block them to stop that)."""
    low, high = Friendship.pair(user.id, user_id)
    result = await session.execute(
        delete(Friendship).where(
            Friendship.user_low_id == low,
            Friendship.user_high_id == high,
            Friendship.requester_id == user_id,
            Friendship.status == FriendshipStatus.PENDING,
        )
    )
    if result.rowcount == 0:  # type: ignore[attr-defined]
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No friend request from this person")
    await session.commit()


@router.delete("/friends/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_friend(user_id: UserId, user: CurrentUser, session: SessionDep) -> None:
    """Unfriend, or cancel your request. Doing it twice is fine."""
    low, high = Friendship.pair(user.id, user_id)
    await session.execute(
        delete(Friendship).where(Friendship.user_low_id == low, Friendship.user_high_id == high)
    )
    await session.commit()


@router.get("/blocks")
async def list_blocks(user: CurrentUser, session: SessionDep) -> list[PersonRead]:
    blocked = await session.scalars(
        select(User)
        .join(UserBlock, UserBlock.blocked_id == User.id)
        .where(UserBlock.blocker_id == user.id)
        .order_by(func.lower(User.display_name))
    )
    return [PersonRead.of(other) for other in blocked]


@router.put("/blocks/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def block_person(user_id: UserId, user: CurrentUser, session: SessionDep) -> None:
    """Block someone: ends any friendship or request between you, and stops new ones."""
    if user_id == user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You can't block yourself.")
    await _get_person(session, user_id)
    low, high = Friendship.pair(user.id, user_id)
    await session.execute(
        delete(Friendship).where(Friendship.user_low_id == low, Friendship.user_high_id == high)
    )
    await session.execute(
        insert(UserBlock).values(blocker_id=user.id, blocked_id=user_id).on_conflict_do_nothing()
    )
    await session.commit()


@router.delete("/blocks/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unblock_person(user_id: UserId, user: CurrentUser, session: SessionDep) -> None:
    await session.execute(
        delete(UserBlock).where(UserBlock.blocker_id == user.id, UserBlock.blocked_id == user_id)
    )
    await session.commit()


def _active_links(owner: uuid.UUID) -> Select[InviteLink]:
    return select(InviteLink).where(
        InviteLink.owner_id == owner,
        InviteLink.revoked_at.is_(None),
        InviteLink.expires_at > func.now(),
    )


def _link_read(link: InviteLink) -> InviteLinkRead:
    return InviteLinkRead(
        id=link.id,
        token=link.token,
        created_at=link.created_at,
        expires_at=link.expires_at,
        use_count=link.use_count,
    )


@router.get("/invite-links")
async def list_invite_links(user: CurrentUser, session: SessionDep) -> list[InviteLinkRead]:
    links = await session.scalars(_active_links(user.id).order_by(InviteLink.created_at.desc()))
    return [_link_read(link) for link in links]


@router.post("/invite-links", status_code=status.HTTP_201_CREATED)
async def create_invite_link(user: CurrentUser, session: SessionDep) -> InviteLinkRead:
    active = await session.scalar(
        select(func.count()).select_from(_active_links(user.id).subquery())
    )
    if (active or 0) >= MAX_ACTIVE_INVITE_LINKS:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"You have {MAX_ACTIVE_INVITE_LINKS} links open. Turn one off to make another.",
        )
    link = InviteLink(
        token=secrets.token_urlsafe(16),
        owner_id=user.id,
        expires_at=datetime.now(UTC) + INVITE_LIFETIME,
    )
    session.add(link)
    await session.commit()
    await session.refresh(link)
    return _link_read(link)


@router.delete("/invite-links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def turn_off_invite_link(link_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> None:
    await session.execute(
        update(InviteLink)
        .where(
            InviteLink.id == link_id,
            InviteLink.owner_id == user.id,
            InviteLink.revoked_at.is_(None),
        )
        .values(revoked_at=func.now())
    )
    await session.commit()


async def _live_invite(session: AsyncSession, token: str) -> tuple[InviteLink, User]:
    row = (
        await session.execute(
            select(InviteLink, User)
            .join(User, User.id == InviteLink.owner_id)
            .where(
                InviteLink.token == token,
                InviteLink.revoked_at.is_(None),
                InviteLink.expires_at > func.now(),
            )
        )
    ).first()
    if row is None:
        raise INVITE_GONE
    link, owner = row
    return link, owner


InviteToken = Annotated[str, Path(min_length=1, max_length=64)]


@router.get("/invites/{token}")
async def preview_invite(token: InviteToken, session: SessionDep) -> InvitePreview:
    """Who sent this link. Open to anyone with it, signed in or not, so the page can say
    who's asking before they create an account."""
    _link, owner = await _live_invite(session, token)
    return InvitePreview(inviter=PersonRead.of(owner))


@router.post("/invites/{token}/accept")
async def accept_invite(token: InviteToken, user: CurrentUser, session: SessionDep) -> RelationRead:
    """Become friends with the link's owner straight away (no request to answer)."""
    link, owner = await _live_invite(session, token)
    if owner.id == user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "That's your own invite link.")
    if await blocked_either_way(session, owner.id, user.id):
        raise INVITE_GONE

    friendship = await friendship_between(session, user.id, owner.id)
    if friendship is None or friendship.status != FriendshipStatus.ACCEPTED:
        low, high = Friendship.pair(user.id, owner.id)
        await session.execute(
            insert(Friendship)
            .values(
                user_low_id=low,
                user_high_id=high,
                requester_id=owner.id,
                status=FriendshipStatus.ACCEPTED,
                accepted_at=func.now(),
            )
            .on_conflict_do_update(
                index_elements=[Friendship.user_low_id, Friendship.user_high_id],
                set_={"status": FriendshipStatus.ACCEPTED, "accepted_at": func.now()},
            )
        )
        link.use_count += 1
        await session.commit()
    return RelationRead(person=PersonRead.of(owner), relation=Relation.FRIENDS)


SEARCH_LIMIT = 8


def _like_prefix(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")
    return f"{escaped}%"


@router.get("/people/search")
async def search_people(
    user: CurrentUser,
    session: SessionDep,
    q: Annotated[str, Query(max_length=320)] = "",
) -> list[PersonMatch]:
    """People to suggest as you type: names starting with what you typed (or with a word
    in the name that does), friends first. An email only matches when typed in full, so
    suggestions never give one away. People who have blocked you, or whom you've blocked,
    never appear."""
    text = " ".join(q.split()).lower()
    if len(text) < 2:
        return []
    blocks = (
        select(UserBlock.blocker_id)
        .where(UserBlock.blocked_id == user.id)
        .union(select(UserBlock.blocked_id).where(UserBlock.blocker_id == user.id))
    )
    name = func.lower(User.display_name)
    if "@" in text:
        matches = func.lower(User.email) == text
    else:
        matches = or_(
            name.like(_like_prefix(text), escape="\\"),
            name.like("% " + _like_prefix(text), escape="\\"),
        )
    is_friend = (
        select(Friendship.user_low_id)
        .where(
            Friendship.status == FriendshipStatus.ACCEPTED,
            or_(
                (Friendship.user_low_id == user.id) & (Friendship.user_high_id == User.id),
                (Friendship.user_high_id == user.id) & (Friendship.user_low_id == User.id),
            ),
        )
        .exists()
    )
    found = await session.scalars(
        select(User)
        .where(matches, User.id != user.id, User.id.not_in(blocks), User.banned_at.is_(None))
        .order_by(is_friend.desc(), name.like(_like_prefix(text), escape="\\").desc(), name)
        .limit(SEARCH_LIMIT)
    )
    return [
        PersonMatch(
            person=PersonRead.of(other), relation=await relation(session, user.id, other.id)
        )
        for other in found
    ]


@router.get("/people/{user_id}")
async def read_person(user_id: UserId, user: CurrentUser, session: SessionDep) -> PersonProfile:
    other = await _get_person(session, user_id)
    if await blocked_either_way(session, user.id, other.id):
        raise PERSON_NOT_FOUND
    current = await relation(session, user.id, other.id)
    return PersonProfile(
        person=PersonRead.of(other),
        relation=current,
        games_visible=can_see_games(other, current),
    )


@router.get("/people/{user_id}/games")
async def list_person_games(
    user_id: UserId, user: CurrentUser, session: SessionDep
) -> list[SharedGameRead]:
    other = await _get_person(session, user_id)
    if await blocked_either_way(session, user.id, other.id):
        raise PERSON_NOT_FOUND
    if not can_see_games(other, await relation(session, user.id, other.id)):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Their games aren't shared with you.")
    rows = await session.execute(
        select(UserGame, Game)
        .join(Game, Game.id == UserGame.game_id)
        .where(UserGame.user_id == other.id)
        .order_by(Game.name)
    )
    return [SharedGameRead.build(row, game) for row, game in rows]
