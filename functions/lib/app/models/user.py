import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import ARRAY, DateTime, Enum, ForeignKey, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.pieces import Piece, PieceColor


class CollectionVisibility(StrEnum):
    PRIVATE = "private"
    FRIENDS = "friends"
    PUBLIC = "public"


def _values(enum: type[StrEnum]) -> list[str]:
    """Store a StrEnum as its values in a plain string column (no Postgres enum type)."""
    return [member.value for member in enum]


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
    # The game piece that stands for this user (app.pieces). Null: a meeple, and a color
    # worked out from their id.
    piece: Mapped[Piece | None] = mapped_column(
        Enum(Piece, native_enum=False, length=32, values_callable=_values)
    )
    piece_color: Mapped[PieceColor | None] = mapped_column(
        Enum(PieceColor, native_enum=False, length=16, values_callable=_values)
    )
    time_zone: Mapped[str] = mapped_column(String(64), default="UTC")
    # The Discord account linked through the bot (app.discord.link), so its button clicks
    # act as this user. The name is only for showing which account it is.
    discord_id: Mapped[str | None] = mapped_column(String(20), unique=True)
    discord_username: Mapped[str | None] = mapped_column(String(100))
    bgg_username: Mapped[str | None] = mapped_column(String(64))
    # When this user last applied a pull from BGG (not just previewed one).
    bgg_pulled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    collection_visibility: Mapped[CollectionVisibility] = mapped_column(
        Enum(
            CollectionVisibility,
            native_enum=False,
            length=16,
            values_callable=_values,
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
    # Who brought this person to the app: the invite they accepted was made before their
    # account was (app.achievements.earn_recruit). Set once.
    referred_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    # When the account last used the app, to the nearest few minutes (see app.auth).
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
