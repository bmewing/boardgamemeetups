"""What the bot does with each slash command and button click Discord sends.

Discord waits only 3 seconds for an answer, so everything here answers straight away:
replies only the clicker sees ("ephemeral"), or the card they clicked, redrawn.
"""

import uuid
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.discord import cards
from app.discord.client import Discord, Message
from app.discord.link import DiscordAccount, link_url
from app.groups import RUNS_GROUP
from app.models import (
    DiscordCard,
    DiscordChannel,
    Group,
    GroupMember,
    Meetup,
    RsvpResponse,
    User,
)
from app.rsvp import change_response

Interaction = dict[str, Any]

# Interaction types Discord sends, and the response types we answer with.
PING, COMMAND, COMPONENT = 1, 2, 3
PONG, REPLY, UPDATE = 1, 4, 7
EPHEMERAL = 1 << 6
# Permission bits, as Discord sends them for the member and for the bot itself.
ADMINISTRATOR = 1 << 3
MANAGE_GUILD = 1 << 5
VIEW_CHANNEL = 1 << 10
SEND_MESSAGES = 1 << 11
EMBED_LINKS = 1 << 14
POSTING = VIEW_CHANNEL | SEND_MESSAGES | EMBED_LINKS
STRING_SELECT = 3
SELECT_LIMIT = 25

CONNECT_ID = "connect"
COMMAND_NAME = "bggroup"


def signature_ok(signature: str, timestamp: str, body: bytes) -> bool:
    """Discord signs every request with the application's key; anything else is refused.
    (Discord sends some badly signed requests on purpose, to check we do.)"""
    try:
        key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(get_settings().discord_public_key))
        key.verify(bytes.fromhex(signature), timestamp.encode() + body)
    except (ValueError, InvalidSignature):
        return False
    return True


def reply(content: str, components: list[Message] | None = None) -> Message:
    """A message only the person who clicked or typed sees."""
    return {
        "type": REPLY,
        "data": {
            "content": content,
            "flags": EPHEMERAL,
            "components": components or [],
            "allowed_mentions": {"parse": []},
        },
    }


def _discord_account(interaction: Interaction) -> DiscordAccount:
    user = (interaction.get("member") or {}).get("user") or interaction.get("user") or {}
    return DiscordAccount(id=str(user.get("id", "")), username=str(user.get("username", "")))


def _channel_id(interaction: Interaction) -> str:
    return str(interaction.get("channel_id") or (interaction.get("channel") or {}).get("id", ""))


def _bits(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _manages_server(interaction: Interaction) -> bool:
    permissions = _bits((interaction.get("member") or {}).get("permissions"))
    return bool(permissions & (ADMINISTRATOR | MANAGE_GUILD))


def _link_button(account: DiscordAccount) -> list[Message]:
    button = {
        "type": cards.BUTTON,
        "style": cards.LINK,
        "label": "Link my account",
        "url": link_url(account),
    }
    return [{"type": cards.BUTTON_ROW, "components": [button]}]


def link_prompt(account: DiscordAccount, first: str) -> Message:
    return reply(
        f"{first} Link your Discord account to Board Game Group first: open this link and "
        "sign in. It works for 15 minutes.",
        _link_button(account),
    )


async def _linked_user(session: AsyncSession, account: DiscordAccount) -> User | None:
    if not account.id:
        return None
    return await session.scalar(select(User).where(User.discord_id == account.id))


SUSPENDED = reply("Your Board Game Group account has been suspended.")


async def handle(session: AsyncSession, discord: Discord, interaction: Interaction) -> Message:
    kind = interaction.get("type")
    if kind == PING:
        return {"type": PONG}
    if not interaction.get("guild_id"):
        return reply("I only work in server channels.")
    if kind == COMMAND:
        return await _command(session, discord, interaction)
    if kind == COMPONENT:
        custom_id = str((interaction.get("data") or {}).get("custom_id", ""))
        if custom_id.startswith("rsvp:"):
            return await _rsvp(session, discord, interaction, custom_id)
        if custom_id == CONNECT_ID:
            return await _connect_picked(session, interaction)
    return reply("I don't know that one.")


async def _command(session: AsyncSession, discord: Discord, interaction: Interaction) -> Message:
    data = interaction.get("data") or {}
    options = data.get("options") or [{}]
    sub = options[0].get("name")
    if sub == "link":
        return await _link(session, interaction)
    if sub == "connect":
        return await _connect(session, interaction)
    if sub == "disconnect":
        return await _disconnect(session, interaction)
    if sub == "next":
        return await _next(session, discord, interaction)
    return reply("I don't know that command.")


async def _link(session: AsyncSession, interaction: Interaction) -> Message:
    account = _discord_account(interaction)
    user = await _linked_user(session, account)
    if user is None:
        return link_prompt(account, "Let's get you set up.")
    return reply(
        f"You're linked to **{user.display_name}** on Board Game Group. To link a different "
        "account instead, open this link and sign in as that one. It works for 15 minutes.",
        _link_button(account),
    )


async def _groups_run_by(session: AsyncSession, user: User) -> list[Group]:
    return list(
        await session.scalars(
            select(Group)
            .join(GroupMember, GroupMember.group_id == Group.id)
            .where(GroupMember.user_id == user.id, GroupMember.role.in_(RUNS_GROUP))
            .order_by(Group.name)
        )
    )


async def _connect(session: AsyncSession, interaction: Interaction) -> Message:
    if not _manages_server(interaction):
        return reply("Connecting a channel takes the Manage Server permission.")
    account = _discord_account(interaction)
    user = await _linked_user(session, account)
    if user is None:
        return link_prompt(account, "Connecting a channel needs to know who you are.")
    if user.banned_at is not None:
        return SUSPENDED
    groups = await _groups_run_by(session, user)
    if not groups:
        return reply("You don't run any groups on Board Game Group. Owners and admins can.")
    if len(groups) == 1:
        return await _save_connection(session, interaction, user, groups[0], REPLY)
    return reply(
        "Which group should this channel follow?",
        [
            {
                "type": cards.BUTTON_ROW,
                "components": [
                    {
                        "type": STRING_SELECT,
                        "custom_id": CONNECT_ID,
                        "placeholder": "Pick a group",
                        "options": [
                            {"label": cards.clip(group.name, 100), "value": str(group.id)}
                            for group in groups[:SELECT_LIMIT]
                        ],
                    }
                ],
            }
        ],
    )


async def _connect_picked(session: AsyncSession, interaction: Interaction) -> Message:
    """The group chosen from /bggroup connect's list, checked again."""
    if not _manages_server(interaction):
        return reply("Connecting a channel takes the Manage Server permission.")
    user = await _linked_user(session, _discord_account(interaction))
    if user is None or user.banned_at is not None:
        return reply("Run /bggroup connect again.")
    values = (interaction.get("data") or {}).get("values") or []
    try:
        group_id = uuid.UUID(str(values[0]))
    except (IndexError, ValueError):
        return reply("Run /bggroup connect again.")
    group = next((g for g in await _groups_run_by(session, user) if g.id == group_id), None)
    if group is None:
        return reply("You don't run that group any more.")
    return await _save_connection(session, interaction, user, group, UPDATE)


async def _save_connection(
    session: AsyncSession, interaction: Interaction, user: User, group: Group, answer_with: int
) -> Message:
    channel_id = _channel_id(interaction)
    # A channel switching groups drops the cards it had for the old one.
    await session.execute(
        delete(DiscordChannel).where(
            DiscordChannel.channel_id == channel_id, DiscordChannel.group_id != group.id
        )
    )
    await session.execute(
        insert(DiscordChannel)
        .values(
            channel_id=channel_id,
            guild_id=str(interaction["guild_id"]),
            group_id=group.id,
            connected_by_id=user.id,
        )
        .on_conflict_do_nothing()
    )
    await session.commit()
    text = (
        f"This channel now follows **{group.name}**. Each date gets a card here a week "
        "ahead, where people can say whether they're coming. Post the next one now with "
        "`/bggroup next`."
    )
    if _bits(interaction.get("app_permissions")) & POSTING != POSTING:
        text += (
            "\n\nI can't post here yet. Give me View Channel, Send Messages and Embed Links "
            "in this channel."
        )
    message = reply(text)
    message["type"] = answer_with
    return message


async def _disconnect(session: AsyncSession, interaction: Interaction) -> Message:
    if not _manages_server(interaction):
        return reply("Disconnecting a channel takes the Manage Server permission.")
    removed = await session.scalar(
        delete(DiscordChannel)
        .where(DiscordChannel.channel_id == _channel_id(interaction))
        .returning(DiscordChannel.group_id)
    )
    await session.commit()
    if removed is None:
        return reply("This channel isn't following a group.")
    return reply("This channel no longer follows a group. Cards already here stop updating.")


async def _next(session: AsyncSession, discord: Discord, interaction: Interaction) -> Message:
    channel_id = _channel_id(interaction)
    group_id = await session.scalar(
        select(DiscordChannel.group_id).where(DiscordChannel.channel_id == channel_id)
    )
    if group_id is None:
        return reply(
            "This channel isn't following a group. Someone who runs one can use `/bggroup connect`."
        )
    meetup = await cards.next_date(session, group_id)
    if meetup is None:
        return reply("No dates coming up.")
    if not await cards.repost(session, discord, meetup.id, channel_id):
        return reply("I couldn't post here. I need View Channel, Send Messages and Embed Links.")
    return reply("Posted.")


async def _rsvp(
    session: AsyncSession, discord: Discord, interaction: Interaction, custom_id: str
) -> Message:
    meetup_part, _, response_part = custom_id.removeprefix("rsvp:").partition(":")
    try:
        meetup_id = uuid.UUID(meetup_part)
        response = RsvpResponse(response_part)
    except ValueError:
        return reply("That button doesn't work any more.")
    account = _discord_account(interaction)
    user = await _linked_user(session, account)
    if user is None:
        return link_prompt(account, "Almost there!")
    if user.banned_at is not None:
        return SUSPENDED
    row = (
        await session.execute(
            select(Meetup, Group)
            .join(Group, Group.id == Meetup.group_id)
            .where(Meetup.id == meetup_id)
        )
    ).first()
    if row is None:
        return reply("That date has been removed.")
    meetup, group = row
    member = await session.scalar(
        select(GroupMember).where(GroupMember.group_id == group.id, GroupMember.user_id == user.id)
    )
    if member is None:
        return reply(
            f"You're not in **{group.name}** on Board Game Group. Ask its owner for an invite."
        )
    try:
        await change_response(session, meetup, group, user, response)
    except HTTPException as exc:
        await session.rollback()
        return reply(str(exc.detail))
    message_id = str((interaction.get("message") or {}).get("id", ""))
    card = await cards.card_for(session, meetup.id)
    await cards.refresh_cards(session, discord, meetup.id, skip=message_id)
    if card is None or not await _is_card(session, meetup.id, message_id):
        return reply(f"Got it: {cards.HEADINGS[response].lower()}.")
    return {"type": UPDATE, "data": card}


async def _is_card(session: AsyncSession, meetup_id: uuid.UUID, message_id: str) -> bool:
    """Whether the clicked message is a card we keep up to date (old, replaced ones aren't
    redrawn, so they don't look current)."""
    found = await session.scalar(
        select(DiscordCard.meetup_id).where(
            DiscordCard.meetup_id == meetup_id, DiscordCard.message_id == message_id
        )
    )
    return found is not None
