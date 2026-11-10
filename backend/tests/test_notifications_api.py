from datetime import UTC, date, datetime, timedelta
from typing import Any
from urllib.parse import urlsplit

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.email import Email, EmailKind, Message, to_address
from app.models import Meetup
from app.notify import send_due_reminders
from app.schedule import today_in
from tests.conftest import MakePerson, Outbox, Person
from tests.test_groups_api import DUO, Crew, crew, games, invite, make_group, own
from tests.test_meetup_rsvps import add_date, answer

__all__ = ["crew", "games"]  # fixtures used here


def subjects(outbox: Outbox, who: Person) -> list[str]:
    return [email.subject for email in outbox.to(who.email)]


def unsubscribe_path(email: Email) -> str:
    """The API path in the one-click unsubscribe header."""
    url = email.headers["List-Unsubscribe"].strip("<>")
    parts = urlsplit(url)
    return f"{parts.path}?{parts.query}"


async def patch_date(client: AsyncClient, meetup: str, who: Person, **changes: Any) -> None:
    response = await client.patch(f"/api/meetups/{meetup}", headers=who.headers, json=changes)
    assert response.status_code == 200, response.text


async def test_a_friend_request_emails_the_person_asked(
    client: AsyncClient, person: MakePerson, outbox: Outbox
) -> None:
    ann, ben = await person("Ann"), await person("Ben")

    await client.post("/api/friends/requests", headers=ann.headers, json={"email": ben.email})
    await client.post("/api/friends/requests", headers=ann.headers, json={"email": ben.email})
    # Ben asking back accepts Ann's request, which tells nobody.
    await client.post("/api/friends/requests", headers=ben.headers, json={"email": ann.email})

    assert subjects(outbox, ben) == ["Ann wants to be friends"]
    assert outbox.to(ann.email) == []
    email = outbox.to(ben.email)[0]
    assert "/friends" in email.text
    assert "Stop emails about friend requests" in email.text
    assert email.headers["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"


async def test_group_invites_email_people_on_the_app_and_addresses_not_yet_on_it(
    client: AsyncClient, person: MakePerson, outbox: Outbox
) -> None:
    ann, ben, cat = await person("Ann"), await person("Ben"), await person("Cat")
    group = await make_group(client, ann)
    await client.put(f"/api/blocks/{ann.id}", headers=cat.headers)

    await invite(client, group, ann, ben.email.upper())
    await invite(client, group, ann, ben.email)  # already invited: no second email
    await invite(client, group, ann, "newcomer@example.com")
    await invite(client, group, ann, cat.email)  # Cat blocked Ann

    assert subjects(outbox, ben) == ["Ann invited you to Thursday Crew"]
    assert "/groups" in outbox.to(ben.email)[0].text
    newcomer = outbox.to("newcomer@example.com")
    assert [e.subject for e in newcomer] == ["Ann invited you to Thursday Crew"]
    assert "Sign up with this email address (newcomer@example.com)" in newcomer[0].text
    assert newcomer[0].headers == {}  # nothing to unsubscribe from
    assert outbox.to(cat.email) == []


async def test_changing_a_date_tells_whoever_might_come(
    client: AsyncClient, crew: Crew, outbox: Outbox
) -> None:
    group, (ann, ben, cat, dee, eve) = crew
    day = today_in("UTC") + timedelta(days=5)
    meetup = await add_date(client, group, ann, day)
    await answer(client, meetup, ben, "yes")
    await answer(client, meetup, cat, "maybe")
    await answer(client, meetup, dee, "no")
    outbox.sent.clear()

    await patch_date(client, meetup, ann, notes="Bring snacks", duration_minutes=240)
    assert outbox.sent == []  # notes and length don't count

    await patch_date(client, meetup, ann, local_time="18:30:00", location="The library")
    assert {e.to for e in outbox.sent} == {ben.email, cat.email, eve.email}  # not Dee, not Ann
    text = outbox.to(ben.email)[0].text
    assert "Ann changed Thursday Crew's date:" in text
    assert "6:30 pm (was" in text and "7:00 pm)" in text
    assert "Now at The library (was at 12 Elm St, Apt 3)" in text

    outbox.sent.clear()
    await patch_date(client, meetup, ann, status="cancelled")
    assert subjects(outbox, ben) == [f"Cancelled: Thursday Crew on {day:%A}, {day:%B} {day.day}"]
    outbox.sent.clear()
    await patch_date(client, meetup, ann, status="scheduled")
    assert subjects(outbox, eve) == [f"Back on: Thursday Crew on {day:%A}, {day:%B} {day.day}"]

    outbox.sent.clear()
    removed = await client.delete(f"/api/meetups/{meetup}", headers=ann.headers)
    assert removed.status_code == 204
    assert {e.to for e in outbox.sent} == {ben.email, cat.email, eve.email}
    assert outbox.sent[0].subject.startswith("Cancelled: Thursday Crew")
    assert f"/groups/{group['id']}" in outbox.sent[0].text


async def test_past_dates_change_quietly(client: AsyncClient, crew: Crew, outbox: Outbox) -> None:
    group, (ann, *_rest) = crew
    meetup = await add_date(client, group, ann, today_in("UTC") - timedelta(days=3))
    outbox.sent.clear()

    await patch_date(client, meetup, ann, location="Somewhere else")

    assert outbox.sent == []


async def test_a_schedule_change_sends_one_summary(
    client: AsyncClient, crew: Crew, outbox: Outbox
) -> None:
    group, (ann, ben, *_rest) = crew
    url = f"/api/groups/{group['id']}"
    today = today_in("UTC")
    weekly = {"kind": "weekly", "weekday": today.weekday(), "starts_on": today.isoformat()}
    outbox.sent.clear()
    await client.patch(url, headers=ann.headers, json={"schedule": weekly})
    first = outbox.to(ben.email)
    assert [e.subject for e in first] == ["Thursday Crew's dates have changed"]
    assert first[0].text.count("New: ") == 8

    outbox.sent.clear()
    await client.patch(url, headers=ann.headers, json={"description": "Games!"})
    assert outbox.sent == []

    await client.patch(url, headers=ann.headers, json={"schedule": {**weekly, "every_weeks": 2}})
    summary = outbox.to(ben.email)
    assert len(summary) == 1
    assert summary[0].text.count("Dropped: ") == 4
    assert summary[0].text.count("New: ") == 4
    assert outbox.to(ann.email) == []

    outbox.sent.clear()
    await client.patch(url, headers=ann.headers, json={"start_time": "20:00:00"})
    moved = outbox.to(ben.email)[0].text
    assert moved.count("Moved: ") == 8
    assert "8:00 pm (was" in moved


async def test_locking_the_pick_and_handing_out_games(
    client: AsyncClient, crew: Crew, games: None, outbox: Outbox
) -> None:
    group, (ann, ben, cat, dee, _eve) = crew
    await own(client, ben, DUO)
    await own(client, cat, DUO)
    meetup = await add_date(client, group, ann, today_in("UTC") + timedelta(days=3))
    for who in (ann, ben, cat):
        await answer(client, meetup, who, "yes")
    await answer(client, meetup, dee, "maybe")
    nominated = await client.post(
        f"/api/meetups/{meetup}/nominations", headers=ben.headers, json={"game_id": DUO}
    )
    nomination = nominated.json()["nominations"][0]["id"]
    outbox.sent.clear()

    await client.post(
        f"/api/meetups/{meetup}/lock", headers=ann.headers, json={"nomination_ids": [nomination]}
    )

    assert {e.to for e in outbox.sent} == {ben.email, cat.email, dee.email}  # not Ann or Eve
    assert subjects(outbox, dee) == ["Picked for Thursday Crew: Zyx Duo to Four"]
    assert "Zyx Duo to Four: nobody has said they'll bring it yet" in outbox.to(dee.email)[0].text

    outbox.sent.clear()
    bring = f"/api/meetups/{meetup}/bring/{DUO}"
    await client.put(bring, headers=ben.headers, json={})  # claiming it yourself
    assert outbox.sent == []
    await client.put(bring, headers=ann.headers, json={"user_id": cat.id})
    assert subjects(outbox, cat) == ["You're bringing Zyx Duo to Four to Thursday Crew"]
    assert "Ann asked you to bring" in outbox.to(cat.email)[0].text
    outbox.sent.clear()
    await client.put(bring, headers=ann.headers, json={"user_id": cat.id})  # no change
    assert outbox.sent == []


async def test_the_pick_tells_whoever_is_bringing_a_game(
    client: AsyncClient, crew: Crew, games: None, outbox: Outbox
) -> None:
    group, (ann, ben, cat, *_rest) = crew
    await own(client, ben, DUO)
    meetup = await add_date(client, group, ann, today_in("UTC") + timedelta(days=3))
    for who in (ann, ben, cat):
        await answer(client, meetup, who, "yes")
    nominated = await client.post(
        f"/api/meetups/{meetup}/nominations", headers=ben.headers, json={"game_id": DUO}
    )
    nomination = nominated.json()["nominations"][0]["id"]
    await client.patch("/api/me", headers=ben.headers, json={"email_opt_outs": ["pick_locked"]})
    outbox.sent.clear()

    await client.post(
        f"/api/meetups/{meetup}/lock", headers=ann.headers, json={"nomination_ids": [nomination]}
    )

    # Ben turned off pick emails, but he's the only owner going, so he's bringing it.
    ben_text = outbox.to(ben.email)[0].text
    assert "Zyx Duo to Four: you're bringing it" in ben_text
    assert "You're bringing Zyx Duo to Four." in ben_text
    assert "Stop emails about games you're bringing" in ben_text
    assert "Zyx Duo to Four: Ben is bringing it" in outbox.to(cat.email)[0].text


async def soon(client: AsyncClient, group: dict[str, Any], who: Person, hours: int) -> str:
    """A date starting in about `hours` hours (the group is in UTC)."""
    at = (datetime.now(UTC) + timedelta(hours=hours)).replace(second=0, microsecond=0)
    response = await client.post(
        f"/api/groups/{group['id']}/meetups",
        headers=who.headers,
        json={"local_date": at.date().isoformat(), "local_time": at.time().isoformat()},
    )
    assert response.status_code == 201, response.text
    meetup: str = response.json()["id"]
    return meetup


async def test_reminders_go_out_the_day_before_and_only_once(
    client: AsyncClient, crew: Crew, outbox: Outbox
) -> None:
    group, (ann, ben, cat, dee, eve) = crew
    meetup = await soon(client, group, ann, hours=3)
    later = await soon(client, group, ann, hours=30)
    await answer(client, meetup, ann, "yes")
    await answer(client, meetup, ben, "maybe")
    await answer(client, meetup, cat, "no")
    await client.patch("/api/me", headers=eve.headers, json={"email_opt_outs": ["rsvp_reminder"]})
    outbox.sent.clear()

    first = await client.post("/api/notifications/run")
    second = await client.post("/api/notifications/run")

    assert first.json() == {"reminded_dates": 1, "announced_dates": 0, "refreshed_games": 0}
    assert second.json() == {"reminded_dates": 0, "announced_dates": 0, "refreshed_games": 0}
    assert {e.to for e in outbox.sent} == {ben.email, dee.email}
    assert "you said maybe" in outbox.to(ben.email)[0].text
    assert "you haven't said whether you're coming" in outbox.to(dee.email)[0].text
    assert "1 person has said yes so far." in outbox.to(dee.email)[0].text
    assert f"/meetups/{meetup}" in outbox.to(dee.email)[0].text
    assert later not in " ".join(e.text for e in outbox.sent)


async def test_a_moved_date_is_reminded_again_and_a_failed_send_is_retried(
    client: AsyncClient, crew: Crew, outbox: Outbox, db_session: AsyncSession
) -> None:
    group, (ann, ben, *_rest) = crew
    meetup = await soon(client, group, ann, hours=3)
    outbox.failing = True

    assert await send_due_reminders(db_session, outbox) == 0
    assert (
        await db_session.scalar(select(Meetup.reminder_sent_at).where(Meetup.id == meetup)) is None
    )

    outbox.failing = False
    assert await send_due_reminders(db_session, outbox) == 1
    tomorrow = (datetime.now(UTC) + timedelta(hours=5)).replace(second=0, microsecond=0)
    await patch_date(
        client,
        meetup,
        ann,
        local_time=tomorrow.time().isoformat(),
        local_date=tomorrow.date().isoformat(),
    )
    outbox.sent.clear()
    assert await send_due_reminders(db_session, outbox) == 1
    assert ben.email in {e.to for e in outbox.sent}


async def test_unsubscribing_from_an_email_link(
    client: AsyncClient, person: MakePerson, outbox: Outbox
) -> None:
    ann, ben = await person("Ann"), await person("Ben")
    await client.post("/api/friends/requests", headers=ann.headers, json={"email": ben.email})
    email = outbox.to(ben.email)[0]
    token = unsubscribe_path(email).split("/")[-1].split("?")[0]

    seen = await client.get(f"/api/email/unsubscribe/{token}")
    assert seen.json() == {"email_opt_outs": []}
    # A mail app's one-click unsubscribe posts a form body, which is ignored.
    one_click = await client.post(
        unsubscribe_path(email),
        content="List-Unsubscribe=One-Click",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert one_click.status_code == 200, one_click.text
    assert one_click.json() == {"email_opt_outs": ["friend_request"]}
    me = (await client.get("/api/me", headers=ben.headers)).json()
    assert me["email_opt_outs"] == ["friend_request"]

    everything = await client.post(f"/api/email/unsubscribe/{token}")
    assert sorted(everything.json()["email_opt_outs"]) == sorted(k.value for k in EmailKind)
    assert (await client.get("/api/email/unsubscribe/nope")).status_code == 404

    back_on = await client.patch("/api/me", headers=ben.headers, json={"email_opt_outs": []})
    assert back_on.json()["email_opt_outs"] == []
    unknown = await client.patch("/api/me", headers=ben.headers, json={"email_opt_outs": ["spam"]})
    assert unknown.status_code == 422


async def test_emails_escape_what_people_typed() -> None:
    email = to_address(
        "x@example.com",
        Message(subject="Hi", paragraphs=["<b>Ann</b> & co"], link=("Go", "https://a/?x=1&y=2")),
    )

    assert "&lt;b&gt;Ann&lt;/b&gt; &amp; co" in email.html
    assert 'href="https://a/?x=1&amp;y=2"' in email.html
    assert "<b>Ann</b> & co" in email.text


def test_emails_open_with_greg_once_the_site_has_an_address() -> None:
    message = Message(subject="Hi", paragraphs=["Hello"])
    settings = get_settings()
    original = settings.app_url
    try:
        settings.app_url = ""
        assert "<img" not in to_address("x@example.com", message).html

        settings.app_url = "https://games.example"
        email = to_address("x@example.com", message)
        assert '<img src="https://games.example/mascot/grouper-head-128.png"' in email.html
        assert email.html.index("Board Game Group") < email.html.index("Hello")
        assert "Board Game Group" not in email.text
    finally:
        settings.app_url = original


def test_dates_read_naturally() -> None:
    from datetime import time

    from app.models import Group, User
    from app.notify import when

    group = Group(name="G", time_zone="America/New_York")
    here = User(display_name="A", time_zone="America/New_York")
    away = User(display_name="B", time_zone="Europe/London")
    thursday = date(2026, 11, 5)

    assert when(thursday, time(19, 0), group, here) == "Thursday, November 5 at 7:00 pm"
    assert when(thursday, time(0, 5), group, away) == (
        "Thursday, November 5 at 12:05 am (America/New York time)"
    )
