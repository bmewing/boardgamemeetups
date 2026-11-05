import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import ARRAY, DateTime, Enum, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class CollectionVisibility(StrEnum):
    PRIVATE = "private"
    FRIENDS = "friends"
    PUBLIC = "public"


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        # Display names double as usernames, so no two may match, ignoring case. Alembic
        # can't compare this index, so changes to it need a hand-written migration.
        Index("uq_users_display_name_lower", text("lower(display_name)"), unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    kinde_id: Mapped[str] = mapped_column(String(255), unique=True)
    email: Mapped[str | None] = mapped_column(String(320), index=True)
    display_name: Mapped[str] = mapped_column(String(80))
    avatar_url: Mapped[str | None] = mapped_column(String(2048))
    time_zone: Mapped[str] = mapped_column(String(64), default="UTC")
    bgg_username: Mapped[str | None] = mapped_column(String(64))
    # When this user last applied a pull from BGG (not just previewed one).
    bgg_pulled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    collection_visibility: Mapped[CollectionVisibility] = mapped_column(
        Enum(
            CollectionVisibility,
            native_enum=False,
            length=16,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        default=CollectionVisibility.FRIENDS,
    )
    # Kinds of email (app.email.EmailKind) this user has turned off; empty means all on.
    email_opt_outs: Mapped[list[str]] = mapped_column(
        ARRAY(String(32)), default=list, server_default=text("'{}'")
    )
    # Secret in each email's unsubscribe link, so it works without signing in. Made when
    # the first email goes out.
    email_token: Mapped[str | None] = mapped_column(String(64), unique=True)
    # Admins see the admin portal: site stats, and banning or deleting accounts. Kinde decides
    # (see Settings.kinde_admin_permission); this copy is refreshed on each request.
    is_admin: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    # A banned account keeps its data but every request it makes is refused.
    banned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ban_reason: Mapped[str | None] = mapped_column(String(500))
    # When the account last used the app, to the nearest few minutes (see app.auth).
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
