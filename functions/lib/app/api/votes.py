"""Picking a date's games: nominating, approval voting, locking the pick, and who brings
each picked game.

Members who said yes nominate and vote. The owner and admins lock the pick (one game or
several), which stops voting and nominating; answers stay open. A picked game with one
owner going is theirs to bring; with several, the first to claim it brings it.

At an online date the games are Board Game Arena's: any game on BGA can be nominated, it's
fitted to BGA's player counts, and nobody brings anything.
"""

import uuid
from collections import defaultdict
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app import achievements, notify
from app.api.collection import GameBrief
from app.api.friends import PersonRead
from app.api.games import GameSummary
from app.api.meetups import _meetup
from app.auth import CurrentUser
from app.bga import BgaLink, bga_games_for, counts_fit
from app.db import SessionDep
from app.email import MailerDep
from app.groups import RUNS_GROUP, TableFit, player_range, require_runner, table_fit
from app.models import (
    BringAssignment,
    Game,
    Group,
    GroupMember,
    Meetup,
    MeetupNomination,
    MeetupStatus,
    MeetupVote,
    Ownership,
    User,
    UserGame,
)
from app.pieces import Achievement
from app.plays import going

router = APIRouter(tags=["votes"])

NOMINATION_NOT_FOUND = HTTPException(status.HTTP_404_NOT_FOUND, "Nomination not found")
ONLINE_NOTHING_TO_BRING = HTTPException(
    status.HTTP_409_CONFLICT, "This date is on Board Game Arena; there's nothing to bring."
)


class BringRead(BaseModel):
    person: PersonRead | None  # null: nobody has claimed it yet
    owners_going: list[PersonRead]  # who could bring it


class NominationRead(BaseModel):
    id: uuid.UUID
    game: GameSummary
    nominated_by: PersonRead | None
    votes: list[PersonRead]  # members going who voted for it
    my_vote: bool
    picked: bool
    fits_now: bool  # still seats tonight's headcount, as answers change
    fit: TableFit | None  # how it seats the headcount: everyone together, split, or not at all
    # The game's player range, widened by expansions people going are bringing.
    min_players: int | None
    max_players: int | None
    bring: BringRead | None  # for picked games (never at an online date)
    bga: BgaLink | None  # at an online date, how to play it on BGA
    can_remove: bool


class VoteRead(BaseModel):
    locked: bool
    locked_at: datetime | None
    can_vote: bool  # you said yes and the pick isn't locked
    can_lock: bool  # you're the owner or an admin
    headcount: int
    nominations: list[NominationRead]  # picked first, then most votes
    # Games someone going owns that aren't nominated yet; online, the games on BGA that
    # someone going has among their games (any other BGA game can be searched for).
    nominatable: list[GameBrief]
    online: bool
    # Someone going has BGA Premium, so they can start a table of a Premium game.
    premium_host_going: bool


class NominationIn(BaseModel):
    game_id: int


class LockIn(BaseModel):
    nomination_ids: list[uuid.UUID] = Field(min_length=1, max_length=20)


class BringIn(BaseModel):
    """Who brings it: yourself when left out. Someone else takes the owner or an admin."""

    user_id: uuid.UUID | None = None


async def _owners_going(
    session: AsyncSession, coming: list[uuid.UUID], game_ids: list[int]
) -> dict[int, list[User]]:
    """For each game, the members going who own it (whether or not they planned to bring it)."""
    owners: dict[int, list[User]] = defaultdict(list)
    if not coming or not game_ids:
        return owners
    rows = await session.execute(
        select(UserGame.game_id, User)
        .join(User, User.id == UserGame.user_id)
        .where(
            UserGame.user_id.in_(coming),
            UserGame.game_id.in_(game_ids),
            UserGame.ownership == Ownership.OWNED,
        )
        .order_by(func.lower(User.display_name))
    )
    for game_id, person in rows:
        owners[game_id].append(person)
    return owners


async def vote_state(
    session: AsyncSession, meetup: Meetup, group: Group, me: GroupMember, user: User
) -> VoteRead:
    coming, guests = await going(session, meetup.id)
    headcount = len(coming) + guests
    locked = meetup.picks_locked_at is not None
    runs = me.role in RUNS_GROUP

    rows = (
        await session.execute(
            select(MeetupNomination, Game)
            .join(Game, Game.id == MeetupNomination.game_id)
            .where(MeetupNomination.meetup_id == meetup.id)
        )
    ).all()
    nomination_ids = [n.id for n, _ in rows]
    votes: dict[uuid.UUID, list[User]] = defaultdict(list)
    if nomination_ids:
        voters = await session.execute(
            select(MeetupVote.nomination_id, User)
            .join(User, User.id == MeetupVote.user_id)
            .where(MeetupVote.nomination_id.in_(nomination_ids), MeetupVote.user_id.in_(coming))
            .order_by(func.lower(User.display_name))
        )
        for nomination_id, person in voters:
            votes[nomination_id].append(person)
    people = {
        u.id: u
        for u in await session.scalars(
            select(User).where(
                User.id.in_([n.nominated_by_id for n, _ in rows if n.nominated_by_id])
            )
        )
    }

    game_ids = [g.id for _, g in rows]
    on_bga = await bga_games_for(session, game_ids) if meetup.is_online else {}
    owners = await _owners_going(session, coming, game_ids)
    bringers = {
        a.game_id: a.user_id
        for a in await session.scalars(
            select(BringAssignment).where(BringAssignment.meetup_id == meetup.id)
        )
    }
    bringer_users = {
        u.id: u for u in await session.scalars(select(User).where(User.id.in_(bringers.values())))
    }
    expansions = await _expansions_going(session, coming)

    nominations: list[NominationRead] = []
    for nomination, game in rows:
        bga = on_bga.get(game.id)
        low: int | None
        high: int | None
        if bga is not None:
            counts = sorted(bga.player_counts)
            low, high = counts[0], counts[-1]
            fit = counts_fit(counts, headcount, group.willing_to_split)
        else:
            low, high = player_range(game, [e for e in expansions if game.id in e.base_game_ids])
            fit = table_fit(low, high, headcount, group.willing_to_split)
        bring = None
        if nomination.picked and not meetup.is_online:
            who = bringers.get(game.id)
            bring = BringRead(
                person=PersonRead.of(bringer_users[who]) if who in bringer_users else None,
                owners_going=[PersonRead.of(o) for o in owners[game.id]],
            )
        nominations.append(
            NominationRead(
                id=nomination.id,
                game=GameSummary.from_game(game),
                nominated_by=PersonRead.of(people[nomination.nominated_by_id])
                if nomination.nominated_by_id in people
                else None,
                votes=[PersonRead.of(v) for v in votes[nomination.id]],
                my_vote=any(v.id == user.id for v in votes[nomination.id]),
                picked=nomination.picked,
                fits_now=fit is not None,
                fit=fit,
                min_players=low,
                max_players=high,
                bring=bring,
                bga=BgaLink.of(bga) if bga is not None else None,
                can_remove=not locked and (runs or nomination.nominated_by_id == user.id),
            )
        )
    nominations.sort(key=lambda n: (not n.picked, -len(n.votes), n.game.name.lower()))

    nominatable: list[GameBrief] = []
    if coming and not locked and meetup.is_online:
        theirs = set(
            await session.scalars(select(UserGame.game_id).where(UserGame.user_id.in_(coming)))
        )
        known = await bga_games_for(session, theirs - set(game_ids))
        nominatable = [
            GameBrief(
                id=g.id,
                name=g.name,
                year_published=g.year_published,
                thumbnail_url=g.thumbnail_url,
                is_expansion=g.is_expansion,
            )
            for g in await session.scalars(
                select(Game).where(Game.id.in_(list(known))).order_by(Game.name)
            )
        ]
    elif coming and not locked:
        owned = await session.scalars(
            select(Game)
            .join(UserGame, UserGame.game_id == Game.id)
            .where(
                UserGame.user_id.in_(coming),
                UserGame.ownership == Ownership.OWNED,
                Game.is_expansion.is_(False),
                Game.id.not_in(game_ids or [0]),
            )
            .distinct()
            .order_by(Game.name)
        )
        nominatable = [
            GameBrief(
                id=g.id,
                name=g.name,
                year_published=g.year_published,
                thumbnail_url=g.thumbnail_url,
                is_expansion=g.is_expansion,
            )
            for g in owned
        ]
    return VoteRead(
        locked=locked,
        locked_at=meetup.picks_locked_at,
        can_vote=not locked and user.id in coming and meetup.status == MeetupStatus.SCHEDULED,
        can_lock=runs,
        headcount=headcount,
        nominations=nominations,
        nominatable=nominatable,
        online=meetup.is_online,
        premium_host_going=meetup.is_online and await _premium_going(session, coming),
    )


async def _premium_going(session: AsyncSession, coming: list[uuid.UUID]) -> bool:
    if not coming:
        return False
    found = await session.scalar(
        select(User.id).where(User.id.in_(coming), User.bga_premium.is_(True)).limit(1)
    )
    return found is not None


async def _expansions_going(session: AsyncSession, coming: list[uuid.UUID]) -> list[Game]:
    if not coming:
        return []
    return list(
        await session.scalars(
            select(Game)
            .join(UserGame, UserGame.game_id == Game.id)
            .where(
                UserGame.user_id.in_(coming),
                UserGame.ownership == Ownership.OWNED,
                UserGame.will_bring.is_(True),
                Game.is_expansion.is_(True),
            )
            .distinct()
        )
    )


def _open(meetup: Meetup) -> None:
    if meetup.status == MeetupStatus.CANCELLED:
        raise HTTPException(status.HTTP_409_CONFLICT, "This date has been cancelled.")
    if meetup.picks_locked_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "The pick is locked.")


async def _require_going(session: AsyncSession, meetup: Meetup, user: User) -> None:
    if user.id not in (await going(session, meetup.id))[0]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Say you're going to nominate and vote.")


async def _nomination(
    session: AsyncSession, meetup: Meetup, nomination_id: uuid.UUID
) -> MeetupNomination:
    nomination = await session.get(MeetupNomination, nomination_id)
    if nomination is None or nomination.meetup_id != meetup.id:
        raise NOMINATION_NOT_FOUND
    return nomination


@router.get("/meetups/{meetup_id}/vote")
async def read_vote(meetup_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> VoteRead:
    meetup, group, me = await _meetup(session, meetup_id, user)
    return await vote_state(session, meetup, group, me, user)


@router.post("/meetups/{meetup_id}/nominations")
async def nominate(
    meetup_id: uuid.UUID, body: NominationIn, user: CurrentUser, session: SessionDep
) -> VoteRead:
    """Put forward a game someone going owns, or at an online date any game on BGA. You vote
    for what you nominate; nominating a game that's already up just adds your vote."""
    meetup, group, me = await _meetup(session, meetup_id, user)
    _open(meetup)
    await _require_going(session, meetup, user)
    if meetup.is_online:
        if body.game_id not in await bga_games_for(session, [body.game_id]):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "That game isn't on Board Game Arena."
            )
    else:
        coming = (await going(session, meetup.id))[0]
        if not (await _owners_going(session, coming, [body.game_id]))[body.game_id]:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "Nobody going owns that game."
            )
    await session.execute(
        insert(MeetupNomination)
        .values(id=uuid.uuid4(), meetup_id=meetup.id, game_id=body.game_id, nominated_by_id=user.id)
        .on_conflict_do_nothing(
            index_elements=[MeetupNomination.meetup_id, MeetupNomination.game_id]
        )
    )
    nomination_id = await session.scalar(
        select(MeetupNomination.id).where(
            MeetupNomination.meetup_id == meetup.id, MeetupNomination.game_id == body.game_id
        )
    )
    await session.execute(
        insert(MeetupVote)
        .values(nomination_id=nomination_id, user_id=user.id)
        .on_conflict_do_nothing()
    )
    await session.commit()
    return await vote_state(session, meetup, group, me, user)


@router.delete("/meetups/{meetup_id}/nominations/{nomination_id}")
async def withdraw_nomination(
    meetup_id: uuid.UUID, nomination_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> VoteRead:
    """Take a game off the ballot: whoever nominated it, or the owner or an admin."""
    meetup, group, me = await _meetup(session, meetup_id, user)
    _open(meetup)
    nomination = await _nomination(session, meetup, nomination_id)
    if nomination.nominated_by_id != user.id:
        require_runner(me)
    await session.delete(nomination)
    await session.commit()
    return await vote_state(session, meetup, group, me, user)


@router.put("/meetups/{meetup_id}/nominations/{nomination_id}/vote")
async def vote(
    meetup_id: uuid.UUID, nomination_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> VoteRead:
    meetup, group, me = await _meetup(session, meetup_id, user)
    _open(meetup)
    await _require_going(session, meetup, user)
    nomination = await _nomination(session, meetup, nomination_id)
    await session.execute(
        insert(MeetupVote)
        .values(nomination_id=nomination.id, user_id=user.id)
        .on_conflict_do_nothing()
    )
    await achievements.earn(session, Achievement.VOTE, user.id)
    await session.commit()
    return await vote_state(session, meetup, group, me, user)


@router.delete("/meetups/{meetup_id}/nominations/{nomination_id}/vote")
async def unvote(
    meetup_id: uuid.UUID, nomination_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> VoteRead:
    meetup, group, me = await _meetup(session, meetup_id, user)
    _open(meetup)
    nomination = await _nomination(session, meetup, nomination_id)
    await session.execute(
        delete(MeetupVote).where(
            MeetupVote.nomination_id == nomination.id, MeetupVote.user_id == user.id
        )
    )
    await session.commit()
    return await vote_state(session, meetup, group, me, user)


@router.post("/meetups/{meetup_id}/lock")
async def lock_pick(
    meetup_id: uuid.UUID,
    body: LockIn,
    user: CurrentUser,
    session: SessionDep,
    mailer: MailerDep,
) -> VoteRead:
    """Choose the game or games to play, and stop the voting. A picked game with exactly one
    owner going is tagged as theirs to bring (not at an online date, where nobody brings
    anything). Members who said yes or maybe are emailed the pick."""
    meetup, group, me = await _meetup(session, meetup_id, user)
    require_runner(me)
    _open(meetup)
    chosen = list(
        await session.scalars(
            select(MeetupNomination).where(
                MeetupNomination.meetup_id == meetup.id,
                MeetupNomination.id.in_(body.nomination_ids),
            )
        )
    )
    if len(chosen) != len(set(body.nomination_ids)):
        raise NOMINATION_NOT_FOUND
    for nomination in chosen:
        nomination.picked = True
    meetup.picks_locked_at = datetime.now(UTC)
    await achievements.earn(session, Achievement.LOCK_PICK, user.id)
    await achievements.earn(
        session,
        Achievement.NOMINATE_PICKED,
        *(n.nominated_by_id for n in chosen if n.nominated_by_id is not None),
    )
    coming = (await going(session, meetup.id))[0]
    owners = await _owners_going(session, coming, [n.game_id for n in chosen])
    for nomination in chosen:
        if len(owners[nomination.game_id]) == 1 and not meetup.is_online:
            session.add(
                BringAssignment(
                    meetup_id=meetup.id,
                    game_id=nomination.game_id,
                    user_id=owners[nomination.game_id][0].id,
                )
            )
            await achievements.earn(
                session, Achievement.BRING_GAME, owners[nomination.game_id][0].id
            )
    await session.commit()
    result = await vote_state(session, meetup, group, me, user)
    await notify.pick_locked(session, mailer, meetup, group, user)
    return result


@router.post("/meetups/{meetup_id}/unlock")
async def unlock_pick(meetup_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> VoteRead:
    """Open the voting again. The pick and who was bringing it are cleared."""
    meetup, group, me = await _meetup(session, meetup_id, user)
    require_runner(me)
    if meetup.logged_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "What was played is already logged.")
    await session.execute(delete(BringAssignment).where(BringAssignment.meetup_id == meetup.id))
    for nomination in await session.scalars(
        select(MeetupNomination).where(MeetupNomination.meetup_id == meetup.id)
    ):
        nomination.picked = False
    meetup.picks_locked_at = None
    await session.commit()
    return await vote_state(session, meetup, group, me, user)


async def _picked(session: AsyncSession, meetup: Meetup, game_id: int) -> None:
    picked = await session.scalar(
        select(MeetupNomination.id).where(
            MeetupNomination.meetup_id == meetup.id,
            MeetupNomination.game_id == game_id,
            MeetupNomination.picked.is_(True),
        )
    )
    if picked is None or meetup.picks_locked_at is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That game isn't one of the picks.")


@router.put("/meetups/{meetup_id}/bring/{game_id}")
async def bring_game(
    meetup_id: uuid.UUID,
    game_id: int,
    body: BringIn,
    user: CurrentUser,
    session: SessionDep,
    mailer: MailerDep,
) -> VoteRead:
    """Claim a picked game to bring, or (owner or admin) hand it to another owner going,
    who is emailed about it."""
    meetup, group, me = await _meetup(session, meetup_id, user)
    if meetup.is_online:
        raise ONLINE_NOTHING_TO_BRING
    await _picked(session, meetup, game_id)
    bringer = body.user_id or user.id
    if bringer != user.id:
        require_runner(me)
    coming = (await going(session, meetup.id))[0]
    if not any(o.id == bringer for o in (await _owners_going(session, coming, [game_id]))[game_id]):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Only someone going who owns it can bring it."
        )
    previous = await session.scalar(
        select(BringAssignment.user_id).where(
            BringAssignment.meetup_id == meetup.id, BringAssignment.game_id == game_id
        )
    )
    await session.execute(
        insert(BringAssignment)
        .values(meetup_id=meetup.id, game_id=game_id, user_id=bringer)
        .on_conflict_do_update(
            index_elements=[BringAssignment.meetup_id, BringAssignment.game_id],
            set_={"user_id": bringer},
        )
    )
    await achievements.earn(session, Achievement.BRING_GAME, bringer)
    await session.commit()
    result = await vote_state(session, meetup, group, me, user)
    if bringer != previous:
        game = await session.get(Game, game_id)
        bringer_user = await session.get(User, bringer)
        if game is not None and bringer_user is not None:
            await notify.bringing(session, mailer, meetup, group, game, bringer_user, user)
    return result


@router.delete("/meetups/{meetup_id}/bring/{game_id}")
async def stop_bringing(
    meetup_id: uuid.UUID, game_id: int, user: CurrentUser, session: SessionDep
) -> VoteRead:
    """No longer bringing it (yourself, or anyone for the owner or an admin)."""
    meetup, group, me = await _meetup(session, meetup_id, user)
    assignment = await session.get(BringAssignment, (meetup.id, game_id))
    if assignment is not None:
        if assignment.user_id != user.id:
            require_runner(me)
        await session.delete(assignment)
        await session.commit()
    return await vote_state(session, meetup, group, me, user)
