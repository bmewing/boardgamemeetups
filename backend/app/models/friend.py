"""Friendships between users, blocks, and the invite links that bring new people in."""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class FriendshipStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"


class Friendship(Base):
    """One row per pair of users, whichever of them asked.

    The pair is stored in a fixed order (smaller id first) so two people asking each other
    at the same moment can't end up with two rows. A declined or cancelled request, and a
    removed friend, simply have no row.
    """

    __tablename__ = "friendships"
    __table_args__ = (
        CheckConstraint("user_low_id < user_high_id", name="pair_in_order"),
        CheckConstraint(
            "requester_id = user_low_id OR requester_id = user_high_id",
            name="requester_in_pair",
        ),
    )

    user_low_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    # Indexed so "my friends" can look up either side of the pair.
    user_high_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    requester_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    status: Mapped[FriendshipStatus] = mapped_column(
        Enum(
            FriendshipStatus,
            native_enum=False,
            length=16,
            values_callable=lambda enum: [member.value for member in enum],
        )
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @staticmethod
    def pair(a: uuid.UUID, b: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
        return (a, b) if a < b else (b, a)

    def other(self, user_id: uuid.UUID) -> uuid.UUID:
        return self.user_high_id if user_id == self.user_low_id else self.user_low_id


class UserBlock(Base):
    """`blocker` doesn't want to hear from `blocked`: no requests, no finding them by email."""

    __tablename__ = "user_blocks"
    __table_args__ = (CheckConstraint("blocker_id <> blocked_id", name="not_self"),)

    blocker_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    blocked_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class InviteLink(Base):
    """A link anyone can open to become friends with its owner, until it expires or is
    turned off. Stored rather than signed so a link that gets passed around can be stopped.
    """

    __tablename__ = "invite_links"
    __table_args__ = (CheckConstraint("use_count >= 0", name="use_count_not_negative"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    token: Mapped[str] = mapped_column(String(64), unique=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # New friendships made through this link.
    use_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
