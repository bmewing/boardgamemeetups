import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.discord.interactions import ADMINISTRATOR, COMMAND, COMPONENT, MANAGE_GUILD, POSTING
from app.discord.link import DiscordAccount, make_token
from app.models import DiscordCard, DiscordChannel
from app.schedule import today_in
from tests.conftest import FakeDiscord, MakePerson, Person
from tests.test_groups_api import Crew, crew, make_group
from tests.test_meetup_rsvps import add_date, answer

__all__ = ["crew"]  # fixtures used here

GUILD, CHANNEL = "111", "222"
EVERYONE = "0"


@pytest.fixture
def bot_key() -> Iterator[Ed25519PrivateKey]:
    """The bot set up, with a key standing in for the one Discord signs requests with."""
    key = Ed25519PrivateKey.generate()
    settings = get_settings()
    original = (settings.discord_public_key, settings.discord_bot_token, settings.app_url)
    settings.discord_public_key = (
        key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
    )
    settings.discord_bot_token = "test-bot-token"
    settings.app_url = "https://bggroup.test"
    yield key
    settings.discord_public_key, settings.discord_bot_token, settings.app_url = original


def signed(key: Ed25519PrivateKey, body: bytes, timestamp: str = "1762500000") -> dict[str, str]:
    return {
        "X-Signature-Ed25519": key.sign(timestamp.encode() + body).hex(),
        "X-Signature-Timestamp": timestamp,
        "Content-Type": "application/json",
    }


async def send(client: AsyncClient, key: Ed25519PrivateKey, interaction: dict[str, Any]) -> Any:
    body = json.dumps(interaction).encode()
    response = await client.post(
        "/api/discord/interactions", content=body, headers=signed(key, body)
    )
    assert response.status_code == 200, response.text
    return response.json()


def _member(user_id: str, permissions: str) -> dict[str, Any]:
    return {"user": {"id": user_id, "username": f"user{user_id}"}, "permissions": permissions}


def command(
    sub: str, user_id: str, *, permissions: str = EVERYONE, channel: str = CHANNEL
) -> dict[str, Any]:
    return {
        "type": COMMAND,
        "guild_id": GUILD,
        "channel_id": channel,
        "member": _member(user_id, permissions),
        "app_permissions": str(POSTING),
        "data": {"name": "bggroup", "options": [{"type": 1, "name": sub}]},
    }


def click(
    custom_id: str,
    user_id: str,
    *,
    message_id: str = "",
    values: list[str] | None = None,
    permissions: str = EVERYONE,
) -> dict[str, Any]:
    data: dict[str, Any] = {"custom_id": custom_id}
    if values is not None:
        data["values"] = values
    return {
        "type": COMPONENT,
        "guild_id": GUILD,
        "channel_id": CHANNEL,
        "member": _member(user_id, permissions),
        "app_permissions": str(POSTING),
        "message": {"id": message_id},
        "data": data,
    }


def manager() -> str:
    return str(MANAGE_GUILD)


async def link(client: AsyncClient, who: Person, discord_id: str) -> Response:
    token = make_token(DiscordAccount(id=discord_id, username=f"user{discord_id}"))
    return await client.put("/api/me/discord", headers=who.headers, json={"token": token})


def buttons(message: dict[str, Any]) -> list[str]:
    rows = message["components"]
    return [b.get("custom_id") or b["label"] for row in rows for b in row["components"]]


def fields(message: dict[str, Any]) -> dict[str, str]:
    return {f["name"]: f["value"] for f in message["embeds"][0]["fields"]}


async def connected(
    client: AsyncClient, key: Ed25519PrivateKey, crew: Crew, discord_id: str = "900"
) -> None:
    """Ann (who owns the crew's group) links her Discord account and connects the channel."""
    _, (ann, *_) = crew
    assert (await link(client, ann, discord_id)).status_code == 200
    reply = await send(client, key, command("connect", discord_id, permissions=manager()))
    assert "now follows **Thursday Crew**" in reply["data"]["content"]


async def soon(client: AsyncClient, crew: Crew, days: int = 3) -> str:
    group, (ann, *_) = crew
    return await add_date(client, group, ann, today_in("UTC") + timedelta(days=days))


async def run_hourly(client: AsyncClient) -> dict[str, Any]:
    response = await client.post("/api/notifications/run")
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


async def test_only_requests_signed_by_discord_get_in(
    client: AsyncClient, bot_key: Ed25519PrivateKey
) -> None:
    body = json.dumps({"type": 1}).encode()
    forged = signed(Ed25519PrivateKey.generate(), body)
    response = await client.post("/api/discord/interactions", content=body, headers=forged)
    assert response.status_code == 401
    garbage = {**signed(bot_key, body), "X-Signature-Ed25519": "not hex"}
    response = await client.post("/api/discord/interactions", content=body, headers=garbage)
    assert response.status_code == 401
    assert await send(client, bot_key, {"type": 1}) == {"type": 1}


async def test_the_endpoint_is_closed_until_the_bot_is_set_up(client: AsyncClient) -> None:
    response = await client.post("/api/discord/interactions", json={"type": 1})
    assert response.status_code == 404


async def test_linking_an_account_from_the_bot(
    client: AsyncClient, bot_key: Ed25519PrivateKey, person: MakePerson
) -> None:
    ann = await person("Ann")
    reply = await send(client, bot_key, command("link", "900"))
    assert reply["data"]["flags"] == 64  # only the person who asked sees it
    url = reply["data"]["components"][0]["components"][0]["url"]
    assert url.startswith("https://bggroup.test/discord/link/")
    token = url.rsplit("/", 1)[1]

    preview = await client.get(f"/api/discord/link/{token}")
    assert preview.json() == {"discord_username": "user900"}
    linked = await client.put("/api/me/discord", headers=ann.headers, json={"token": token})
    assert linked.json()["discord_username"] == "user900"

    reply = await send(client, bot_key, command("link", "900"))
    assert "linked to **Ann**" in reply["data"]["content"]

    unlinked = await client.delete("/api/me/discord", headers=ann.headers)
    assert unlinked.json()["discord_username"] is None


async def test_link_tokens_expire_and_cannot_be_altered(
    client: AsyncClient, bot_key: Ed25519PrivateKey, person: MakePerson
) -> None:
    ann = await person("Ann")
    account = DiscordAccount(id="900", username="ann")
    old = make_token(account, now=datetime.now(UTC) - timedelta(hours=1))
    assert (await client.get(f"/api/discord/link/{old}")).status_code == 404
    signature = make_token(account).split(".")[1]
    other_body = make_token(DiscordAccount(id="901", username="eve")).split(".")[0]
    altered = f"{other_body}.{signature}"
    response = await client.put("/api/me/discord", headers=ann.headers, json={"token": altered})
    assert response.status_code == 404


async def test_a_discord_account_moves_to_whoever_links_it_last(
    client: AsyncClient, bot_key: Ed25519PrivateKey, person: MakePerson
) -> None:
    ann, ben = await person("Ann"), await person("Ben")
    await link(client, ann, "900")
    await link(client, ben, "900")
    assert (await client.get("/api/me", headers=ann.headers)).json()["discord_username"] is None
    reply = await send(client, bot_key, command("link", "900"))
    assert "linked to **Ben**" in reply["data"]["content"]


async def test_connecting_a_channel(
    client: AsyncClient, bot_key: Ed25519PrivateKey, crew: Crew, db_session: AsyncSession
) -> None:
    group, (ann, ben, *_) = crew
    reply = await send(client, bot_key, command("connect", "900"))
    assert "Manage Server" in reply["data"]["content"]

    reply = await send(client, bot_key, command("connect", "900", permissions=manager()))
    assert "Link my account" in buttons(reply["data"])

    await link(client, ben, "901")  # a member, not an admin
    reply = await send(client, bot_key, command("connect", "901", permissions=manager()))
    assert "don't run any groups" in reply["data"]["content"]

    await connected(client, bot_key, crew)
    channel = await db_session.scalar(select(DiscordChannel))
    assert channel is not None and str(channel.group_id) == group["id"]

    # With two groups to choose from, Ann picks one from a list.
    other = await make_group(client, ann, name="Weekend Crew")
    reply = await send(client, bot_key, command("connect", "900", permissions=str(ADMINISTRATOR)))
    options = reply["data"]["components"][0]["components"][0]["options"]
    assert [o["label"] for o in options] == ["Thursday Crew", "Weekend Crew"]
    picked = await send(
        client, bot_key, click("connect", "900", values=[other["id"]], permissions=manager())
    )
    assert picked["type"] == 7  # replaces the list
    assert "now follows **Weekend Crew**" in picked["data"]["content"]
    db_session.expunge_all()
    channel = await db_session.scalar(select(DiscordChannel))
    assert channel is not None and str(channel.group_id) == other["id"]

    reply = await send(client, bot_key, command("disconnect", "900", permissions=manager()))
    assert "no longer follows" in reply["data"]["content"]
    assert await db_session.scalar(select(DiscordChannel)) is None


async def test_cards_go_up_a_week_ahead_once(
    client: AsyncClient, bot_key: Ed25519PrivateKey, crew: Crew, discord: FakeDiscord
) -> None:
    await connected(client, bot_key, crew)
    meetup_id = await soon(client, crew)
    await soon(client, crew, days=10)  # too far off yet

    assert (await run_hourly(client))["announced_dates"] == 1
    [(channel, _, message)] = discord.posts
    assert channel == CHANNEL
    embed = message["embeds"][0]
    assert embed["title"].startswith("Thursday Crew: ")
    assert embed["url"] == f"https://bggroup.test/meetups/{meetup_id}"
    assert "At 12 Elm St, Apt 3" in embed["description"]
    assert fields(message) == {
        "Going (0)": "Nobody yet",
        "Maybe (0)": "Nobody yet",
        "Can't go (0)": "Nobody yet",
    }
    assert buttons(message) == [
        f"rsvp:{meetup_id}:yes",
        f"rsvp:{meetup_id}:maybe",
        f"rsvp:{meetup_id}:no",
        "Open in the app",
    ]
    assert message["allowed_mentions"] == {"parse": []}

    assert (await run_hourly(client))["announced_dates"] == 0
    assert len(discord.posts) == 1


async def test_a_failed_post_is_tried_again_next_hour(
    client: AsyncClient, bot_key: Ed25519PrivateKey, crew: Crew, discord: FakeDiscord
) -> None:
    await connected(client, bot_key, crew)
    await soon(client, crew)
    discord.failing = True
    assert (await run_hourly(client))["announced_dates"] == 0
    discord.failing = False
    assert (await run_hourly(client))["announced_dates"] == 1


async def test_answering_with_the_buttons(
    client: AsyncClient,
    bot_key: Ed25519PrivateKey,
    crew: Crew,
    discord: FakeDiscord,
    person: MakePerson,
) -> None:
    group, (ann, ben, *_) = crew
    await client.patch(
        f"/api/groups/{group['id']}", headers=ann.headers, json={"plus_one_limit": 2}
    )
    await connected(client, bot_key, crew)
    meetup_id = await soon(client, crew)
    await run_hourly(client)
    [(_, card_id, _)] = discord.posts

    # Not linked yet: asked to link first.
    reply = await send(client, bot_key, click(f"rsvp:{meetup_id}:yes", "901", message_id=card_id))
    assert "Link my account" in buttons(reply["data"])

    # Ben said maybe with a guest in the app; Going on Discord keeps the guest.
    await answer(client, meetup_id, ben, "maybe", guests=1)
    await link(client, ben, "901")
    reply = await send(client, bot_key, click(f"rsvp:{meetup_id}:yes", "901", message_id=card_id))
    assert reply["type"] == 7  # the card, redrawn
    assert fields(reply["data"])["Going (2)"] == "Ben +1"
    meetup = (await client.get(f"/api/meetups/{meetup_id}", headers=ben.headers)).json()
    assert (meetup["rsvps"][0]["response"], meetup["my_guests"]) == ("yes", 1)

    # Can't go clears the guest.
    reply = await send(client, bot_key, click(f"rsvp:{meetup_id}:no", "901", message_id=card_id))
    assert fields(reply["data"])["Can't go (1)"] == "Ben"

    # Someone outside the group is told so, and nothing changes.
    outsider = await person("Zed")
    await link(client, outsider, "999")
    reply = await send(client, bot_key, click(f"rsvp:{meetup_id}:yes", "999", message_id=card_id))
    assert "not in **Thursday Crew**" in reply["data"]["content"]


async def test_cards_follow_changes_made_in_the_app(
    client: AsyncClient, bot_key: Ed25519PrivateKey, crew: Crew, discord: FakeDiscord
) -> None:
    _, (ann, ben, *_) = crew
    await connected(client, bot_key, crew)
    meetup_id = await soon(client, crew)
    await run_hourly(client)
    [(_, card_id, _)] = discord.posts

    await answer(client, meetup_id, ben, "yes")
    _, edited_id, message = discord.edits[-1]
    assert edited_id == card_id
    assert fields(message)["Going (1)"] == "Ben"

    await client.patch(
        f"/api/meetups/{meetup_id}", headers=ann.headers, json={"status": "cancelled"}
    )
    message = discord.edits[-1][2]
    assert message["embeds"][0]["title"].startswith("Cancelled: ")
    assert buttons(message) == ["Open in the app"]

    await client.delete(f"/api/meetups/{meetup_id}", headers=ann.headers)
    assert discord.deleted == [(CHANNEL, card_id)]


async def test_a_card_deleted_in_discord_is_left_alone(
    client: AsyncClient,
    bot_key: Ed25519PrivateKey,
    crew: Crew,
    discord: FakeDiscord,
    db_session: AsyncSession,
) -> None:
    _, (_, ben, *_) = crew
    await connected(client, bot_key, crew)
    meetup_id = await soon(client, crew)
    await run_hourly(client)
    [(_, card_id, _)] = discord.posts
    discord.gone.add(card_id)

    await answer(client, meetup_id, ben, "yes")
    card = await db_session.scalar(select(DiscordCard))
    assert card is not None and card.message_id is None
    assert (await run_hourly(client))["announced_dates"] == 0


async def test_posting_the_next_date_on_request(
    client: AsyncClient, bot_key: Ed25519PrivateKey, crew: Crew, discord: FakeDiscord
) -> None:
    reply = await send(client, bot_key, command("next", "500"))
    assert "isn't following a group" in reply["data"]["content"]

    await connected(client, bot_key, crew)
    reply = await send(client, bot_key, command("next", "500"))
    assert reply["data"]["content"] == "No dates coming up."

    later = await soon(client, crew, days=20)
    await soon(client, crew, days=30)
    reply = await send(client, bot_key, command("next", "500"))
    assert reply["data"]["content"] == "Posted."
    [(_, first_id, message)] = discord.posts
    assert buttons(message)[0] == f"rsvp:{later}:yes"

    # Asking again moves the card down to the bottom of the channel.
    await send(client, bot_key, command("next", "500"))
    assert len(discord.posts) == 2
    assert discord.deleted == [(CHANNEL, first_id)]
