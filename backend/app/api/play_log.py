"""What was played at a date: which games, in what order, who came, who played, and who won.
A game can be played more than once in a night; each time counts as a play.

The owner or an admin logs it once the date has started. A date with a locked pick that
nobody logs within a week is filled in as played as picked by the members who said yes.
"""

import uuid
from collections import defaultdict
from datetime import UTC, datetime
from typing import Self

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import achievements
from app.api.friends import PersonRead
from app.api.games import GameSummary
from app.api.meetups import _meetup
from app.auth import CurrentUser
from app.db import SessionDep
from app.groups import RUNS_GROUP, require_runner
from app.models import (
    Game,
    GroupMember,
    Meetup,
    MeetupAttendee,
    MeetupNomination,
    MeetupStatus,
    Play,
    PlayPlayer,
    User,
)
from app.pieces import Achievement
from app.plays import PlayLine, coop_by_default, fill_unlogged, going, save_log

router = APIRouter(tags=["play log"])

MAX_GAMES = 20


class PlayRead(BaseModel):
    game: GameSummary
    coop: bool
    coop_won: bool | None  # co-op only; null when not recorded
    players: list[PersonRead]
    winners: list[PersonRead]  # competitive only


class SuggestedGame(BaseModel):
    game: GameSummary
    coop: bool  # from BGG's mechanics; whoever logs it can change it


class LogRead(BaseModel):
    logged: bool
    assumed: bool  # filled in from the pick a week later because nobody logged it
    logged_at: datetime | None
    can_log: bool  # the owner or an admin, once the date has started
    attendees: list[PersonRead]
    plays: list[PlayRead]
    # To start the form from: the members who said yes, and the picked games.
    suggested_attendees: list[PersonRead]
    suggested_games: list[SuggestedGame]


class PlayIn(BaseModel):
    game_id: int
    coop: bool
    coop_won: bool | None = None
    players: list[uuid.UUID] = Field(default_factory=list, max_length=100)
    winners: list[uuid.UUID] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def results_match_the_kind_of_game(self) -> Self:
        if self.coop and self.winners:
            raise ValueError("A co-op game is won or lost by the table, not by players.")
        if not self.coop and self.coop_won is not None:
            raise ValueError("Only a co-op game has a table result.")
        if not set(self.winners) <= set(self.players):
            raise ValueError("Winners have to be among the players.")
        return self


class LogIn(BaseModel):
    """The whole log, in the order the games were played; it replaces what was there."""

    attendees: list[uuid.UUID] = Field(max_length=100)
    plays: list[PlayIn] = Field(max_length=MAX_GAMES)

    @model_validator(mode="after")
    def players_came(self) -> Self:
        came = set(self.attendees)
        for play in self.plays:
            if not set(play.players) <= came:
                raise ValueError("Players have to be among the people who came.")
        return self


def _started(meetup: Meetup) -> bool:
    return meetup.starts_at <= datetime.now(UTC)


async def _read(session: AsyncSession, meetup: Meetup, me: GroupMember) -> LogRead:
    attendee_users = list(
        await session.scalars(
            select(User)
            .join(MeetupAttendee, MeetupAttendee.user_id == User.id)
            .where(MeetupAttendee.meetup_id == meetup.id)
            .order_by(func.lower(User.display_name))
        )
    )
    rows = (
        await session.execute(
            select(Play, Game)
            .join(Game, Game.id == Play.game_id)
            .where(Play.meetup_id == meetup.id)
            .order_by(Play.position, Game.name)
        )
    ).all()
    players: dict[uuid.UUID, list[tuple[User, bool]]] = defaultdict(list)
    if rows:
        for player, person in await session.execute(
            select(PlayPlayer, User)
            .join(User, User.id == PlayPlayer.user_id)
            .where(PlayPlayer.play_id.in_([p.id for p, _ in rows]))
            .order_by(func.lower(User.display_name))
        ):
            players[player.play_id].append((person, player.won))

    yes = (await going(session, meetup.id))[0]
    suggested_attendees = list(
        await session.scalars(
            select(User).where(User.id.in_(yes)).order_by(func.lower(User.display_name))
        )
    )
    picked = await session.scalars(
        select(Game)
        .join(MeetupNomination, MeetupNomination.game_id == Game.id)
        .where(MeetupNomination.meetup_id == meetup.id, MeetupNomination.picked.is_(True))
        .order_by(Game.name)
    )
    return LogRead(
        logged=meetup.logged_at is not None,
        assumed=meetup.log_assumed,
        logged_at=meetup.logged_at,
        can_log=me.role in RUNS_GROUP
        and _started(meetup)
        and meetup.status == MeetupStatus.SCHEDULED,
        attendees=[PersonRead.of(u) for u in attendee_users],
        plays=[
            PlayRead(
                game=GameSummary.from_game(game),
                coop=play.coop,
                coop_won=play.coop_won,
                players=[PersonRead.of(u) for u, _ in players[play.id]],
                winners=[PersonRead.of(u) for u, won in players[play.id] if won],
            )
            for play, game in rows
        ],
        suggested_attendees=[PersonRead.of(u) for u in suggested_attendees],
        suggested_games=[
            SuggestedGame(game=GameSummary.from_game(g), coop=coop_by_default(g)) for g in picked
        ],
    )


@router.get("/meetups/{meetup_id}/log")
async def read_log(meetup_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> LogRead:
    meetup, group, me = await _meetup(session, meetup_id, user)
    await fill_unlogged(session, group)
    return await _read(session, meetup, me)


@router.put("/meetups/{meetup_id}/log")
async def save_play_log(
    meetup_id: uuid.UUID, body: LogIn, user: CurrentUser, session: SessionDep
) -> LogRead:
    """Record (or correct) what was played. Each player's play count for each game goes up
    by one; correcting a log takes the old one's plays back off first."""
    meetup, group, me = await _meetup(session, meetup_id, user)
    require_runner(me)
    if meetup.status == MeetupStatus.CANCELLED:
        raise HTTPException(status.HTTP_409_CONFLICT, "This date was cancelled.")
    if not _started(meetup):
        raise HTTPException(status.HTTP_409_CONFLICT, "This date hasn't happened yet.")
    members = set(
        await session.scalars(select(GroupMember.user_id).where(GroupMember.group_id == group.id))
    )
    if not set(body.attendees) <= members:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Only members can be marked as coming."
        )
    game_ids = list({p.game_id for p in body.plays})
    known = set(await session.scalars(select(Game.id).where(Game.id.in_(game_ids))))
    if missing := sorted(set(game_ids) - known):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown games: {missing}")
    await save_log(
        session,
        meetup,
        body.attendees,
        [PlayLine(p.game_id, p.coop, p.coop_won, p.players, p.winners) for p in body.plays],
    )
    await achievements.earn(session, Achievement.LOG_NIGHT, user.id)
    await session.commit()
    return await _read(session, meetup, me)
