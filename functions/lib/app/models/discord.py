"""Discord channels that follow a group, and the meetup cards the bot has posted in them."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class DiscordChannel(Base):
    """A channel a group's owner or admin connected to the group: its dates are posted
    there. A channel follows one group; a group may have several channels."""

    __tablename__ = "discord_channels"

    # Discord IDs ("snowflakes") are 64-bit numbers, kept as the strings Discord sends.
    channel_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    guild_id: Mapped[str] = mapped_column(String(20))
    group_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"), index=True
    )
    connected_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class DiscordCard(Base):
    """The bot's post about one date in one channel, kept up to date as people answer.

    The row is made before the post goes out, so two runs can't both post it. Its message
    ID stays null while posting, and goes back to null if the post is deleted in Discord,
    so it isn't posted again.
    """

    __tablename__ = "discord_cards"

    meetup_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("meetups.id", ondelete="CASCADE"), primary_key=True
    )
    channel_id: Mapped[str] = mapped_column(
        ForeignKey("discord_channels.channel_id", ondelete="CASCADE"), primary_key=True
    )
    message_id: Mapped[str | None] = mapped_column(String(20))
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
