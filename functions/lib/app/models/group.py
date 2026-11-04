"""Groups, who's in them, the dates they meet, and who's coming."""

import uuid
from datetime import date, datetime, time
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    Time,
    false,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _string_enum[E: StrEnum](enum: type[E]) -> Enum:
    return Enum(
        enum,
        native_enum=False,
        length=16,
        values_callable=lambda members: [member.value for member in members],
    )


class GroupRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class MeetupStatus(StrEnum):
    SCHEDULED = "scheduled"
    CANCELLED = "cancelled"


class RsvpResponse(StrEnum):
    YES = "yes"
    MAYBE = "maybe"
    NO = "no"


class Group(Base):
    __tablename__ = "groups"
    __table_args__ = (
        CheckConstraint("duration_minutes > 0", name="duration_positive"),
        CheckConstraint("plus_one_limit >= 0", name="plus_one_limit_not_negative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str | None] = mapped_column(Text)
    # The owner's time zone when the group was made. Dates are kept as local times here.
    time_zone: Mapped[str] = mapped_column(String(64))
    # Happy to split into several tables, rather than everyone playing one game.
    willing_to_split: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    # How the group meets (see app.schedule.Schedule); null for dates added one at a time.
    schedule: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    # Defaults for new dates, scheduled or one-off.
    start_time: Mapped[time] = mapped_column(Time, default=time(19, 0))
    duration_minutes: Mapped[int] = mapped_column(Integer, default=180)
    location: Mapped[str | None] = mapped_column(String(200))
    # Guests each member may bring to a date; 0 means no guests.
    plus_one_limit: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class GroupMember(Base):
    __tablename__ = "group_members"
    __table_args__ = (
        # One owner per group.
        Index(
            "uq_group_members_one_owner",
            "group_id",
            unique=True,
            postgresql_where=text("role = 'owner'"),
        ),
    )

    group_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True
    )
    # Indexed for "my groups".
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    role: Mapped[GroupRole] = mapped_column(_string_enum(GroupRole))
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GroupInvite(Base):
    """An invitation to an email address. It's matched to whoever signs in with that email,
    so it can wait for someone who isn't on the app yet."""

    __tablename__ = "group_invites"
    __table_args__ = (Index("uq_group_invites_group_email", "group_id", "email", unique=True),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    group_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"))
    # Stored lowercased; one invite per address per group.
    email: Mapped[str] = mapped_column(String(320), index=True)
    invited_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Meetup(Base):
    """One date a group meets. Scheduled ones remember the rule date they came from."""

    __tablename__ = "meetups"
    __table_args__ = (
        CheckConstraint("duration_minutes > 0", name="duration_positive"),
        # A rule date makes at most one meetup.
        Index(
            "uq_meetups_group_slot",
            "group_id",
            "slot_date",
            unique=True,
            postgresql_where=text("slot_date IS NOT NULL"),
        ),
        Index("ix_meetups_group_starts", "group_id", "starts_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    group_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"))
    # The wall-clock date and time in the group's time zone, which is what people agreed to.
    local_date: Mapped[date] = mapped_column(Date)
    local_time: Mapped[time] = mapped_column(Time)
    # The same moment as an instant, for sorting and "upcoming"; recomputed if the time
    # zone changes.
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration_minutes: Mapped[int] = mapped_column(Integer)
    location: Mapped[str | None] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[MeetupStatus] = mapped_column(
        _string_enum(MeetupStatus), default=MeetupStatus.SCHEDULED
    )
    # The schedule's date this came from; null for a date added on its own.
    slot_date: Mapped[date | None] = mapped_column(Date)
    # Changed by hand, so schedule changes leave it alone.
    is_overridden: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    # When the owner or an admin locked the pick: voting and nominating stop.
    picks_locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # When what was played was logged; `log_assumed` when it was filled in a week later
    # from the pick and the yes answers because nobody logged it.
    logged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    log_assumed: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MeetupRsvp(Base):
    __tablename__ = "meetup_rsvps"
    __table_args__ = (CheckConstraint("guests >= 0", name="guests_not_negative"),)

    meetup_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("meetups.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    response: Mapped[RsvpResponse] = mapped_column(_string_enum(RsvpResponse))
    # Guests coming along (yes or maybe only), up to the group's plus-one limit.
    guests: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    responded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MeetupRsvpMood(Base):
    """A mood someone is in for a date they might come to (yes or maybe)."""

    __tablename__ = "meetup_rsvp_moods"
    __table_args__ = (
        ForeignKeyConstraint(
            ["meetup_id", "user_id"],
            ["meetup_rsvps.meetup_id", "meetup_rsvps.user_id"],
            ondelete="CASCADE",
        ),
    )

    meetup_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    mood_id: Mapped[str] = mapped_column(String(32), ForeignKey("moods.id"), primary_key=True)
