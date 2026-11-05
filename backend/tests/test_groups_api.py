from datetime import date, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Game
from app.schedule import today_in
from tests.conftest import MakePerson, Person

# Far outside BGG's range, so a local database holding the real catalog can't interfere.
DUO, FOUR, BIG, UNKNOWN, BASE, EXPANSION = range(990_300_001, 990_300_007)

Crew = tuple[dict[str, Any], list[Person]]


async def make_group(client: AsyncClient, owner: Person, **fields: Any) -> dict[str, Any]:
    response = await client.post(
        "/api/groups", headers=owner.headers, json={"name": "Thursday Crew", **fields}
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


async def invite(
    client: AsyncClient, group: dict[str, Any], inviter: Person, email: str
) -> dict[str, Any]:
    response = await client.post(
        f"/api/groups/{group['id']}/invites", headers=inviter.headers, json={"email": email}
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


async def join(
    client: AsyncClient, group: dict[str, Any], inviter: Person, *people: Person
) -> None:
    for who in people:
        sent = await invite(client, group, inviter, who.email)
        accepted = await client.post(
            f"/api/group-invites/{sent['invite']['id']}/accept", headers=who.headers
        )
        assert accepted.status_code == 200, accepted.text


async def read(client: AsyncClient, group: dict[str, Any], who: Person) -> dict[str, Any]:
    response = await client.get(f"/api/groups/{group['id']}", headers=who.headers)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def roles(group: dict[str, Any]) -> dict[str, str]:
    return {m["person"]["id"]: m["role"] for m in group["members"]}


def dates(group: dict[str, Any]) -> list[str]:
    return [m["local_date"] for m in group["upcoming"]]


@pytest.fixture
async def crew(client: AsyncClient, person: MakePerson) -> Crew:
    """Ann's group, with Ben, Cat, Dee and Eve as members."""
    people = [await person(name) for name in ("Ann", "Ben", "Cat", "Dee", "Eve")]
    group = await make_group(client, people[0])
    await join(client, group, people[0], *people[1:])
    return group, people


async def test_creating_a_group_makes_you_its_owner(
    client: AsyncClient, person: MakePerson
) -> None:
    ann = await person("Ann")

    group = await make_group(client, ann, description="Weeknight games", willing_to_split=True)

    assert group["my_role"] == "owner"
    assert roles(group) == {ann.id: "owner"}
    assert group["time_zone"] == "UTC"  # the owner's
    assert group["willing_to_split"] is True
    assert group["schedule"] is None
    assert group["upcoming"] == []
    listed = (await client.get("/api/groups", headers=ann.headers)).json()
    assert [(g["name"], g["my_role"], g["member_count"]) for g in listed["groups"]] == [
        ("Thursday Crew", "owner", 1)
    ]


async def test_a_new_group_takes_its_owners_time_zone_unless_told_otherwise(
    client: AsyncClient, person: MakePerson
) -> None:
    ann = await person("Ann")
    await client.patch("/api/me", headers=ann.headers, json={"time_zone": "America/Chicago"})

    own = await make_group(client, ann)
    chosen = await make_group(client, ann, time_zone="Europe/London")
    bad = await client.post(
        "/api/groups", headers=ann.headers, json={"name": "X", "time_zone": "Nowhere/Here"}
    )

    assert own["time_zone"] == "America/Chicago"
    assert chosen["time_zone"] == "Europe/London"
    assert bad.status_code == 422


async def test_joining_takes_accepting_an_invite(client: AsyncClient, person: MakePerson) -> None:
    ann, ben = await person("Ann"), await person("Ben")
    group = await make_group(client, ann)

    sent = await invite(client, group, ann, "BEN@example.com")

    assert sent["on_app"] is True
    # Not in yet: the group is hidden, and the invite waits on Ben's Groups page.
    hidden = await client.get(f"/api/groups/{group['id']}", headers=ben.headers)
    assert hidden.status_code == 404
    waiting = (await client.get("/api/groups", headers=ben.headers)).json()["invites"]
    assert [(i["group_name"], i["invited_by"]["id"]) for i in waiting] == [
        ("Thursday Crew", ann.id)
    ]
    # Admins see who's invited by name, never by their email.
    pending = (await read(client, group, ann))["invites"]
    assert [(i["person"]["id"], i["email"]) for i in pending] == [(ben.id, None)]

    accepted = await client.post(
        f"/api/group-invites/{waiting[0]['id']}/accept", headers=ben.headers
    )

    assert accepted.json()["my_role"] == "member"
    assert roles(accepted.json()) == {ann.id: "owner", ben.id: "member"}
    assert (await read(client, group, ann))["invites"] == []
    assert (await client.get("/api/groups", headers=ben.headers)).json()["invites"] == []
    again = await client.post(
        f"/api/groups/{group['id']}/invites", headers=ann.headers, json={"email": ben.email}
    )
    assert again.status_code == 409


async def test_declining_an_invite(client: AsyncClient, person: MakePerson) -> None:
    ann, ben = await person("Ann"), await person("Ben")
    group = await make_group(client, ann)
    invite_id = (await invite(client, group, ann, ben.email))["invite"]["id"]

    declined = await client.post(f"/api/group-invites/{invite_id}/decline", headers=ben.headers)
    not_hers = await client.post(f"/api/group-invites/{invite_id}/accept", headers=ann.headers)

    assert declined.status_code == 204
    assert not_hers.status_code == 404
    assert (await read(client, group, ann))["invites"] == []


async def test_an_invite_waits_for_someone_to_sign_up(
    client: AsyncClient, person: MakePerson
) -> None:
    ann = await person("Ann")
    group = await make_group(client, ann)

    sent = await invite(client, group, ann, "dee@example.com")
    dee = await person("Dee")

    assert sent["on_app"] is False
    assert sent["invite"]["email"] == "dee@example.com"
    waiting = (await client.get("/api/groups", headers=dee.headers)).json()["invites"]
    assert [i["group_id"] for i in waiting] == [group["id"]]


async def test_someone_who_blocked_you_never_sees_your_invite(
    client: AsyncClient, person: MakePerson
) -> None:
    ann, ben = await person("Ann"), await person("Ben")
    await client.put(f"/api/blocks/{ann.id}", headers=ben.headers)
    group = await make_group(client, ann)

    sent = await invite(client, group, ann, ben.email)

    assert sent["on_app"] is False
    assert (await client.get("/api/groups", headers=ben.headers)).json()["invites"] == []
    accept = await client.post(
        f"/api/group-invites/{sent['invite']['id']}/accept", headers=ben.headers
    )
    assert accept.status_code == 404


async def test_what_members_admins_and_the_owner_can_do(client: AsyncClient, crew: Crew) -> None:
    group, (ann, ben, cat, dee, eve) = crew
    url = f"/api/groups/{group['id']}"

    async def make_role(who: Person, target: Person, role: str) -> int:
        response = await client.patch(
            f"{url}/members/{target.id}", headers=who.headers, json={"role": role}
        )
        return response.status_code

    async def remove(who: Person, target: Person) -> int:
        return (await client.delete(f"{url}/members/{target.id}", headers=who.headers)).status_code

    # Members can't run the group.
    assert (await client.patch(url, headers=ben.headers, json={"name": "X"})).status_code == 403
    refused = await client.post(f"{url}/invites", headers=ben.headers, json={"email": "z@x.com"})
    assert refused.status_code == 403

    # Only the owner makes admins.
    assert await make_role(ann, ben, "admin") == 200

    # Admins run it...
    renamed = await client.patch(url, headers=ben.headers, json={"name": "Thursday Club"})
    assert renamed.json()["name"] == "Thursday Club"
    allowed = await client.post(f"{url}/invites", headers=ben.headers, json={"email": "z@x.com"})
    assert allowed.status_code == 201
    assert await remove(ben, dee) == 204
    # ...but can't make admins, remove admins or the owner, or delete the group.
    assert await make_role(ben, cat, "admin") == 403
    assert await make_role(ann, cat, "admin") == 200
    assert await remove(ben, cat) == 403
    assert await remove(ben, ann) == 403
    assert (await client.delete(url, headers=ben.headers)).status_code == 403

    # The owner can remove anyone, and delete the group.
    assert await remove(ann, cat) == 204
    assert set(roles(await read(client, group, ann))) == {ann.id, ben.id, eve.id}
    assert (await client.delete(url, headers=ann.headers)).status_code == 204
    assert (await client.get(url, headers=ben.headers)).status_code == 404


async def test_handing_the_group_over(client: AsyncClient, crew: Crew) -> None:
    group, (ann, ben, *_rest) = crew
    url = f"/api/groups/{group['id']}"

    stuck = await client.delete(f"{url}/members/{ann.id}", headers=ann.headers)
    handed = await client.patch(
        f"{url}/members/{ben.id}", headers=ann.headers, json={"role": "owner"}
    )

    assert stuck.status_code == 400
    assert roles(handed.json())[ben.id] == "owner"
    assert roles(handed.json())[ann.id] == "admin"
    left = await client.delete(f"{url}/members/{ann.id}", headers=ann.headers)
    assert left.status_code == 204


async def test_deleting_your_account_hands_your_groups_on(
    client: AsyncClient, crew: Crew, person: MakePerson
) -> None:
    group, (ann, ben, cat, *_rest) = crew
    url = f"/api/groups/{group['id']}"
    await client.patch(f"{url}/members/{cat.id}", headers=ann.headers, json={"role": "admin"})
    solo = await make_group(client, ann)

    await client.delete("/api/me", headers=ann.headers)

    # Cat is the only admin, so Cat takes over; Ann's group of one goes.
    after = roles(await read(client, group, ben))
    assert after[cat.id] == "owner"
    assert ann.id not in after
    # Signing in again makes a fresh account, which sees no trace of the old group.
    fresh = await person("Ann")
    gone = await client.get(f"/api/groups/{solo['id']}", headers=fresh.headers)
    assert gone.status_code == 404


async def test_schedule_keeps_eight_dates_and_respects_edits(
    client: AsyncClient, crew: Crew
) -> None:
    group, (ann, ben, *_rest) = crew
    url = f"/api/groups/{group['id']}"
    today = today_in("UTC")
    weekly = {"kind": "weekly", "weekday": today.weekday(), "starts_on": today.isoformat()}

    scheduled = (
        await client.patch(
            url, headers=ann.headers, json={"schedule": weekly, "start_time": "19:00:00"}
        )
    ).json()

    expected = [(today + timedelta(weeks=n)).isoformat() for n in range(8)]
    assert dates(scheduled) == expected
    assert all(m["scheduled"] and not m["edited"] for m in scheduled["upcoming"])
    first, second, third = scheduled["upcoming"][:3]

    # Move the second date a day later; the others stay put.
    moved_to = (today + timedelta(weeks=1, days=1)).isoformat()
    by_member = await client.patch(
        f"/api/meetups/{second['id']}", headers=ben.headers, json={"local_date": moved_to}
    )
    moved = await client.patch(
        f"/api/meetups/{second['id']}", headers=ann.headers, json={"local_date": moved_to}
    )
    assert by_member.status_code == 403
    assert moved.json()["edited"] is True
    after_move = await read(client, group, ann)
    assert dates(after_move) == [expected[0], moved_to, *expected[2:]]
    assert [m["id"] for m in after_move["upcoming"]] == [m["id"] for m in scheduled["upcoming"]]

    # Every two weeks, starting later in the evening: untouched dates follow, the moved one
    # stays as it is, and dates that still fit keep their ids.
    biweekly = {**weekly, "every_weeks": 2}
    changed = (
        await client.patch(
            url, headers=ann.headers, json={"schedule": biweekly, "start_time": "20:00:00"}
        )
    ).json()

    every_other = [(today + timedelta(weeks=2 * n)).isoformat() for n in range(8)]
    assert dates(changed) == sorted([*every_other, moved_to])
    by_date = {m["local_date"]: m for m in changed["upcoming"]}
    assert by_date[moved_to]["id"] == second["id"]
    assert by_date[moved_to]["local_time"] == "19:00:00"
    assert by_date[expected[0]]["id"] == first["id"]
    assert by_date[expected[0]]["local_time"] == "20:00:00"
    assert by_date[expected[2]]["id"] == third["id"]

    # Turning the schedule off removes untouched dates but keeps the edited one.
    off = (await client.patch(url, headers=ann.headers, json={"schedule": None})).json()
    assert dates(off) == [moved_to]


async def test_cancelled_dates_stay_cancelled_and_one_offs_come_and_go(
    client: AsyncClient, crew: Crew
) -> None:
    group, (ann, *_rest) = crew
    url = f"/api/groups/{group['id']}"
    today = today_in("UTC")
    schedule = {"kind": "monthly_day", "day": 28, "starts_on": today.isoformat()}
    scheduled = (await client.patch(url, headers=ann.headers, json={"schedule": schedule})).json()
    first = scheduled["upcoming"][0]

    cancelled = await client.patch(
        f"/api/meetups/{first['id']}", headers=ann.headers, json={"status": "cancelled"}
    )
    refused = await client.delete(f"/api/meetups/{first['id']}", headers=ann.headers)
    one_off = await client.post(
        f"{url}/meetups",
        headers=ann.headers,
        json={"local_date": (today + timedelta(days=3)).isoformat(), "location": "Ann's place"},
    )
    group_now = await read(client, group, ann)

    assert cancelled.json()["status"] == "cancelled"
    assert refused.status_code == 409
    assert one_off.status_code == 201
    assert one_off.json()["scheduled"] is False
    assert one_off.json()["local_time"] == "19:00:00"  # the group's default
    statuses = {m["id"]: m["status"] for m in group_now["upcoming"]}
    assert statuses[first["id"]] == "cancelled"
    assert len([m for m in group_now["upcoming"] if m["scheduled"]]) == 8
    assert one_off.json()["id"] in statuses

    removed = await client.delete(f"/api/meetups/{one_off.json()['id']}", headers=ann.headers)
    assert removed.status_code == 204
    remaining = {m["id"] for m in (await read(client, group, ann))["upcoming"]}
    assert one_off.json()["id"] not in remaining


@pytest.fixture
async def games(db_session: AsyncSession) -> None:
    db_session.add_all(
        [
            Game(id=DUO, name="Zyx Duo to Four", min_players=2, max_players=4),
            Game(id=FOUR, name="Zyx Exactly Four", min_players=4, max_players=4),
            Game(id=BIG, name="Zyx Big Table", min_players=5, max_players=6),
            Game(id=UNKNOWN, name="Zyx Mystery"),
            Game(id=BASE, name="Zyx Base", min_players=2, max_players=5),
            Game(
                id=EXPANSION,
                name="Zyx Base: More",
                is_expansion=True,
                base_game_ids=[BASE],
                min_players=2,
                max_players=6,
            ),
        ]
    )
    await db_session.commit()


async def own(client: AsyncClient, who: Person, game_id: int, **answers: Any) -> None:
    response = await client.put(
        f"/api/me/games/{game_id}", headers=who.headers, json={"ownership": "owned", **answers}
    )
    assert response.status_code == 200, response.text


async def test_games_that_fit_follow_who_is_coming(
    client: AsyncClient, crew: Crew, games: None
) -> None:
    group, (ann, ben, cat, dee, eve) = crew
    url = f"/api/groups/{group['id']}"
    await own(client, ann, DUO)
    await own(client, ann, FOUR)
    await own(client, ben, BIG)
    await own(client, ben, UNKNOWN)
    await own(client, dee, BASE)
    await own(client, cat, DUO, will_bring=False)
    created = await client.post(
        f"{url}/meetups", headers=ann.headers, json={"local_date": date.today().isoformat()}
    )
    meetup = created.json()

    async def fitting() -> dict[str, Any]:
        response = await client.get(f"/api/meetups/{meetup['id']}/games", headers=eve.headers)
        assert response.status_code == 200, response.text
        body: dict[str, Any] = response.json()
        return body

    async def answer(who: Person, response: str) -> None:
        sent = await client.put(
            f"/api/meetups/{meetup['id']}/rsvp", headers=who.headers, json={"response": response}
        )
        assert sent.status_code == 200, sent.text

    for who in (ann, ben, cat):
        await answer(who, "yes")
    await answer(dee, "no")
    await answer(eve, "maybe")

    three = await fitting()
    assert three["confirmed"] == 3
    # Dee's game stays home with Dee; only Duo seats exactly three.
    assert [(g["game"]["id"], g["fit"]) for g in three["games"]] == [(DUO, "together")]
    # Cat's copy stays home too; Ann brings hers.
    assert [p["id"] for p in three["games"][0]["bringers"]] == [ann.id]
    assert three["unknown_player_count"] == 1

    await answer(dee, "yes")
    await answer(eve, "yes")
    five = await fitting()
    assert five["confirmed"] == 5
    assert [(g["game"]["id"], g["fit"]) for g in five["games"]] == [
        (BASE, "together"),
        (BIG, "together"),
    ]

    split = await client.patch(url, headers=ann.headers, json={"willing_to_split": True})
    assert split.status_code == 200
    five_split = await fitting()
    # A table of 2 or 3 leaves enough for another; exactly 4 would leave someone alone.
    assert [(g["game"]["id"], g["fit"]) for g in five_split["games"]] == [
        (BASE, "together"),
        (BIG, "together"),
        (DUO, "split"),
    ]

    detail = (await client.get(f"/api/meetups/{meetup['id']}", headers=eve.headers)).json()
    assert (detail["yes"], detail["maybe"], detail["no"]) == (5, 0, 0)
    assert detail["my_response"] == "yes"
    assert detail["no_answer"] == []


async def test_leaving_drops_your_answers_for_dates_to_come(
    client: AsyncClient, crew: Crew
) -> None:
    group, (ann, ben, *_rest) = crew
    url = f"/api/groups/{group['id']}"
    created = await client.post(
        f"{url}/meetups",
        headers=ann.headers,
        json={"local_date": (date.today() + timedelta(days=2)).isoformat()},
    )
    meetup = created.json()
    await client.put(
        f"/api/meetups/{meetup['id']}/rsvp", headers=ben.headers, json={"response": "yes"}
    )

    await client.delete(f"{url}/members/{ben.id}", headers=ben.headers)

    detail = (await client.get(f"/api/meetups/{meetup['id']}", headers=ann.headers)).json()
    assert detail["yes"] == 0
    hidden = await client.get(f"/api/meetups/{meetup['id']}", headers=ben.headers)
    assert hidden.status_code == 404


async def test_group_library(client: AsyncClient, crew: Crew, games: None) -> None:
    group, (ann, ben, cat, *_rest) = crew
    await own(client, ann, BASE, rating=8, notes="Ann's private note")
    await own(client, ben, EXPANSION)
    await own(client, ben, DUO)
    # Cat has rated Duo without owning it.
    await client.put(f"/api/me/games/{DUO}", headers=cat.headers, json={"rating": 6})

    library = (await client.get(f"/api/groups/{group['id']}/games", headers=cat.headers)).json()

    assert [g["game"]["id"] for g in library] == [BASE, DUO]
    base, duo = library
    assert [p["id"] for p in base["owners"]] == [ann.id]
    assert [e["id"] for e in base["expansions"]] == [EXPANSION]
    # Ben's expansion lets Ann's copy seat six.
    assert (base["min_players"], base["max_players"]) == (2, 6)
    assert (duo["min_players"], duo["max_players"]) == (2, 4)
    assert [(a["person"]["id"], a["rating"]) for a in base["answers"]] == [(ann.id, 8)]
    assert "notes" not in base["answers"][0]
    assert {a["person"]["id"]: a["rating"] for a in duo["answers"]} == {ben.id: None, cat.id: 6}


async def test_inviting_someone_picked_from_the_search(
    client: AsyncClient, person: MakePerson
) -> None:
    ann, ben = await person("Ann"), await person("Ben")
    group = await make_group(client, ann)

    sent = await client.post(
        f"/api/groups/{group['id']}/invites", headers=ann.headers, json={"user_id": ben.id}
    )
    both = await client.post(
        f"/api/groups/{group['id']}/invites",
        headers=ann.headers,
        json={"user_id": ben.id, "email": ben.email},
    )

    assert sent.status_code == 201
    assert sent.json()["invite"]["person"]["id"] == ben.id
    assert sent.json()["invite"]["email"] is None
    assert both.status_code == 422
    waiting = (await client.get("/api/groups", headers=ben.headers)).json()["invites"]
    assert [i["group_id"] for i in waiting] == [group["id"]]
