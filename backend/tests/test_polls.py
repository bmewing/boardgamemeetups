from datetime import date
from typing import Any

from httpx import AsyncClient

from app.polls import best_stretches, day_slots
from tests.conftest import MakePerson, Outbox, Person
from tests.test_groups_api import Crew, crew

__all__ = ["crew"]  # fixture used here

DAY1, DAY2 = date(2026, 11, 19), date(2026, 11, 20)


def poll_body(**changes: Any) -> dict[str, Any]:
    return {
        "title": "Trivia night",
        "dates": [DAY2.isoformat(), DAY1.isoformat()],
        "start_time": "18:00",
        "end_time": "21:00",
        "time_zone": "America/New_York",
        "duration_minutes": 120,
        **changes,
    }


async def make_poll(
    client: AsyncClient, crew: Crew, who: Person | None = None, **changes: Any
) -> dict[str, Any]:
    group, people = crew
    response = await client.post(
        f"/api/groups/{group['id']}/polls",
        headers=(who or people[0]).headers,
        json=poll_body(**changes),
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


async def answer(client: AsyncClient, poll: dict[str, Any], who: Person, slots: list[str]) -> Any:
    return await client.put(
        f"/api/polls/{poll['id']}/answer", headers=who.headers, json={"slots": slots}
    )


def at(day: date, hhmm: str) -> str:
    return f"{day.isoformat()}T{hhmm}"


def test_a_day_has_a_slot_every_half_hour_and_can_end_at_midnight() -> None:
    assert day_slots(DAY1, 18 * 60, 20 * 60) == [
        "2026-11-19T18:00",
        "2026-11-19T18:30",
        "2026-11-19T19:00",
        "2026-11-19T19:30",
    ]
    assert day_slots(DAY1, 23 * 60, 24 * 60) == ["2026-11-19T23:00", "2026-11-19T23:30"]


def test_best_times_rank_by_people_then_earliest_and_cover_the_whole_stretch() -> None:
    day1 = day_slots(DAY1, 18 * 60, 21 * 60)
    day2 = day_slots(DAY2, 18 * 60, 21 * 60)
    answers = {
        "ann": {*day1[:4], *day2[2:]},  # 6-8pm Thursday, 7-9pm Friday
        "ben": {*day1[1:4]},  # 6:30-8pm Thursday: can't do two hours
        "cat": set(day2[2:]),  # 7-9pm Friday
    }

    best = best_stretches([day1, day2], answers, 120)

    # Friday 7-9 has two people; the two-hour stretch Ben could make doesn't exist.
    assert [(s.start, s.available) for s in best] == [
        (day2[2], ["ann", "cat"]),
        (day1[0], ["ann"]),
    ]
    assert best[1].missing == ["ben", "cat"]


def test_best_times_do_not_overlap_and_skip_times_nobody_can_make() -> None:
    day = day_slots(DAY1, 18 * 60, 22 * 60)

    best = best_stretches([day], {"ann": set(day)}, 60)

    assert [s.start for s in best] == [day[0], day[2], day[4], day[6]]  # not every half hour
    assert best_stretches([day], {"ann": set()}, 60) == []
    assert best_stretches([day], {}, 60) == []


def test_a_game_longer_than_the_window_uses_the_whole_window() -> None:
    day = day_slots(DAY1, 18 * 60, 19 * 60)

    best = best_stretches([day], {"ann": set(day)}, 240)

    assert best[0].slots == day


async def test_making_a_poll_offers_slots_and_emails_the_group(
    client: AsyncClient, crew: Crew, outbox: Outbox
) -> None:
    _, people = crew

    poll = await make_poll(client, crew, end_time="00:00")

    assert poll["status"] == "open"
    assert [d["date"] for d in poll["days"]] == ["2026-11-19", "2026-11-20"]
    assert poll["days"][0]["slots"][0] == "2026-11-19T18:00"
    assert poll["days"][0]["slots"][-1] == "2026-11-19T23:30"
    assert poll["can_manage"] is True
    assert poll["my_slots"] is None
    assert len(poll["waiting"]) == 5
    assert {email.to for email in outbox.sent} == {p.email for p in people[1:]}


async def test_a_poll_must_have_a_sensible_window(client: AsyncClient, crew: Crew) -> None:
    group, (ann, *_) = crew
    url = f"/api/groups/{group['id']}/polls"
    days = [date.fromordinal(DAY1.toordinal() + i).isoformat() for i in range(28)]
    too_many = [date.fromordinal(DAY1.toordinal() + i).isoformat() for i in range(63)]

    cases: list[dict[str, Any]] = [
        {"start_time": "21:00", "end_time": "18:00"},
        {"start_time": "18:00", "end_time": "18:00"},
        {"start_time": "18:15"},
        {"time_zone": "Nowhere/Here"},
        {"dates": []},
        {"dates": too_many},
        {"duration_minutes": 45},
        {"title": "  "},
    ]
    for changes in cases:
        response = await client.post(url, headers=ann.headers, json=poll_body(**changes))
        assert response.status_code == 422, changes
    ok = await client.post(url, headers=ann.headers, json=poll_body(dates=days))
    assert ok.status_code == 201


async def test_an_answer_replaces_the_last_and_is_sorted_and_deduplicated(
    client: AsyncClient, crew: Crew
) -> None:
    _, (_, ben, *_) = crew
    poll = await make_poll(client, crew)

    response = await answer(
        client, poll, ben, [at(DAY2, "19:00"), at(DAY1, "18:30"), at(DAY1, "18:30")]
    )

    assert response.json()["my_slots"] == [at(DAY1, "18:30"), at(DAY2, "19:00")]
    again = await answer(client, poll, ben, [at(DAY1, "20:00")])
    assert again.json()["my_slots"] == [at(DAY1, "20:00")]


async def test_an_empty_answer_counts_as_answered(client: AsyncClient, crew: Crew) -> None:
    _, (_, ben, *_) = crew
    poll = await make_poll(client, crew)

    response = (await answer(client, poll, ben, [])).json()

    assert response["my_slots"] == []
    assert ben.id in [r["person"]["id"] for r in response["respondents"]]
    assert ben.id not in [p["id"] for p in response["waiting"]]


async def test_answers_must_be_slots_of_an_open_poll(client: AsyncClient, crew: Crew) -> None:
    _, (_, ben, *_) = crew
    poll = await make_poll(client, crew)

    foreign = await answer(client, poll, ben, [at(DAY1, "18:00"), at(DAY1, "22:00")])
    assert foreign.status_code == 422
    assert "2026-11-19T22:00" in foreign.json()["detail"]
    after = (await client.get(f"/api/polls/{poll['id']}", headers=ben.headers)).json()
    assert after["my_slots"] is None  # a refused answer saves nothing
    await client.post(f"/api/polls/{poll['id']}/close", headers=crew[1][0].headers)
    closed = await answer(client, poll, ben, [at(DAY1, "18:00")])
    assert closed.status_code == 409


async def test_best_times_come_from_current_members_only(client: AsyncClient, crew: Crew) -> None:
    group, (ann, ben, cat, *_) = crew
    poll = await make_poll(client, crew)
    stretch = [at(DAY1, h) for h in ("19:00", "19:30", "20:00", "20:30")]
    for who in (ann, ben, cat):
        await answer(client, poll, who, stretch)

    seen = (await client.get(f"/api/polls/{poll['id']}", headers=ann.headers)).json()
    assert {p["id"] for p in seen["best"][0]["available"]} == {ann.id, ben.id, cat.id}
    assert seen["best"][0]["start"] == at(DAY1, "19:00")
    assert seen["best"][0]["end"] == "21:00"
    assert seen["best"][0]["starts_at"].startswith("2026-11-19T19:00:00-05:00")

    await client.delete(f"/api/groups/{group['id']}/members/{cat.id}", headers=ann.headers)
    after = (await client.get(f"/api/polls/{poll['id']}", headers=ann.headers)).json()
    assert len(after["best"][0]["available"]) == 2
    assert cat.id not in [r["person"]["id"] for r in after["respondents"]]


async def test_only_members_can_see_a_poll_and_only_organizers_run_it(
    client: AsyncClient, crew: Crew, person: MakePerson
) -> None:
    group, (ann, ben, *_) = crew
    stranger = await person("Zed")
    poll = await make_poll(client, crew)
    pid = poll["id"]

    assert (await client.get(f"/api/polls/{pid}", headers=stranger.headers)).status_code == 404
    assert (await answer(client, poll, stranger, [])).status_code == 404
    assert (
        await client.get(f"/api/groups/{group['id']}/polls", headers=stranger.headers)
    ).status_code == 404
    made = await client.post(
        f"/api/groups/{group['id']}/polls", headers=ben.headers, json=poll_body()
    )
    assert made.status_code == 403
    for action in ("close", "reopen", "remind"):
        response = await client.post(f"/api/polls/{pid}/{action}", headers=ben.headers)
        assert response.status_code == 403, action
    schedule = await client.post(
        f"/api/polls/{pid}/schedule", headers=ben.headers, json={"start": at(DAY1, "19:00")}
    )
    assert schedule.status_code == 403
    assert (await client.delete(f"/api/polls/{pid}", headers=ben.headers)).status_code == 403
    assert (await client.get(f"/api/polls/{pid}", headers=ben.headers)).json()[
        "can_manage"
    ] is False
    assert (await client.delete(f"/api/polls/{pid}", headers=ann.headers)).status_code == 204
    assert (await client.get(f"/api/polls/{pid}", headers=ann.headers)).status_code == 404


async def test_the_group_page_lists_polls_with_who_has_answered(
    client: AsyncClient, crew: Crew
) -> None:
    group, (ann, ben, *_) = crew
    poll = await make_poll(client, crew)
    await answer(client, poll, ben, [])

    listed = (await client.get(f"/api/groups/{group['id']}/polls", headers=ben.headers)).json()

    [brief] = listed["polls"]
    assert (brief["answered"], brief["members"], brief["i_answered"]) == (1, 5, True)
    assert (brief["first_date"], brief["last_date"]) == ("2026-11-19", "2026-11-20")
    mine = (await client.get(f"/api/groups/{group['id']}/polls", headers=ann.headers)).json()
    assert mine["polls"][0]["i_answered"] is False


async def test_a_reminder_goes_only_to_members_who_have_not_answered(
    client: AsyncClient, crew: Crew, outbox: Outbox
) -> None:
    _, (ann, ben, cat, dee, eve) = crew
    poll = await make_poll(client, crew)
    await answer(client, poll, ben, [])
    outbox.sent.clear()

    response = await client.post(f"/api/polls/{poll['id']}/remind", headers=ann.headers)

    assert response.status_code == 204
    assert {email.to for email in outbox.sent} == {cat.email, dee.email, eve.email}


async def test_scheduling_a_time_makes_a_date_and_closes_the_poll(
    client: AsyncClient, crew: Crew, outbox: Outbox
) -> None:
    group, (ann, ben, *_) = crew
    poll = await make_poll(client, crew)
    outbox.sent.clear()

    bad = await client.post(
        f"/api/polls/{poll['id']}/schedule", headers=ann.headers, json={"start": at(DAY1, "22:00")}
    )
    assert bad.status_code == 422
    response = await client.post(
        f"/api/polls/{poll['id']}/schedule", headers=ann.headers, json={"start": at(DAY1, "19:00")}
    )

    assert response.status_code == 200, response.text
    scheduled = response.json()
    assert scheduled["status"] == "closed"
    meetup = (
        await client.get(f"/api/meetups/{scheduled['meetup_id']}", headers=ben.headers)
    ).json()
    # The group's zone is UTC, the poll's is New York: 7pm there is midnight UTC next day.
    assert meetup["starts_at"].startswith("2026-11-20T00:00:00")
    assert (meetup["local_date"], meetup["local_time"]) == ("2026-11-20", "00:00:00")
    assert meetup["duration_minutes"] == 120
    again = await client.post(
        f"/api/polls/{poll['id']}/schedule", headers=ann.headers, json={"start": at(DAY1, "19:00")}
    )
    assert again.status_code == 409
    assert ben.email in {email.to for email in outbox.sent}
    assert ann.email not in {email.to for email in outbox.sent}
    listed = (await client.get(f"/api/groups/{group['id']}/polls", headers=ben.headers)).json()
    assert listed["polls"][0]["meetup_id"] == scheduled["meetup_id"]


async def test_a_poll_can_be_closed_and_reopened(client: AsyncClient, crew: Crew) -> None:
    _, (ann, ben, *_) = crew
    poll = await make_poll(client, crew)

    closed = await client.post(f"/api/polls/{poll['id']}/close", headers=ann.headers)
    reopened = await client.post(f"/api/polls/{poll['id']}/reopen", headers=ann.headers)

    assert closed.json()["status"] == "closed"
    assert reopened.json()["status"] == "open"
    assert (await answer(client, poll, ben, [])).status_code == 200
