from datetime import date, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Mood
from tests.conftest import MakePerson, Person
from tests.test_groups_api import Crew, crew, games, invite, make_group, own

__all__ = ["crew", "games"]  # fixtures used here

DUO, FOUR, BIG = range(990_300_001, 990_300_004)


@pytest.fixture
async def moods(db_session: AsyncSession) -> None:
    db_session.add_all(
        [
            Mood(id="chill", name="Chill", description="", taggable=True, sort_order=1),
            Mood(id="brain", name="Brain-burner", description="", taggable=True, sort_order=2),
            Mood(
                id="something_new",
                name="Something new",
                description="",
                taggable=False,
                sort_order=3,
            ),
            Mood(
                id="no_preference",
                name="No preference",
                description="",
                taggable=False,
                sort_order=4,
            ),
        ]
    )
    await db_session.commit()


async def add_date(client: AsyncClient, group: dict[str, Any], who: Person, day: date) -> str:
    response = await client.post(
        f"/api/groups/{group['id']}/meetups",
        headers=who.headers,
        json={"local_date": day.isoformat(), "location": "12 Elm St, Apt 3"},
    )
    assert response.status_code == 201, response.text
    meetup_id: str = response.json()["id"]
    return meetup_id


async def answer(
    client: AsyncClient, meetup_id: str, who: Person, response: str, **extra: Any
) -> Any:
    return await client.put(
        f"/api/meetups/{meetup_id}/rsvp", headers=who.headers, json={"response": response, **extra}
    )


async def set_limit(client: AsyncClient, group: dict[str, Any], who: Person, limit: int) -> None:
    response = await client.patch(
        f"/api/groups/{group['id']}", headers=who.headers, json={"plus_one_limit": limit}
    )
    assert response.status_code == 200, response.text
    assert response.json()["plus_one_limit"] == limit


async def test_guests_need_the_group_to_allow_them(
    client: AsyncClient, crew: Crew, moods: None
) -> None:
    group, (ann, ben, *_rest) = crew
    meetup = await add_date(client, group, ann, date.today() + timedelta(days=3))
    assert group["plus_one_limit"] == 0

    refused = await answer(client, meetup, ben, "yes", guests=1)
    assert refused.status_code == 422
    assert refused.json()["detail"] == "This group doesn't allow guests."

    members_only = await client.patch(
        f"/api/groups/{group['id']}", headers=ben.headers, json={"plus_one_limit": 2}
    )
    assert members_only.status_code == 403
    await set_limit(client, group, ann, 2)

    assert (await answer(client, meetup, ben, "yes", guests=2)).status_code == 200
    too_many = await answer(client, meetup, ben, "yes", guests=3)
    assert too_many.status_code == 422
    assert too_many.json()["detail"] == "This group allows up to 2 guests each."


async def test_moods_guests_and_the_headcount(
    client: AsyncClient, crew: Crew, moods: None, games: None
) -> None:
    group, (ann, ben, cat, dee, eve) = crew
    await set_limit(client, group, ann, 2)
    meetup = await add_date(client, group, ann, date.today() + timedelta(days=3))
    await own(client, ann, DUO)
    await own(client, ann, FOUR)
    await own(client, ben, BIG)

    # Moods come back in the list's order; a mood that can't go on a game is fine here.
    sent = await answer(client, meetup, ann, "yes", guests=1, moods=["something_new", "chill"])
    assert sent.status_code == 200, sent.text
    assert (sent.json()["my_guests"], sent.json()["my_moods"]) == (1, ["chill", "something_new"])
    await answer(client, meetup, ben, "maybe", guests=2, moods=["no_preference"])
    await answer(client, meetup, cat, "yes", moods=["brain"])
    # A no clears guests and moods.
    await answer(client, meetup, dee, "no", guests=1, moods=["chill"])

    detail = (await client.get(f"/api/meetups/{meetup}", headers=eve.headers)).json()
    by_person = {
        r["person"]["id"]: (r["response"], r["guests"], r["moods"]) for r in detail["rsvps"]
    }
    assert by_person == {
        ann.id: ("yes", 1, ["chill", "something_new"]),
        ben.id: ("maybe", 2, ["no_preference"]),
        cat.id: ("yes", 0, ["brain"]),
        dee.id: ("no", 0, []),
    }
    assert (detail["my_guests"], detail["my_moods"]) == (0, [])
    assert [p["id"] for p in detail["no_answer"]] == [eve.id]
    # Ann, her guest and Cat; a maybe's guests don't count yet.
    assert (detail["yes"], detail["headcount"]) == (2, 3)
    # Who's going, so their pieces can go round the table. (They come in the order people
    # said yes, but every answer in a test shares one transaction, and so one time.)
    assert sorted(p["id"] for p in detail["going"]) == sorted([ann.id, cat.id])
    listed = (await client.get(f"/api/groups/{group['id']}", headers=eve.headers)).json()
    assert [m["headcount"] for m in listed["upcoming"] if m["id"] == meetup] == [3]

    fitting = (await client.get(f"/api/meetups/{meetup}/games", headers=eve.headers)).json()
    assert (fitting["confirmed"], fitting["guests"]) == (3, 1)
    # Three players: Duo fits; Four needs one more; Ben's game stays home with a maybe.
    assert [g["game"]["id"] for g in fitting["games"]] == [DUO]

    await answer(client, meetup, ben, "yes", guests=1, moods=["no_preference"])
    five = (await client.get(f"/api/meetups/{meetup}/games", headers=eve.headers)).json()
    assert (five["confirmed"], five["guests"]) == (5, 2)
    assert [g["game"]["id"] for g in five["games"]] == [BIG]

    # Changing your answer replaces your moods.
    await answer(client, meetup, ann, "maybe", moods=["brain"])
    again = (await client.get(f"/api/meetups/{meetup}", headers=ann.headers)).json()
    assert (again["my_guests"], again["my_moods"]) == (0, ["brain"])


async def test_mood_rules(client: AsyncClient, crew: Crew, moods: None) -> None:
    group, (ann, *_rest) = crew
    meetup = await add_date(client, group, ann, date.today() + timedelta(days=3))

    mixed = await answer(client, meetup, ann, "yes", moods=["no_preference", "chill"])
    unknown = await answer(client, meetup, ann, "yes", moods=["chill", "grumpy"])
    repeated = await answer(client, meetup, ann, "yes", moods=["chill", "chill"])

    assert mixed.status_code == 422
    assert mixed.json()["detail"] == "No preference can't go with other moods."
    assert unknown.status_code == 422
    assert unknown.json()["detail"] == "Unknown moods: grumpy"
    assert repeated.json()["my_moods"] == ["chill"]


async def test_lowering_the_limit_trims_guests_on_dates_to_come(
    client: AsyncClient, crew: Crew
) -> None:
    group, (ann, ben, *_rest) = crew
    await set_limit(client, group, ann, 2)
    past = await add_date(client, group, ann, date.today() - timedelta(days=7))
    coming = await add_date(client, group, ann, date.today() + timedelta(days=7))
    for meetup in (past, coming):
        assert (await answer(client, meetup, ben, "yes", guests=2)).status_code == 200

    await set_limit(client, group, ann, 1)

    def guests(meetup: dict[str, Any]) -> int:
        return int(next(r["guests"] for r in meetup["rsvps"] if r["person"]["id"] == ben.id))

    assert guests((await client.get(f"/api/meetups/{coming}", headers=ben.headers)).json()) == 1
    # Who came last week stays as it was.
    assert guests((await client.get(f"/api/meetups/{past}", headers=ben.headers)).json()) == 2


async def test_only_members_see_where_a_date_is(client: AsyncClient, person: MakePerson) -> None:
    ann, ben = await person("Ann"), await person("Ben")
    group = await make_group(client, ann)
    await client.patch(
        f"/api/groups/{group['id']}", headers=ann.headers, json={"location": "12 Elm St"}
    )
    meetup = await add_date(client, group, ann, date.today() + timedelta(days=3))
    await invite(client, group, ann, ben.email)  # invited, not yet joined

    waiting = (await client.get("/api/groups", headers=ben.headers)).json()["invites"]
    assert len(waiting) == 1
    assert "Elm" not in str(waiting)
    for url in (
        f"/api/groups/{group['id']}",
        f"/api/meetups/{meetup}",
        f"/api/meetups/{meetup}/calendar.ics",
    ):
        response = await client.get(url, headers=ben.headers)
        assert response.status_code == 404, url
        assert "Elm" not in response.text
