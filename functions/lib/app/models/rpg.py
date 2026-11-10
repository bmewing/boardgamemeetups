"""Tabletop RPG systems, what people say about them, and the characters they play."""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Sequence,
    String,
    Text,
    false,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

# Systems people add that aren't on RPGGeek count down from -1, clear of RPGGeek's ids.
CUSTOM_RPG_SYSTEM_IDS = Sequence(
    "custom_rpg_system_ids",
    start=-1,
    increment=-1,
    maxvalue=-1,
    minvalue=-(2**31),
    metadata=Base.metadata,
)


class RpgSystem(Base):
    """An RPGGeek "RPG" (a game line such as Blades in the Dark), cached locally, or a system
    someone added that RPGGeek doesn't list.

    RPGGeek rows can start as stubs (a name from a book's link) and gain the description and
    pictures the first time they're looked at; `details_fetched_at` says which is which.
    """

    __tablename__ = "rpg_systems"
    __table_args__ = (
        # Like ix_games_name_trgm: Alembic can create it but not compare it.
        Index("ix_rpg_systems_name_trgm", text("lower(name) gin_trgm_ops"), postgresql_using="gin"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(512))
    description: Mapped[str | None] = mapped_column(Text)
    thumbnail_url: Mapped[str | None] = mapped_column(String(1024))
    image_url: Mapped[str | None] = mapped_column(String(1024))
    # Who added a custom system; they can edit it. Null for RPGGeek systems.
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    details_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    @property
    def is_custom(self) -> bool:
        return self.id < 0


class UserRpgSystem(Base):
    """What one person says about one system. Shared with their groups, except the notes."""

    __tablename__ = "user_rpg_systems"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    system_id: Mapped[int] = mapped_column(
        ForeignKey("rpg_systems.id"), primary_key=True, index=True
    )
    knows: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    can_gm: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    want_to_play: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CharacterStatus(StrEnum):
    ACTIVE = "active"
    RETIRED = "retired"
    DEAD = "dead"


class Character(Base):
    """Someone's character in a system, optionally in one RPG group's party."""

    __tablename__ = "characters"
    __table_args__ = (CheckConstraint("level >= 0", name="level_not_negative"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    system_id: Mapped[int] = mapped_column(ForeignKey("rpg_systems.id"))
    name: Mapped[str] = mapped_column(String(80))
    class_role: Mapped[str | None] = mapped_column(String(120))
    level: Mapped[int | None] = mapped_column(Integer)
    ancestry: Mapped[str | None] = mapped_column(String(120))
    pronouns: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[CharacterStatus] = mapped_column(
        Enum(
            CharacterStatus,
            native_enum=False,
            length=16,
            values_callable=lambda members: [member.value for member in members],
        ),
        default=CharacterStatus.ACTIVE,
        server_default=CharacterStatus.ACTIVE.value,
    )
    notes: Mapped[str | None] = mapped_column(Text)
    portrait_url: Mapped[str | None] = mapped_column(String(1024))
    sheet_url: Mapped[str | None] = mapped_column(String(1024))
    # The party it plays in; cleared if its player leaves the group or the group goes.
    group_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("groups.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
