from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Game, InviteLink
from tests.conftest import MakePerson, Person

# Far outside BGG's range, so a local database holding the real catalog can't interfere.
GAME_ID = 990_200_001


async def friends_of(client: AsyncClient, who: Person) -> dict[str, list[str]]:
    body = (await client.get("/api/friends", headers=who.headers)).json()
    return {key: [f["person"]["id"] for f in body[key]] for key in body}


async def request(client: AsyncClient, sender: Person, email: str) -> dict[str, object]:
    response = await client.post(
        "/api/friends/requests", headers=sender.headers, json={"email": email}
    )
    assert response.status_code == 200, response.text
    body: dict[str, object] = response.json()
    return body


async def test_request_by_email_then_accept(client: AsyncClient, person: MakePerson) -> None:
    ann, ben = await person("Ann"), await person("Ben")

    sent = await request(client, ann, "  BEN@Example.com ")

    assert sent["relation"] == "outgoing"
    assert await friends_of(client, ann) == {"friends": [], "incoming": [], "outgoing": [ben.id]}
    assert await friends_of(client, ben) == {"friends": [], "incoming": [ann.id], "outgoing": []}

    accepted = await client.post(f"/api/friends/{ann.id}/accept", headers=ben.headers)

    assert accepted.json()["relation"] == "friends"
    assert (await friends_of(client, ann))["friends"] == [ben.id]
    assert (await friends_of(client, ben))["friends"] == [ann.id]


async def test_asking_someone_who_already_asked_you_makes_you_friends(
    client: AsyncClient,
    person: MakePerson,
) -> None:
    ann, ben = await person("Ann"), await person("Ben")
    await request(client, ann, ben.email)

    crossed = await request(client, ben, ann.email)

    assert crossed["relation"] == "friends"
    assert (await friends_of(client, ann))["friends"] == [ben.id]


async def test_asking_twice_keeps_one_request(client: AsyncClient, person: MakePerson) -> None:
    ann, ben = await person("Ann"), await person("Ben")
    await request(client, ann, ben.email)

    again = await request(client, ann, ben.email)

    assert again["relation"] == "outgoing"
    assert (await friends_of(client, ben))["incoming"] == [ann.id]


async def test_unknown_email_and_own_email(client: AsyncClient, person: MakePerson) -> None:
    ann = await person("Ann")

    unknown = await client.post(
        "/api/friends/requests", headers=ann.headers, json={"email": "nobody@example.com"}
    )
    own = await client.post("/api/friends/requests", headers=ann.headers, json={"email": ann.email})
    malformed = await client.post(
        "/api/friends/requests", headers=ann.headers, json={"email": "Ben"}
    )

    assert unknown.status_code == 404
    assert unknown.json()["detail"] == "No one here uses that email yet."
    assert own.status_code == 400
    assert malformed.status_code == 422


async def test_decline_quietly_drops_the_request(client: AsyncClient, person: MakePerson) -> None:
    ann, ben = await person("Ann"), await person("Ben")
    await request(client, ann, ben.email)

    declined = await client.post(f"/api/friends/{ann.id}/decline", headers=ben.headers)

    assert declined.status_code == 204
    assert await friends_of(client, ann) == {"friends": [], "incoming": [], "outgoing": []}
    assert await friends_of(client, ben) == {"friends": [], "incoming": [], "outgoing": []}
    # Nothing left to answer; and Ann can't accept her own request.
    again = await client.post(f"/api/friends/{ann.id}/decline", headers=ben.headers)
    assert again.status_code == 404


async def test_cannot_accept_your_own_request(client: AsyncClient, person: MakePerson) -> None:
    ann, ben = await person("Ann"), await person("Ben")
    await request(client, ann, ben.email)

    response = await client.post(f"/api/friends/{ben.id}/accept", headers=ann.headers)

    assert response.status_code == 404


async def test_remove_a_friend_or_cancel_a_request(client: AsyncClient, person: MakePerson) -> None:
    ann, ben, cat = await person("Ann"), await person("Ben"), await person("Cat")
    await request(client, ann, ben.email)
    await request(client, ben, ann.email)
    await request(client, ann, cat.email)

    removed = await client.delete(f"/api/friends/{ben.id}", headers=ann.headers)
    cancelled = await client.delete(f"/api/friends/{cat.id}", headers=ann.headers)

    assert removed.status_code == cancelled.status_code == 204
    assert await friends_of(client, ann) == {"friends": [], "incoming": [], "outgoing": []}
    assert (await friends_of(client, cat))["incoming"] == []


async def test_blocking(client: AsyncClient, person: MakePerson) -> None:
    ann, ben = await person("Ann"), await person("Ben")
    await request(client, ann, ben.email)
    await client.post(f"/api/friends/{ann.id}/accept", headers=ben.headers)

    blocked = await client.put(f"/api/blocks/{ann.id}", headers=ben.headers)

    assert blocked.status_code == 204
    assert (await friends_of(client, ann))["friends"] == []
    # To Ann, Ben's email now looks unused, and his page is gone.
    search = await client.post(
        "/api/friends/requests", headers=ann.headers, json={"email": ben.email}
    )
    assert search.status_code == 404
    assert (await client.get(f"/api/people/{ben.id}", headers=ann.headers)).status_code == 404
    # Ben is told why he can't ask Ann.
    asking = await client.post(
        "/api/friends/requests", headers=ben.headers, json={"email": ann.email}
    )
    assert asking.status_code == 409
    listed = (await client.get("/api/blocks", headers=ben.headers)).json()
    assert [p["id"] for p in listed] == [ann.id]

    unblocked = await client.delete(f"/api/blocks/{ann.id}", headers=ben.headers)

    assert unblocked.status_code == 204
    assert (await client.get("/api/blocks", headers=ben.headers)).json() == []
    assert (await request(client, ann, ben.email))["relation"] == "outgoing"


async def test_cannot_block_yourself(client: AsyncClient, person: MakePerson) -> None:
    ann = await person("Ann")

    response = await client.put(f"/api/blocks/{ann.id}", headers=ann.headers)

    assert response.status_code == 400


async def make_link(client: AsyncClient, owner: Person) -> dict[str, object]:
    response = await client.post("/api/invite-links", headers=owner.headers)
    assert response.status_code == 201
    body: dict[str, object] = response.json()
    return body


async def test_invite_link_makes_friends_once(
    client: AsyncClient,
    person: MakePerson,
) -> None:
    ann, ben = await person("Ann"), await person("Ben")
    link = await make_link(client, ann)

    # Anyone with the link can see who sent it, signed in or not.
    preview = await client.get(f"/api/invites/{link['token']}")
    accepted = await client.post(f"/api/invites/{link['token']}/accept", headers=ben.headers)
    again = await client.post(f"/api/invites/{link['token']}/accept", headers=ben.headers)

    assert preview.json()["inviter"] == {
        "id": ann.id,
        "display_name": "Ann",
        "avatar_url": None,
        "piece": None,
        "piece_color": None,
    }
    assert accepted.json()["relation"] == again.json()["relation"] == "friends"
    assert (await friends_of(client, ben))["friends"] == [ann.id]
    links = (await client.get("/api/invite-links", headers=ann.headers)).json()
    assert [(link["id"], link["use_count"]) for link in links] == [(link["id"], 1)]


async def test_invite_link_settles_a_waiting_request(
    client: AsyncClient,
    person: MakePerson,
) -> None:
    ann, ben = await person("Ann"), await person("Ben")
    await request(client, ben, ann.email)
    link = await make_link(client, ann)

    await client.post(f"/api/invites/{link['token']}/accept", headers=ben.headers)

    assert await friends_of(client, ann) == {"friends": [ben.id], "incoming": [], "outgoing": []}


async def test_own_turned_off_expired_and_blocked_links(
    client: AsyncClient,
    person: MakePerson,
    db_session: AsyncSession,
) -> None:
    ann, ben, cat = await person("Ann"), await person("Ben"), await person("Cat")
    own, off, old, live = [await make_link(client, ann) for _ in range(4)]
    await client.delete(f"/api/invite-links/{off['id']}", headers=ann.headers)
    await db_session.execute(
        update(InviteLink)
        .where(InviteLink.token == old["token"])
        .values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
    )
    await client.put(f"/api/blocks/{cat.id}", headers=ann.headers)

    yours = await client.post(f"/api/invites/{own['token']}/accept", headers=ann.headers)
    turned_off = await client.post(f"/api/invites/{off['token']}/accept", headers=ben.headers)
    expired = await client.get(f"/api/invites/{old['token']}")
    blocked = await client.post(f"/api/invites/{live['token']}/accept", headers=cat.headers)

    assert yours.status_code == 400
    assert turned_off.status_code == expired.status_code == blocked.status_code == 404
    links = (await client.get("/api/invite-links", headers=ann.headers)).json()
    listed = {link["id"] for link in links}
    assert listed == {own["id"], live["id"]}


async def test_open_invite_links_are_limited(
    client: AsyncClient,
    person: MakePerson,
    db_session: AsyncSession,
) -> None:
    ann = await person("Ann")
    for _ in range(20):
        await make_link(client, ann)

    response = await client.post("/api/invite-links", headers=ann.headers)

    assert response.status_code == 409
    tokens = await db_session.scalars(select(InviteLink.token))
    assert len(set(tokens)) == 20


@pytest.fixture
async def game(db_session: AsyncSession) -> int:
    db_session.add(Game(id=GAME_ID, name="Zyxshared", is_expansion=False))
    await db_session.commit()
    return GAME_ID


async def test_seeing_someones_games_follows_their_visibility(
    client: AsyncClient,
    person: MakePerson,
    game: int,
) -> None:
    ann, ben, cat = await person("Ann"), await person("Ben"), await person("Cat")
    await request(client, ann, ben.email)
    await client.post(f"/api/friends/{ann.id}/accept", headers=ben.headers)
    saved = await client.put(
        f"/api/me/games/{game}",
        headers=ann.headers,
        json={"ownership": "owned", "rating": 8, "notes": "Missing a meeple", "moods": []},
    )
    assert saved.status_code == 200, saved.text

    async def view(viewer: Person) -> tuple[bool, int]:
        profile = (await client.get(f"/api/people/{ann.id}", headers=viewer.headers)).json()
        games = await client.get(f"/api/people/{ann.id}/games", headers=viewer.headers)
        return profile["games_visible"], games.status_code

    # Friends only, the default.
    assert await view(ben) == (True, 200)
    assert await view(cat) == (False, 403)
    shared = (await client.get(f"/api/people/{ann.id}/games", headers=ben.headers)).json()
    assert [(g["game"]["id"], g["ownership"], g["rating"]) for g in shared] == [(game, "owned", 8)]
    assert "notes" not in shared[0]

    await client.patch("/api/me", headers=ann.headers, json={"collection_visibility": "public"})
    assert await view(cat) == (True, 200)

    await client.patch("/api/me", headers=ann.headers, json={"collection_visibility": "private"})
    assert await view(ben) == (False, 403)
    assert await view(ann) == (True, 200)


async def test_person_page_shows_how_you_stand(
    client: AsyncClient,
    person: MakePerson,
) -> None:
    ann, ben = await person("Ann"), await person("Ben")
    await request(client, ann, ben.email)

    from_ann = (await client.get(f"/api/people/{ben.id}", headers=ann.headers)).json()
    from_ben = (await client.get(f"/api/people/{ann.id}", headers=ben.headers)).json()
    missing = await client.get(
        "/api/people/00000000-0000-0000-0000-000000000000", headers=ann.headers
    )

    assert from_ann["relation"] == "outgoing"
    assert from_ben["relation"] == "incoming"
    assert from_ann["person"]["display_name"] == "Ben"
    assert missing.status_code == 404


async def test_deleting_an_account_ends_its_friendships(
    client: AsyncClient,
    person: MakePerson,
) -> None:
    ann, ben = await person("Ann"), await person("Ben")
    await request(client, ann, ben.email)
    await client.post(f"/api/friends/{ann.id}/accept", headers=ben.headers)
    await make_link(client, ben)
    await client.put(f"/api/blocks/{ann.id}", headers=ben.headers)

    await client.delete("/api/me", headers=ben.headers)

    assert await friends_of(client, ann) == {"friends": [], "incoming": [], "outgoing": []}
