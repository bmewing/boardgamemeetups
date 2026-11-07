"""Games people add that aren't on BGG."""

import uuid
from typing import Any

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.collection import diff_import
from app.file_import import FileRow
from app.matching import MatchStatus, match_rows
from app.models import Game, Ownership, Source, UserGame
from tests.conftest import MakePerson, Person
from tests.test_games_api import FakeBgg, bgg

__all__ = ["bgg"]  # fixtures used here

# A name no real game has, so a local BGG catalog can't interfere.
HEIST = {"name": "Zyxhomebrew Heist", "min_players": 2, "max_players": 5, "max_playtime": 45}


async def add_game(client: AsyncClient, who: Person, **body: Any) -> Any:
    response = await client.post("/api/games", headers=who.headers, json=body)
    assert response.status_code == 201, response.text
    return response.json()


async def search(client: AsyncClient, who: Person, q: str) -> list[int]:
    response = await client.get("/api/games/search", headers=who.headers, params={"q": q})
    assert response.status_code == 200, response.text
    return [g["id"] for g in response.json()]


async def test_adding_a_game_puts_it_in_your_list_without_asking_bgg(
    client: AsyncClient, bgg: FakeBgg, person: MakePerson
) -> None:
    ann = await person("Ann")

    game = await add_game(client, ann, **HEIST)
    second = await add_game(client, ann, name="Zyxhomebrew Heist 2")

    assert game["id"] < 0 and second["id"] < game["id"]
    assert game["is_custom"] is True
    assert game["bgg_url"] is None
    assert game["created_by_id"] == ann.id
    assert (game["min_players"], game["max_players"], game["playing_time"]) == (2, 5, 45)
    mine = (await client.get("/api/me/games", headers=ann.headers)).json()
    assert {(g["game"]["id"], g["ownership"]) for g in mine} == {
        (game["id"], "owned"),
        (second["id"], "owned"),
    }
    page = await client.get(f"/api/games/{game['id']}", headers=ann.headers)
    assert page.status_code == 200
    assert page.json()["name"] == "Zyxhomebrew Heist"
    assert bgg.thing_calls == []


async def test_others_find_it_through_people_not_search(
    client: AsyncClient, bgg: FakeBgg, person: MakePerson
) -> None:
    ann, ben = await person("Ann"), await person("Ben")
    game = await add_game(client, ann, **HEIST)

    # It's not in anyone's search but the people who have it.
    assert await search(client, ben, "zyxhomebrew") == []
    assert await search(client, ann, "zyxhomebrew") == [game["id"]]

    # Ben sees it in Ann's games, opens it, and adds it to his list.
    assert (await client.get(f"/api/games/{game['id']}", headers=ben.headers)).status_code == 200
    added = await client.put(
        f"/api/me/games/{game['id']}", headers=ben.headers, json={"want_to_play": True}
    )
    assert added.status_code == 200, added.text
    assert added.json()["game"]["is_custom"] is True
    assert await search(client, ben, "zyxhomebrew") == [game["id"]]
    # And takes it off again.
    removed = await client.delete(f"/api/me/games/{game['id']}", headers=ben.headers)
    assert removed.status_code == 204
    assert bgg.thing_calls == []


async def test_only_whoever_added_it_can_change_it(
    client: AsyncClient, bgg: FakeBgg, person: MakePerson, db_session: AsyncSession
) -> None:
    ann, ben = await person("Ann"), await person("Ben")
    game = await add_game(client, ann, **HEIST)
    path = f"/api/games/{game['id']}"

    refused = await client.put(path, headers=ben.headers, json={"name": "Ben's Heist"})
    changed = await client.put(
        path, headers=ann.headers, json={"name": "Zyxhomebrew Heist", "year_published": 2026}
    )

    assert refused.status_code == 403
    assert changed.status_code == 200
    # Everything is sent each time; what's left out is cleared.
    assert (changed.json()["year_published"], changed.json()["max_players"]) == (2026, None)

    db_session.add(Game(id=990_400_001, name="Zyxreal Game"))
    await db_session.commit()
    bgg_game = await client.put("/api/games/990400001", headers=ann.headers, json={"name": "X"})
    assert bgg_game.status_code == 403


async def test_ranges_must_be_in_order(client: AsyncClient, person: MakePerson) -> None:
    ann = await person("Ann")

    players = await client.post(
        "/api/games", headers=ann.headers, json={"name": "X", "min_players": 4, "max_players": 2}
    )
    blank = await client.post("/api/games", headers=ann.headers, json={"name": "   "})

    assert players.status_code == 422
    assert blank.status_code == 422


async def test_an_unknown_negative_id_is_not_asked_of_bgg(
    client: AsyncClient, bgg: FakeBgg, person: MakePerson
) -> None:
    ann = await person("Ann")

    response = await client.get("/api/games/-999999", headers=ann.headers)

    assert response.status_code == 404
    assert bgg.thing_calls == []


async def test_imports_never_match_it(
    client: AsyncClient, bgg: FakeBgg, person: MakePerson, db_session: AsyncSession
) -> None:
    ann = await person("Ann")
    game = await add_game(client, ann, **HEIST)

    [by_name, by_id] = await match_rows(
        db_session,
        bgg,  # type: ignore[arg-type]
        [FileRow(line=2, name="Zyxhomebrew Heist"), FileRow(line=3, bgg_id=game["id"])],
    )

    assert (by_name.status, by_name.candidates) == (MatchStatus.UNMATCHED, [])
    assert by_id.status == MatchStatus.UNMATCHED
    assert bgg.thing_calls == []


def test_a_bgg_pull_leaves_it_alone() -> None:
    user_id = uuid.uuid4()
    rows = {
        game_id: UserGame(
            user_id=user_id, game_id=game_id, ownership=Ownership.OWNED, source=Source.MANUAL
        )
        for game_id in (-1, 990_400_002)
    }

    diffs = diff_import(rows, {}, mirrored=frozenset({"ownership"}))

    # The BGG game is missing from BGG's list, so it's offered for clearing; the other isn't.
    assert [d.game_id for d in diffs] == [990_400_002]
