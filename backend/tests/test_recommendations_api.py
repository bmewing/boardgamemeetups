from datetime import date, timedelta
from typing import Any

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Game
from tests.conftest import Person
from tests.test_groups_api import BASE, BIG, DUO, EXPANSION, FOUR, Crew, crew, games, own
from tests.test_meetup_rsvps import add_date, answer, moods

__all__ = ["crew", "games", "moods"]  # fixtures used here


async def answers(client: AsyncClient, who: Person, game_id: int, **fields: Any) -> None:
    response = await client.put(f"/api/me/games/{game_id}", headers=who.headers, json=fields)
    assert response.status_code == 200, response.text


async def test_meetup_games_are_ranked_and_explained(
    client: AsyncClient, crew: Crew, games: None, moods: None, db_session: AsyncSession
) -> None:
    group, (ann, ben, cat, dee, eve) = crew
    await client.patch(
        f"/api/groups/{group['id']}", headers=ann.headers, json={"plus_one_limit": 2}
    )
    duo = await db_session.get(Game, DUO)
    assert duo is not None
    duo.player_count_votes = {"3": {"best": 50, "recommended": 10, "not_recommended": 0}}
    duo.playing_time = 45
    await db_session.commit()
    await db_session.refresh(duo)
    await own(client, ann, DUO, can_teach=True, teach_minutes=10)
    await own(client, ann, BASE, moods=["chill"])
    await own(client, ann, EXPANSION)  # seats 6, so Base does too
    await answers(client, ben, BASE, want_to_play=True)
    await answers(client, cat, DUO, rating=2)
    meetup = await add_date(client, group, ann, date.today() + timedelta(days=3))
    for who in (ann, ben):
        await answer(client, meetup, who, "yes")
    await answer(client, meetup, cat, "yes", moods=["chill"])
    await answer(client, meetup, dee, "maybe", guests=2)
    await answer(client, meetup, eve, "no")

    response = await client.get(f"/api/meetups/{meetup}/games", headers=eve.headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["confirmed"], body["maybes"]) == (3, 3)
    ranked = {g["game"]["id"]: g for g in body["games"]}
    assert list(ranked) == [BASE, DUO]
    base, duo_read = ranked[BASE], ranked[DUO]
    assert (base["min_players"], base["max_players"]) == (2, 6)
    assert [e["id"] for e in base["expansions"]] == [EXPANSION]
    assert [r["text"] for r in base["reasons"]] == [
        "Ben wants to play",
        "Fits the maybes too",  # six with Dee and her guests: only with the expansion
        "Matches Chill",
        "Ann can teach",  # she owns it, and owners count as teachers until they untick it
    ]
    assert [(r["text"], r["tone"]) for r in duo_read["reasons"]] == [
        ("Best at 3", "good"),
        ("Ann can teach (10 min)", "info"),
        ("Group rating 2.0", "info"),  # just Cat's: this game has no BGG rating to lean on
        ("Cat isn't keen (2)", "bad"),
    ]
    assert duo_read["rollup"]["length_minutes"] == 45
    assert duo_read["rollup"]["teach_minutes"] == 10
    assert [p["id"] for p in duo_read["rollup"]["new_to_it"]] == [ben.id]
    assert base["score"] > duo_read["score"]
    assert body["players"] == 3


async def test_trying_another_player_count(
    client: AsyncClient, crew: Crew, games: None, moods: None, db_session: AsyncSession
) -> None:
    group, (ann, ben, cat, dee, eve) = crew
    duo = await db_session.get(Game, DUO)
    assert duo is not None
    duo.player_count_votes = {
        "3": {"best": 50, "recommended": 10, "not_recommended": 0},
        "4": {"best": 0, "recommended": 10, "not_recommended": 50},
    }
    await db_session.commit()
    await db_session.refresh(duo)
    await own(client, ann, DUO)
    await own(client, ann, FOUR)
    await own(client, ben, BIG)
    meetup = await add_date(client, group, ann, date.today() + timedelta(days=3))
    for who in (ann, ben, cat):
        await answer(client, meetup, who, "yes")
    await answer(client, meetup, dee, "maybe")
    url = f"/api/meetups/{meetup}/games"

    async def fitted(**params: int) -> dict[str, Any]:
        response = await client.get(url, headers=eve.headers, params=params)
        assert response.status_code == 200, response.text
        body: dict[str, Any] = response.json()
        return body

    usual = await fitted()
    four = await fitted(players=4)
    six = await fitted(players=6)
    same = await fitted(players=3)

    assert (usual["confirmed"], usual["players"]) == (3, 3)
    assert [g["game"]["id"] for g in usual["games"]] == [DUO]
    usual_reasons = [r["text"] for r in usual["games"][0]["reasons"]]
    assert usual_reasons[:2] == ["Best at 3", "Fits the maybes too"]
    # Fitted and ranked as if four came; the headcount itself doesn't change.
    assert (four["confirmed"], four["players"]) == (3, 4)
    by_id = {g["game"]["id"]: g for g in four["games"]}
    assert set(by_id) == {DUO, FOUR}
    duo_reasons = [r["text"] for r in by_id[DUO]["reasons"]]
    assert "Not great at 4" in duo_reasons
    # The maybes are taken to be among the four, so they give no lift of their own.
    assert "Fits the maybes too" not in duo_reasons
    assert [g["game"]["id"] for g in six["games"]] == [BIG]
    # Asking for the headcount is the same as not asking.
    assert same == usual

    for bad in (0, 31):
        assert (
            await client.get(url, headers=eve.headers, params={"players": bad})
        ).status_code == 422


async def test_the_group_library_combines_everyones_answers(
    client: AsyncClient, crew: Crew, games: None, moods: None
) -> None:
    group, (ann, ben, cat, dee, eve) = crew
    await own(client, ann, DUO, rating=8, can_teach=True, teach_minutes=10, moods=["chill"])
    await answers(client, ben, DUO, rating=6, player_counts=[{"players": 3, "vote": "best"}])
    await answers(client, cat, DUO, want_to_play=True)

    library = (await client.get(f"/api/groups/{group['id']}/games", headers=dee.headers)).json()

    (duo,) = [g for g in library if g["game"]["id"] == DUO]
    roll = duo["rollup"]
    assert (roll["rating"], roll["rated_by"], roll["lowest_rating"]) == (7.0, 2, 6)
    assert roll["best_at"] == [3]
    assert [p["id"] for p in roll["teachers"]] == [ann.id]
    assert {p["id"] for p in roll["new_to_it"]} == {cat.id, dee.id, eve.id}
    assert [(m["mood"], [p["id"] for p in m["people"]]) for m in roll["moods"]] == [
        ("chill", [ann.id])
    ]
    assert [p["id"] for p in roll["want_to_play"]] == [cat.id]
