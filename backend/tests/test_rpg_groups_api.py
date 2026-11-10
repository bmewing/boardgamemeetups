from datetime import date, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RpgSystem
from tests.conftest import MakePerson, Person
from tests.test_achievements import earned
from tests.test_groups_api import join, make_group, read
from tests.test_meetup_rsvps import add_date, answer

GLOOM, MIRE = 990_500_101, 990_500_102

Party = tuple[dict[str, Any], list[Person]]


@pytest.fixture
async def systems(db_session: AsyncSession) -> None:
    db_session.add_all([RpgSystem(id=GLOOM, name="Gloomzyx"), RpgSystem(id=MIRE, name="Mirequoll")])
    await db_session.commit()


@pytest.fixture
async def party(client: AsyncClient, person: MakePerson, systems: None) -> Party:
    """Ann's RPG group playing Gloomzyx, with Ben and Cat."""
    people = [await person(name) for name in ("Ann", "Ben", "Cat")]
    group = await make_group(client, people[0], kind="rpg", rpg_system_id=GLOOM)
    await join(client, group, people[0], *people[1:])
    return group, people


async def make_character(client: AsyncClient, who: Person, **fields: Any) -> dict[str, Any]:
    response = await client.post(
        "/api/me/characters",
        headers=who.headers,
        json={"name": "Vex", "system_id": GLOOM, **fields},
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


async def test_groups_are_board_game_groups_unless_made_as_rpg_groups(
    client: AsyncClient, person: MakePerson, systems: None
) -> None:
    ann = await person("Ann")

    games = await make_group(client, ann)
    rpg = await make_group(client, ann, kind="rpg", rpg_system_id=GLOOM, willing_to_split=True)

    assert (games["kind"], games["rpg_system"]) == ("board_games", None)
    assert rpg["kind"] == "rpg"
    assert rpg["rpg_system"]["name"] == "Gloomzyx"
    assert rpg["willing_to_split"] is False  # tables are a board-game thing
    listed = (await client.get("/api/groups", headers=ann.headers)).json()["groups"]
    assert sorted(g["kind"] for g in listed) == ["board_games", "rpg"]
    # The kind is fixed; the system can change.
    changed = await client.patch(
        f"/api/groups/{rpg['id']}",
        headers=ann.headers,
        json={"kind": "board_games", "rpg_system_id": MIRE},
    )
    assert (changed.json()["kind"], changed.json()["rpg_system"]["id"]) == ("rpg", MIRE)
    no_system = await client.patch(
        f"/api/groups/{games['id']}", headers=ann.headers, json={"rpg_system_id": GLOOM}
    )
    assert no_system.status_code == 422
    unknown = await client.post(
        "/api/groups", headers=ann.headers, json={"name": "X", "kind": "rpg", "rpg_system_id": 1}
    )
    assert unknown.status_code == 422


async def test_owners_and_admins_mark_gms(client: AsyncClient, party: Party) -> None:
    group, (ann, ben, cat) = party
    url = f"/api/groups/{group['id']}/members"

    assert (
        await client.patch(f"{url}/{cat.id}", headers=ben.headers, json={"is_gm": True})
    ).status_code == 403
    await client.patch(f"{url}/{ben.id}", headers=ann.headers, json={"role": "admin"})
    marked = await client.patch(f"{url}/{ben.id}", headers=ben.headers, json={"is_gm": True})

    assert marked.status_code == 200, marked.text
    gms = {m["person"]["id"]: m["is_gm"] for m in marked.json()["members"]}
    assert gms == {ann.id: False, ben.id: True, cat.id: False}
    assert {m["person"]["id"]: m["role"] for m in marked.json()["members"]}[ben.id] == "admin"


async def test_board_game_groups_have_no_gms_parties_or_recaps(
    client: AsyncClient, person: MakePerson
) -> None:
    ann, ben = await person("Ann"), await person("Ben")
    group = await make_group(client, ann)
    await join(client, group, ann, ben)
    past = await add_date(client, group, ann, date.today() - timedelta(days=1))

    gm = await client.patch(
        f"/api/groups/{group['id']}/members/{ben.id}", headers=ann.headers, json={"is_gm": True}
    )
    party = await client.get(f"/api/groups/{group['id']}/party", headers=ann.headers)
    recap = await client.put(f"/api/meetups/{past}/recap", headers=ann.headers, json={"recap": "x"})

    assert (gm.status_code, party.status_code, recap.status_code) == (409, 409, 409)


async def test_rpg_groups_have_no_game_picks_or_play_log(client: AsyncClient, party: Party) -> None:
    group, (ann, *_rest) = party
    meetup = await add_date(client, group, ann, date.today() + timedelta(days=2))

    for path in (
        f"/api/groups/{group['id']}/games",
        f"/api/meetups/{meetup}/games",
        f"/api/meetups/{meetup}/vote",
        f"/api/meetups/{meetup}/log",
    ):
        response = await client.get(path, headers=ann.headers)
        assert response.status_code == 409, path
        assert response.json()["detail"] == "This is an RPG group."


async def test_characters_are_private_until_they_join_a_party(
    client: AsyncClient, party: Party, person: MakePerson
) -> None:
    group, (_ann, ben, cat) = party
    dee = await person("Dee")

    vex = await make_character(
        client,
        ben,
        class_role="Cutter",
        level=2,
        ancestry="Skovlander",
        pronouns="she/her",
        notes="Owes the Lampblacks",
        portrait_url="https://example.com/vex.png",
        sheet_url="",
    )

    assert (vex["owner"]["id"], vex["system"]["name"], vex["status"]) == (
        ben.id,
        "Gloomzyx",
        "active",
    )
    assert (vex["sheet_url"], vex["group"]) == (None, None)
    url = f"/api/characters/{vex['id']}"
    assert (await client.get(url, headers=cat.headers)).status_code == 404

    joined = await client.patch(url, headers=ben.headers, json={"group_id": group["id"]})

    assert joined.json()["group"] == {"id": group["id"], "name": group["name"]}
    assert (await client.get(url, headers=cat.headers)).json()["name"] == "Vex"
    assert (await client.get(url, headers=dee.headers)).status_code == 404
    assert (await client.patch(url, headers=cat.headers, json={"level": 9})).status_code == 403
    assert (await client.delete(url, headers=cat.headers)).status_code == 403
    left = await client.patch(url, headers=ben.headers, json={"group_id": None, "status": "dead"})
    assert (left.json()["group"], left.json()["status"]) == (None, "dead")
    assert (await client.delete(url, headers=ben.headers)).status_code == 204
    assert (await client.get("/api/me/characters", headers=ben.headers)).json() == []


async def test_only_members_put_characters_in_rpg_groups(
    client: AsyncClient, party: Party, person: MakePerson
) -> None:
    group, (ann, *_rest) = party
    dee = await person("Dee")
    board = await make_group(client, ann, name="Board night")

    outsider = await client.post(
        "/api/me/characters",
        headers=dee.headers,
        json={"name": "Nope", "system_id": GLOOM, "group_id": group["id"]},
    )
    wrong_kind = await client.post(
        "/api/me/characters",
        headers=ann.headers,
        json={"name": "Nope", "system_id": GLOOM, "group_id": board["id"]},
    )
    no_system = await client.post(
        "/api/me/characters", headers=ann.headers, json={"name": "Nope", "system_id": 5}
    )
    bad_link = await client.post(
        "/api/me/characters",
        headers=ann.headers,
        json={"name": "Nope", "system_id": GLOOM, "portrait_url": "javascript:alert(1)"},
    )

    assert outsider.status_code == 404
    assert wrong_kind.status_code == 409
    assert no_system.status_code == 422
    assert bad_link.status_code == 422


async def test_the_party_shows_characters_and_what_members_say_about_the_system(
    client: AsyncClient, party: Party
) -> None:
    group, (ann, ben, cat) = party
    await client.patch(
        f"/api/groups/{group['id']}/members/{ann.id}", headers=ann.headers, json={"is_gm": True}
    )
    await client.put(f"/api/me/rpg-systems/{GLOOM}", headers=ann.headers, json={"can_gm": True})
    await client.put(
        f"/api/me/rpg-systems/{GLOOM}", headers=cat.headers, json={"want_to_play": True}
    )
    await make_character(client, ben, name="Vex", group_id=group["id"])
    await make_character(client, ben, name="Arlo", group_id=group["id"], status="retired")
    await make_character(client, cat, name="Zed", group_id=group["id"])
    await make_character(client, cat, name="Elsewhere")

    response = await client.get(f"/api/groups/{group['id']}/party", headers=ben.headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["system"]["id"] == GLOOM
    assert [c["name"] for c in body["characters"]] == ["Vex", "Zed", "Arlo"]  # active first
    members = {m["person"]["id"]: m for m in body["members"]}
    assert body["members"][0]["person"]["id"] == ann.id  # GMs first
    assert members[ann.id]["is_gm"] is True
    assert members[ann.id]["answers"] == {"knows": True, "can_gm": True, "want_to_play": False}
    assert members[cat.id]["answers"]["want_to_play"] is True
    assert members[ben.id]["answers"] is None


async def test_leaving_takes_your_characters_out_of_the_party(
    client: AsyncClient, party: Party
) -> None:
    group, (ann, ben, _cat) = party
    vex = await make_character(client, ben, group_id=group["id"])

    left = await client.delete(f"/api/groups/{group['id']}/members/{ben.id}", headers=ben.headers)

    assert left.status_code == 204
    still_mine = (await client.get(f"/api/characters/{vex['id']}", headers=ben.headers)).json()
    assert still_mine["group"] is None
    party_now = (await client.get(f"/api/groups/{group['id']}/party", headers=ann.headers)).json()
    assert party_now["characters"] == []


async def test_a_recap_records_who_came_and_shows_on_the_next_date(
    client: AsyncClient, party: Party
) -> None:
    group, (ann, ben, cat) = party
    past = await add_date(client, group, ann, date.today() - timedelta(days=1))
    upcoming = await add_date(client, group, ann, date.today() + timedelta(days=6))
    await answer(client, past, ann, "yes")
    await answer(client, past, ben, "yes", moods=["anything"])
    await answer(client, past, cat, "no")

    early = await client.put(
        f"/api/meetups/{upcoming}/recap", headers=ben.headers, json={"recap": "Too soon"}
    )
    saved = await client.put(
        f"/api/meetups/{past}/recap", headers=ben.headers, json={"recap": "  We stole the bell.  "}
    )

    assert early.status_code == 409
    assert saved.status_code == 200, saved.text
    assert saved.json()["recap"] == "We stole the bell."
    assert saved.json()["recap_updated_at"] is not None
    assert saved.json()["my_moods"] == []  # RPG groups don't use moods
    assert "attend_1" in await earned(client, ann)
    assert "attend_1" in await earned(client, ben)
    assert "attend_1" not in await earned(client, cat)
    next_date = (await client.get(f"/api/meetups/{upcoming}", headers=cat.headers)).json()
    assert (next_date["group"]["kind"], next_date["previous_recap"]) == (
        "rpg",
        "We stole the bell.",
    )


async def test_a_week_on_an_rpg_date_counts_the_yes_answers_as_there(
    client: AsyncClient, party: Party
) -> None:
    group, (ann, ben, cat) = party
    old = await add_date(client, group, ann, date.today() - timedelta(days=10))
    recent = await add_date(client, group, ann, date.today() - timedelta(days=3))
    for meetup in (old, recent):
        await answer(client, meetup, ben, "yes")

    await read(client, group, cat)  # looking at the group fills in old dates

    assert "attend_1" in await earned(client, ben)
    assert "attend_1" not in await earned(client, cat)
