"""Find-a-time polls, and each member's answer to one."""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.group import _string_enum


class PollStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"


class TimePoll(Base):
    """An organizer offers some days and a window of hours; members tap the half hours they
    could make. Slots are derived from the dates and window, never stored."""

    __tablename__ = "time_polls"
    __table_args__ = (
        CheckConstraint(
            "start_minute >= 0 AND start_minute < end_minute AND end_minute <= 1440",
            name="window_in_a_day",
        ),
        CheckConstraint("duration_minutes BETWEEN 30 AND 720", name="duration_range"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    group_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"), index=True
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(120))
    # Sorted, unique ISO dates.
    dates: Mapped[list[str]] = mapped_column(JSONB)
    start_minute: Mapped[int] = mapped_column(Integer)
    end_minute: Mapped[int] = mapped_column(Integer)
    time_zone: Mapped[str] = mapped_column(String(64))
    duration_minutes: Mapped[int] = mapped_column(Integer, default=120)
    status: Mapped[PollStatus] = mapped_column(
        _string_enum(PollStatus), default=PollStatus.OPEN, server_default=PollStatus.OPEN.value
    )
    # The date made from the winning time, once there is one. Kept if the date is deleted.
    meetup_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("meetups.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TimePollResponse(Base):
    """One person's whole answer: the slots they're free. Empty means "none of these work",
    which is different from not having answered."""

    __tablename__ = "time_poll_responses"

    poll_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("time_polls.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    slots: Mapped[list[Any]] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
