from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app import ics
from app.config import get_settings
from app.models import Meetup
from app.schedule import today_in
from tests.conftest import Person
from tests.test_groups_api import Crew, crew, make_group

__all__ = ["crew"]  # fixture used here


@pytest.fixture(autouse=True)
def app_url() -> Iterator[None]:
    settings = get_settings()
    original = settings.app_url
    settings.app_url = "https://games.example"
    yield
    settings.app_url = original


def events(body: str) -> list[dict[str, str]]:
    """Each VEVENT's properties, with folded lines joined back up."""
    unfolded = body.replace("\r\n ", "")
    found: list[dict[str, str]] = []
    for line in unfolded.split("\r\n"):
        if line == "BEGIN:VEVENT":
            found.append({})
        elif found and ":" in line and line != "END:VEVENT":
            key, value = line.split(":", 1)
            found[-1][key] = value
    return found


async def add_date(
    client: AsyncClient, group: dict[str, Any], who: Person, day: date, **fields: Any
) -> dict[str, Any]:
    response = await client.post(
        f"/api/groups/{group['id']}/meetups",
        headers=who.headers,
        json={"local_date": day.isoformat(), **fields},
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


async def make_feed(client: AsyncClient, who: Person) -> str:
    response = await client.post("/api/me/calendar-feed", headers=who.headers)
    assert response.status_code == 201, response.text
    token: str = response.json()["token"]
    return token


def test_text_is_escaped_and_long_lines_folded() -> None:
    event = ics.Event(
        uid="x@test",
        starts_at=datetime(2026, 11, 12, 1, 0, tzinfo=UTC),
        duration=timedelta(hours=3),
        summary="Games; snacks, etc.",
        updated_at=datetime(2026, 11, 4, tzinfo=UTC),
        description="Line one\nCafé " + "é" * 60,
    )

    body = ics.calendar([event])

    assert all(len(line.encode()) <= 75 for line in body.split("\r\n"))
    (parsed,) = events(body)
    assert parsed["SUMMARY"] == "Games\\; snacks\\, etc."
    assert parsed["DESCRIPTION"] == "Line one\\nCafé " + "é" * 60
    assert (parsed["DTSTART"], parsed["DTEND"]) == ("20261112T010000Z", "20261112T040000Z")


async def test_one_date_as_a_calendar_file(client: AsyncClient, crew: Crew) -> None:
    group, (ann, ben, *_rest) = crew
    await client.patch(
        f"/api/groups/{group['id']}", headers=ann.headers, json={"time_zone": "America/Chicago"}
    )
    meetup = await add_date(
        client,
        group,
        ann,
        date(2026, 12, 3),
        local_time="19:00:00",
        location="12 Elm St, Apt 3",
        notes="Bring snacks",
    )

    response = await client.get(f"/api/meetups/{meetup['id']}/calendar.ics", headers=ben.headers)

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/calendar; charset=utf-8"
    assert response.headers["content-disposition"] == (
        'attachment; filename="thursday-crew-2026-12-03.ics"'
    )
    (event,) = events(response.text)
    assert event["UID"] == f"{meetup['id']}@boardgamemeetups"
    assert event["SUMMARY"] == "Thursday Crew"
    # 7 pm in Chicago, in UTC.
    assert (event["DTSTART"], event["DTEND"]) == ("20261204T010000Z", "20261204T040000Z")
    assert event["LOCATION"] == "12 Elm St\\, Apt 3"
    url = f"https://games.example/meetups/{meetup['id']}"
    assert event["DESCRIPTION"] == f"Bring snacks\\n\\n{url}"
    assert event["URL"] == url
    assert event["STATUS"] == "CONFIRMED"


async def test_the_feed_shows_dates_you_might_go_to(client: AsyncClient, crew: Crew) -> None:
    group, (ann, ben, *_rest) = crew
    other = await make_group(client, ann, name="Not Ben's")
    soon = date.today() + timedelta(days=1)
    going, maybe, unanswered, cant, cancelled = [
        (await add_date(client, group, ann, soon + timedelta(days=i)))["id"] for i in range(5)
    ]
    long_ago = (await add_date(client, group, ann, date.today() - timedelta(days=60)))["id"]
    elsewhere = (await add_date(client, other, ann, soon))["id"]
    for meetup_id, reply in ((going, "yes"), (maybe, "maybe"), (cant, "no")):
        await client.put(
            f"/api/meetups/{meetup_id}/rsvp", headers=ben.headers, json={"response": reply}
        )
    await client.patch(
        f"/api/meetups/{cancelled}", headers=ann.headers, json={"status": "cancelled"}
    )
    token = await make_feed(client, ben)

    response = await client.get(f"/api/calendar/{token}.ics")  # no sign-in

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/calendar; charset=utf-8"
    assert "X-WR-CALNAME:Board game meetups" in response.text
    found = {e["UID"].split("@")[0]: e for e in events(response.text)}
    assert set(found) == {going, maybe, unanswered, cancelled}
    assert cant not in found and long_ago not in found and elsewhere not in found
    assert found[going]["DESCRIPTION"].startswith("You're going.")
    assert found[maybe]["DESCRIPTION"].startswith("You said maybe.")
    assert found[unanswered]["DESCRIPTION"].startswith("You haven't said whether you're coming.")
    assert (found[cancelled]["STATUS"], found[cancelled]["SUMMARY"]) == (
        "CANCELLED",
        "Cancelled: Thursday Crew",
    )
    assert int(found[cancelled]["SEQUENCE"]) >= int(found[going]["SEQUENCE"])


async def test_a_feed_link_can_be_replaced_or_turned_off(client: AsyncClient, crew: Crew) -> None:
    _group, (ann, ben, *_rest) = crew
    assert (await client.get("/api/me/calendar-feed", headers=ben.headers)).json() is None

    first = await make_feed(client, ben)
    second = await make_feed(client, ben)

    assert (await client.get(f"/api/calendar/{first}.ics")).status_code == 404
    assert (await client.get(f"/api/calendar/{second}.ics")).status_code == 200
    shown = (await client.get("/api/me/calendar-feed", headers=ben.headers)).json()
    assert shown["token"] == second
    assert (await client.get("/api/me/calendar-feed", headers=ann.headers)).json() is None

    off = await client.delete("/api/me/calendar-feed", headers=ben.headers)

    assert off.status_code == 204
    assert (await client.get(f"/api/calendar/{second}.ics")).status_code == 404
    assert (await client.get("/api/me/calendar-feed", headers=ben.headers)).json() is None
    assert (await client.get("/api/calendar/made-up.ics")).status_code == 404


async def test_fetching_the_feed_tops_up_scheduled_dates(
    client: AsyncClient, crew: Crew, db_session: AsyncSession
) -> None:
    group, (ann, ben, *_rest) = crew
    today = today_in("UTC")
    weekly = {"kind": "weekly", "weekday": today.weekday(), "starts_on": today.isoformat()}
    await client.patch(f"/api/groups/{group['id']}", headers=ann.headers, json={"schedule": weekly})
    token = await make_feed(client, ben)
    # As if nobody had opened the group's page in months.
    await db_session.execute(delete(Meetup))
    await db_session.commit()

    response = await client.get(f"/api/calendar/{token}.ics")

    assert len(events(response.text)) == 8
