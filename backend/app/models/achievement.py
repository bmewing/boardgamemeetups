"""Achievements people have earned (app.achievements), which unlock pieces."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.pieces import Achievement


class UserAchievement(Base):
    __tablename__ = "user_achievements"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    # A plain string: the app checks the names, so new achievements need no migration.
    achievement: Mapped[Achievement] = mapped_column(
        Enum(
            Achievement,
            native_enum=False,
            length=32,
            values_callable=lambda members: [member.value for member in members],
        ),
        primary_key=True,
    )
    earned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # When they first saw what it unlocked; null shows the piece as new.
    seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
