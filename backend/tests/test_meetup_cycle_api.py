from datetime import date, timedelta
from typing import Any

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Game, UserGame
from tests.conftest import Person
from tests.test_groups_api import BASE, BIG, DUO, Crew, crew, games, own
from tests.test_meetup_rsvps import add_date, answer

__all__ = ["crew", "games"]  # fixtures used here

COOP = 990_300_050


async def vote_state(client: AsyncClient, meetup: str, who: Person) -> dict[str, Any]:
    response = await client.get(f"/api/meetups/{meetup}/vote", headers=who.headers)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


async def nominate(client: AsyncClient, meetup: str, who: Person, game_id: int) -> Any:
    return await client.post(
        f"/api/meetups/{meetup}/nominations", headers=who.headers, json={"game_id": game_id}
    )


def by_game(state: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {n["game"]["id"]: n for n in state["nominations"]}


def ids(people: list[dict[str, Any]]) -> list[str]:
    return [p["id"] for p in people]


async def plays_of(db_session: AsyncSession, who: Person, game_id: int) -> int | None:
    db_session.expire_all()
    return await db_session.scalar(
        select(UserGame.plays).where(UserGame.user_id == who.id, UserGame.game_id == game_id)
    )


async def test_vote_lock_and_bring(client: AsyncClient, crew: Crew, games: None) -> None:
    group, (ann, ben, cat, dee, eve) = crew
    await own(client, ann, DUO)
    await own(client, ann, BASE)
    await own(client, ben, DUO, will_bring=False)  # can still be nominated and brought
    meetup = await add_date(client, group, ann, date.today() + timedelta(days=3))
    for who in (ann, ben, cat):
        await answer(client, meetup, who, "yes")
    await answer(client, meetup, dee, "maybe")

    assert (await nominate(client, meetup, dee, DUO)).status_code == 403  # only yes
    assert (await nominate(client, meetup, cat, BIG)).status_code == 422  # nobody owns it
    nominated = await nominate(client, meetup, ben, DUO)
    assert nominated.status_code == 200, nominated.text
    await client.put(
        f"/api/meetups/{meetup}/nominations/{by_game(nominated.json())[DUO]['id']}/vote",
        headers=cat.headers,
    )
    state = (await nominate(client, meetup, ann, BASE)).json()

    assert [n["game"]["id"] for n in state["nominations"]] == [DUO, BASE]  # most votes first
    duo = by_game(state)[DUO]
    assert (ids(duo["votes"]), duo["my_vote"]) == ([ben.id, cat.id], False)
    assert state["nominatable"] == []  # everything someone going owns is up
    locking = {"nomination_ids": [n["id"] for n in state["nominations"]]}
    assert (
        await client.post(f"/api/meetups/{meetup}/lock", headers=ben.headers, json=locking)
    ).status_code == 403

    locked = (
        await client.post(f"/api/meetups/{meetup}/lock", headers=ann.headers, json=locking)
    ).json()

    assert locked["locked"] is True
    picks = by_game(locked)
    # Only Ann owns Base, so it's hers to bring; Duo has two owners going.
    assert picks[BASE]["bring"]["person"]["id"] == ann.id
    assert picks[DUO]["bring"]["person"] is None
    assert ids(picks[DUO]["bring"]["owners_going"]) == [ann.id, ben.id]
    assert (await nominate(client, meetup, cat, DUO)).status_code == 409
    vote_url = f"/api/meetups/{meetup}/nominations/{picks[DUO]['id']}/vote"
    assert (await client.put(vote_url, headers=ann.headers)).status_code == 409

    bring_duo = f"/api/meetups/{meetup}/bring/{DUO}"
    assert (await client.put(bring_duo, headers=cat.headers, json={})).status_code == 422
    claimed = (await client.put(bring_duo, headers=ben.headers, json={})).json()
    assert by_game(claimed)[DUO]["bring"]["person"]["id"] == ben.id

    # Ben drops out: Duo needs a new bringer. Answers stay open after the lock.
    assert (await answer(client, meetup, ben, "no")).status_code == 200
    assert by_game(await vote_state(client, meetup, ann))[DUO]["bring"]["person"] is None
    assert (await answer(client, meetup, ben, "yes")).status_code == 200
    handed = await client.put(bring_duo, headers=ann.headers, json={"user_id": ben.id})
    assert by_game(handed.json())[DUO]["bring"]["person"]["id"] == ben.id

    # Five going is too many for Duo at one table.
    for who in (dee, eve):
        await answer(client, meetup, who, "yes")
    crowded = by_game(await vote_state(client, meetup, ann))
    assert (crowded[DUO]["fits_now"], crowded[BASE]["fits_now"]) == (False, True)
    assert (crowded[DUO]["fit"], crowded[BASE]["fit"]) == (None, "together")
    assert (crowded[DUO]["min_players"], crowded[DUO]["max_players"]) == (2, 4)
    # Happy to split: Duo still seats some of the five, at a second table.
    await client.patch(
        f"/api/groups/{group['id']}", headers=ann.headers, json={"willing_to_split": True}
    )
    split = by_game(await vote_state(client, meetup, ann))
    assert (split[DUO]["fits_now"], split[DUO]["fit"]) == (True, "split")

    unlocked = (await client.post(f"/api/meetups/{meetup}/unlock", headers=ann.headers)).json()
    assert unlocked["locked"] is False
    assert all(not n["picked"] and n["bring"] is None for n in unlocked["nominations"])


async def test_logging_what_was_played(
    client: AsyncClient, crew: Crew, games: None, db_session: AsyncSession
) -> None:
    group, (ann, ben, cat, *_rest) = crew
    db_session.add(
        Game(
            id=COOP,
            name="Zyx Together",
            min_players=1,
            max_players=4,
            mechanics=["Cooperative Game"],
        )
    )
    await db_session.commit()
    await own(client, ann, DUO)
    upcoming = await add_date(client, group, ann, date.today() + timedelta(days=3))
    past = await add_date(client, group, ann, date.today() - timedelta(days=2))
    url = f"/api/meetups/{past}/log"
    log: dict[str, Any] = {
        "attendees": [ann.id, ben.id, cat.id],
        "plays": [
            {"game_id": DUO, "coop": False, "players": [ann.id, ben.id], "winners": [ben.id]},
            {"game_id": COOP, "coop": True, "coop_won": True, "players": [ann.id, cat.id]},
        ],
    }

    assert (await client.put(url, headers=ben.headers, json=log)).status_code == 403
    not_yet = await client.put(f"/api/meetups/{upcoming}/log", headers=ann.headers, json=log)
    assert not_yet.status_code == 409
    bad_winner = {**log, "plays": [{**log["plays"][0], "winners": [cat.id]}]}
    assert (await client.put(url, headers=ann.headers, json=bad_winner)).status_code == 422
    stranger = {**log, "attendees": [*log["attendees"], "00000000-0000-0000-0000-000000000001"]}
    assert (await client.put(url, headers=ann.headers, json=stranger)).status_code == 422

    saved = await client.put(url, headers=ann.headers, json=log)

    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert (body["logged"], body["assumed"]) == (True, False)
    assert ids(body["attendees"]) == [ann.id, ben.id, cat.id]
    plays = {p["game"]["id"]: p for p in body["plays"]}
    assert ids(plays[DUO]["winners"]) == [ben.id]
    assert (plays[COOP]["coop"], plays[COOP]["coop_won"], plays[COOP]["winners"]) == (
        True,
        True,
        [],
    )
    assert await plays_of(db_session, ann, DUO) == 1
    assert await plays_of(db_session, cat, COOP) == 1  # added to Cat's list with one play

    # Correcting the log takes the old plays back off.
    await client.put(url, headers=ann.headers, json={**log, "plays": log["plays"][1:]})
    assert await plays_of(db_session, ann, DUO) == 0
    assert await plays_of(db_session, ann, COOP) == 1

    # The next date's recommendations know it was played last time.
    await client.put(url, headers=ann.headers, json=log)
    await answer(client, upcoming, ann, "yes")
    await answer(client, upcoming, ben, "yes")
    recs = (await client.get(f"/api/meetups/{upcoming}/games", headers=ann.headers)).json()
    (duo,) = [g for g in recs["games"] if g["game"]["id"] == DUO]
    assert "Played last time" in [r["text"] for r in duo["reasons"]]


async def test_a_night_can_repeat_a_game_and_keeps_the_order_played(
    client: AsyncClient, crew: Crew, games: None, db_session: AsyncSession
) -> None:
    group, (ann, ben, *_rest) = crew
    past = await add_date(client, group, ann, date.today() - timedelta(days=1))
    url = f"/api/meetups/{past}/log"
    duo = {"game_id": DUO, "coop": False, "players": [ann.id, ben.id]}
    filler = {"game_id": BIG, "coop": False, "players": [ann.id]}
    log: dict[str, Any] = {
        "attendees": [ann.id, ben.id],
        "plays": [
            {**duo, "winners": [ann.id]},
            filler,
            {**duo, "winners": [ben.id]},
        ],
    }

    saved = await client.put(url, headers=ann.headers, json=log)

    assert saved.status_code == 200, saved.text
    plays = saved.json()["plays"]
    assert [p["game"]["id"] for p in plays] == [DUO, BIG, DUO]  # as played, not A-Z
    assert [ids(p["winners"]) for p in plays] == [[ann.id], [], [ben.id]]
    assert await plays_of(db_session, ben, DUO) == 2  # each round counts

    # Dropping a round takes just that play back off.
    await client.put(url, headers=ann.headers, json={**log, "plays": log["plays"][:2]})
    assert await plays_of(db_session, ben, DUO) == 1


async def test_a_week_later_an_unlogged_pick_counts_as_played(
    client: AsyncClient, crew: Crew, games: None, db_session: AsyncSession
) -> None:
    group, (ann, ben, cat, *_rest) = crew
    await own(client, ann, DUO)
    picked = await add_date(client, group, ann, date.today() - timedelta(days=10))
    unpicked = await add_date(client, group, ann, date.today() - timedelta(days=9))
    recent = await add_date(client, group, ann, date.today() - timedelta(days=3))
    for meetup in (picked, unpicked, recent):
        await answer(client, meetup, ann, "yes")
        await answer(client, meetup, ben, "yes")
    await answer(client, picked, cat, "no")
    for meetup in (picked, recent):
        state = (await nominate(client, meetup, ann, DUO)).json()
        await client.post(
            f"/api/meetups/{meetup}/lock",
            headers=ann.headers,
            json={"nomination_ids": [state["nominations"][0]["id"]]},
        )

    logged = (await client.get(f"/api/meetups/{picked}/log", headers=cat.headers)).json()

    assert (logged["logged"], logged["assumed"]) == (True, True)
    assert ids(logged["attendees"]) == [ann.id, ben.id]
    (play,) = logged["plays"]
    assert (play["game"]["id"], ids(play["players"]), play["winners"]) == (
        DUO,
        [ann.id, ben.id],
        [],
    )
    assert await plays_of(db_session, ben, DUO) == 1
    # No pick, nothing to assume; and the last few days aren't a week yet.
    for meetup in (unpicked, recent):
        log = (await client.get(f"/api/meetups/{meetup}/log", headers=cat.headers)).json()
        assert log["logged"] is False
