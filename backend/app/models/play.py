"""Picking a meetup's games, who brings them, and what was actually played."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    false,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class MeetupNomination(Base):
    """A game put forward for a date. `picked` marks the ones chosen when the vote locks."""

    __tablename__ = "meetup_nominations"
    __table_args__ = (Index("uq_meetup_nominations_game", "meetup_id", "game_id", unique=True),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    meetup_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("meetups.id", ondelete="CASCADE"))
    game_id: Mapped[int] = mapped_column(Integer, ForeignKey("games.id"))
    nominated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    picked: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MeetupVote(Base):
    """Approval voting: one row per person per game they'd be happy to play."""

    __tablename__ = "meetup_votes"

    nomination_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("meetup_nominations.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )


class BringAssignment(Base):
    """Who's bringing a picked game. No row means nobody has claimed it yet."""

    __tablename__ = "bring_assignments"

    meetup_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("meetups.id", ondelete="CASCADE"), primary_key=True
    )
    game_id: Mapped[int] = mapped_column(Integer, ForeignKey("games.id"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )


class MeetupAttendee(Base):
    """Someone who actually came, as the play log records it."""

    __tablename__ = "meetup_attendees"

    meetup_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("meetups.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )


class Play(Base):
    """One game played at a date. Co-op games record whether the table won; competitive
    games record who won on `PlayPlayer`. No scores, no length. A night can have several,
    the same game more than once (a few rounds of a filler); `position` is the order they
    were played in."""

    __tablename__ = "plays"
    __table_args__ = (
        CheckConstraint("coop OR coop_won IS NULL", name="coop_result_only_for_coop"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    meetup_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("meetups.id", ondelete="CASCADE"), index=True
    )
    game_id: Mapped[int] = mapped_column(Integer, ForeignKey("games.id"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    coop: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    coop_won: Mapped[bool | None] = mapped_column(Boolean)  # null: not recorded


class PlayPlayer(Base):
    __tablename__ = "play_players"

    play_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("plays.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    won: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
