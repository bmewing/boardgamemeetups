from collections.abc import Iterable, Iterator
from dataclasses import replace
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.games import get_bgg_client
from app.bgg import BggError, BggStillPreparing, BggUnknownUser, CollectionEntry, GameDetails
from app.main import app
from app.models import Game, Mood, RemovedGame
from tests.conftest import TokenFactory, bearer

# Ids far outside BGG's range, so a local database holding the real catalog can't interfere.
OWNED, WISHED, EXPANSION, MANUAL = 990_100_001, 990_100_002, 990_100_003, 990_100_004


def bgg_collection() -> list[CollectionEntry]:
    return [
        CollectionEntry(
            id=OWNED,
            name="Zyxowned",
            is_expansion=False,
            year_published=2030,
            thumbnail_url="https://example.com/owned.jpg",
            min_players=2,
            max_players=4,
            own=True,
            rating=8.5,
            plays=3,
            comment="Sleeved.",
        ),
        CollectionEntry(
            id=WISHED, name="Zyxwished", is_expansion=False, wishlist_priority=2, want_to_play=True
        ),
        CollectionEntry(id=EXPANSION, name="Zyxowned: More", is_expansion=True, preordered=True),
    ]


class FakeBgg:
    def __init__(self) -> None:
        self.entries = bgg_collection()
        self.usernames: list[str] = []
        self.error: Exception | None = None
        self.thing_calls: list[list[int]] = []

    async def things(self, ids: Iterable[int]) -> list[GameDetails]:
        ids = list(ids)
        self.thing_calls.append(ids)
        if self.error:
            raise self.error
        return [GameDetails(id=i, name=f"Zyx {i}", is_expansion=False, weight=2.0) for i in ids]

    async def collection(self, username: str) -> list[CollectionEntry]:
        self.usernames.append(username)
        if self.error:
            raise self.error
        return self.entries


@pytest.fixture
def bgg() -> Iterator[FakeBgg]:
    fake = FakeBgg()
    app.dependency_overrides[get_bgg_client] = lambda: fake
    yield fake


@pytest.fixture
def auth(make_token: TokenFactory) -> dict[str, str]:
    return bearer(make_token("kp_collector"))


@pytest.fixture
async def with_bgg_username(client: AsyncClient, auth: dict[str, str]) -> None:
    response = await client.patch("/api/me", json={"bgg_username": "collector"}, headers=auth)
    assert response.status_code == 200


async def preview(client: AsyncClient, auth: dict[str, str]) -> dict[str, Any]:
    response = await client.post("/api/me/games/bgg-pull", headers=auth)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def accept_all(preview_body: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": "bgg",
        "changes": [
            {
                "game_id": game["game"]["id"],
                "field": change["field"],
                "expected": change["current"],
                "value": change["incoming"],
            }
            for game in preview_body["games"]
            for change in game["changes"]
        ],
    }


def changes_for(preview_body: dict[str, Any], game_id: int) -> dict[str, dict[str, Any]]:
    [game] = [g for g in preview_body["games"] if g["game"]["id"] == game_id]
    return {change["field"]: change for change in game["changes"]}


async def my_games(client: AsyncClient, auth: dict[str, str]) -> dict[int, dict[str, Any]]:
    response = await client.get("/api/me/games", headers=auth)
    assert response.status_code == 200
    return {row["game"]["id"]: row for row in response.json()}


async def test_pull_needs_a_bgg_username(
    client: AsyncClient, bgg: FakeBgg, auth: dict[str, str]
) -> None:
    response = await client.post("/api/me/games/bgg-pull", headers=auth)

    assert response.status_code == 400
    assert bgg.usernames == []


@pytest.mark.usefixtures("with_bgg_username")
async def test_first_pull_previews_new_games_and_writes_nothing(
    client: AsyncClient, bgg: FakeBgg, auth: dict[str, str]
) -> None:
    body = await preview(client, auth)

    assert bgg.usernames == ["collector"]
    assert body["counts"] == {
        "games_on_source": 3,
        "new_games": 3,
        "fills": 7,
        "overwrites": 0,
        "not_on_source": 0,
        "removed_before": 0,
    }
    owned = changes_for(body, OWNED)
    assert owned["ownership"] == {
        "field": "ownership",
        "current": None,
        "incoming": "owned",
        "kind": "fill",
    }
    assert {name: c["incoming"] for name, c in owned.items()} == {
        "ownership": "owned",
        "rating": 8.5,
        "plays": 3,
        "notes": "Sleeved.",
    }
    assert set(changes_for(body, WISHED)) == {"wishlist_priority", "want_to_play"}
    assert changes_for(body, EXPANSION)["ownership"]["incoming"] == "preordered"
    # The games reached the shared catalog, but the user's list is still empty.
    [owned_game] = [g for g in body["games"] if g["game"]["id"] == OWNED]
    assert owned_game["game"]["thumbnail_url"] == "https://example.com/owned.jpg"
    assert await my_games(client, auth) == {}


@pytest.mark.usefixtures("with_bgg_username")
async def test_applying_a_preview_records_the_games(
    client: AsyncClient, bgg: FakeBgg, auth: dict[str, str]
) -> None:
    response = await client.post(
        "/api/me/games/import", json=accept_all(await preview(client, auth)), headers=auth
    )

    assert response.json() == {"applied": 7, "skipped": []}
    games = await my_games(client, auth)
    assert set(games) == {OWNED, WISHED, EXPANSION}
    owned = games[OWNED]
    assert (owned["ownership"], owned["rating"], owned["plays"]) == ("owned", 8.5, 3)
    assert owned["source"] == "bgg"
    assert owned["will_bring"] is True
    assert owned["game"]["max_players"] == 4
    assert games[WISHED]["wishlist_priority"] == 2
    me = (await client.get("/api/me", headers=auth)).json()
    assert me["bgg_pulled_at"] is not None


@pytest.mark.usefixtures("with_bgg_username")
async def test_second_pull_shows_what_would_be_overwritten(
    client: AsyncClient, bgg: FakeBgg, auth: dict[str, str]
) -> None:
    await client.post(
        "/api/me/games/import", json=accept_all(await preview(client, auth)), headers=auth
    )
    # Edited here since the first pull:
    await client.put(f"/api/me/games/{OWNED}", json={"rating": 6}, headers=auth)
    # Changed on BGG since: rated differently, one game gone, one played more.
    owned, _wished, expansion = bgg.entries
    bgg.entries = [replace(owned, rating=9, plays=1), replace(expansion, plays=2)]

    body = await preview(client, auth)

    owned_changes = changes_for(body, OWNED)
    assert owned_changes["rating"] == {
        "field": "rating",
        "current": 6.0,
        "incoming": 9.0,
        "kind": "overwrite",
    }
    assert "plays" not in owned_changes  # BGG's count is lower; counts only go up
    assert changes_for(body, EXPANSION)["plays"]["kind"] == "fill"
    wished = changes_for(body, WISHED)
    assert {c["kind"] for c in wished.values()} == {"not_on_source"}
    assert wished["wishlist_priority"]["incoming"] is None
    assert body["counts"]["overwrites"] == 1
    assert body["counts"]["not_on_source"] == 1


@pytest.mark.usefixtures("with_bgg_username")
async def test_a_blank_on_bgg_never_clears_an_opinion(
    client: AsyncClient, bgg: FakeBgg, auth: dict[str, str]
) -> None:
    await client.post(
        "/api/me/games/import", json=accept_all(await preview(client, auth)), headers=auth
    )
    bgg.entries = [replace(bgg.entries[0], rating=None, comment=None), *bgg.entries[1:]]

    body = await preview(client, auth)

    assert body["games"] == []


@pytest.mark.usefixtures("with_bgg_username")
async def test_changes_made_after_the_preview_are_not_overwritten(
    client: AsyncClient, bgg: FakeBgg, auth: dict[str, str]
) -> None:
    accepted = accept_all(await preview(client, auth))
    await client.put(f"/api/me/games/{OWNED}", json={"rating": 4}, headers=auth)

    response = await client.post("/api/me/games/import", json=accepted, headers=auth)

    result = response.json()
    assert {"game_id": OWNED, "field": "rating", "reason": "changed since preview"} in result[
        "skipped"
    ]
    assert result["applied"] == 6
    assert (await my_games(client, auth))[OWNED]["rating"] == 4


@pytest.mark.usefixtures("with_bgg_username")
async def test_only_the_kept_changes_are_applied(
    client: AsyncClient, bgg: FakeBgg, auth: dict[str, str]
) -> None:
    accepted = accept_all(await preview(client, auth))
    accepted["changes"] = [c for c in accepted["changes"] if c["game_id"] == OWNED]

    await client.post("/api/me/games/import", json=accepted, headers=auth)

    assert set(await my_games(client, auth)) == {OWNED}


async def test_import_rejects_values_that_dont_fit_the_field(
    client: AsyncClient, auth: dict[str, str]
) -> None:
    response = await client.post(
        "/api/me/games/import",
        json={
            "source": "bgg",
            "changes": [{"game_id": OWNED, "field": "rating", "expected": None, "value": 11}],
        },
        headers=auth,
    )

    assert response.status_code == 422


@pytest.mark.usefixtures("with_bgg_username")
@pytest.mark.parametrize(
    ("error", "expected_status"),
    [(BggUnknownUser("collector"), 404), (BggStillPreparing("queued"), 503)],
)
async def test_pull_explains_bgg_problems(
    client: AsyncClient,
    bgg: FakeBgg,
    auth: dict[str, str],
    error: Exception,
    expected_status: int,
) -> None:
    bgg.error = error

    response = await client.post("/api/me/games/bgg-pull", headers=auth)

    assert response.status_code == expected_status


@pytest.fixture
async def manual_game(db_session: AsyncSession) -> int:
    db_session.add(Game(id=MANUAL, name="Zyxmanual", year_published=2030))
    await db_session.commit()
    return MANUAL


async def test_add_edit_and_remove_a_game_by_hand(
    client: AsyncClient, auth: dict[str, str], manual_game: int
) -> None:
    response = await client.put(
        f"/api/me/games/{manual_game}",
        json={"rating": 7.5, "can_teach": True, "teach_minutes": 20},
        headers=auth,
    )

    assert response.status_code == 200
    row = response.json()
    assert (row["rating"], row["can_teach"], row["teach_minutes"]) == (7.5, True, 20)
    assert (row["ownership"], row["want_to_play"], row["plays"]) == (None, False, 0)
    assert row["source"] == "manual"

    response = await client.put(
        f"/api/me/games/{manual_game}", json={"playtime_feel": "longer"}, headers=auth
    )
    assert (response.json()["playtime_feel"], response.json()["rating"]) == ("longer", 7.5)

    response = await client.delete(f"/api/me/games/{manual_game}", headers=auth)
    assert response.status_code == 204
    assert await my_games(client, auth) == {}


async def test_teaching_needs_a_teach_time(
    client: AsyncClient, auth: dict[str, str], manual_game: int
) -> None:
    response = await client.put(
        f"/api/me/games/{manual_game}", json={"can_teach": True}, headers=auth
    )

    assert response.status_code == 422


@pytest.fixture
async def moods(db_session: AsyncSession) -> None:
    db_session.add_all(
        [
            Mood(id="zz_chill", name="Chill", description="", taggable=True, sort_order=1),
            Mood(id="zz_laughs", name="Laughs", description="", taggable=True, sort_order=2),
            Mood(id="zz_new", name="Something new", description="", taggable=False, sort_order=3),
        ]
    )
    await db_session.commit()


async def test_player_counts_replace_the_whole_list(
    client: AsyncClient, auth: dict[str, str], manual_game: int
) -> None:
    url = f"/api/me/games/{manual_game}"
    response = await client.put(
        url,
        json={
            "player_counts": [
                {"players": 4, "vote": "recommended"},
                {"players": 3, "vote": "best"},
            ]
        },
        headers=auth,
    )

    assert response.status_code == 200, response.text
    assert response.json()["player_counts"] == [
        {"players": 3, "vote": "best"},
        {"players": 4, "vote": "recommended"},
    ]
    assert response.json()["source"] == "manual"

    # 3 changes its vote, 4 goes blank, 5 is new; other fields are left alone.
    response = await client.put(
        url,
        json={
            "rating": 6,
            "player_counts": [
                {"players": 3, "vote": "recommended"},
                {"players": 5, "vote": "not_recommended"},
            ],
        },
        headers=auth,
    )
    assert response.status_code == 200, response.text
    assert response.json()["player_counts"] == [
        {"players": 3, "vote": "recommended"},
        {"players": 5, "vote": "not_recommended"},
    ]

    response = await client.put(url, json={"notes": "Fun."}, headers=auth)
    assert len(response.json()["player_counts"]) == 2
    assert response.json()["rating"] == 6

    response = await client.put(url, json={"player_counts": []}, headers=auth)
    assert response.json()["player_counts"] == []


@pytest.mark.parametrize(
    "player_counts",
    [
        None,
        [{"players": 0, "vote": "best"}],
        [{"players": 3, "vote": "great"}],
        [{"players": 3, "vote": "best"}, {"players": 3, "vote": "recommended"}],
    ],
)
async def test_player_counts_must_make_sense(
    client: AsyncClient, auth: dict[str, str], manual_game: int, player_counts: Any
) -> None:
    response = await client.put(
        f"/api/me/games/{manual_game}", json={"player_counts": player_counts}, headers=auth
    )

    assert response.status_code == 422
    assert await my_games(client, auth) == {}


async def test_moods_replace_the_whole_list(
    client: AsyncClient, auth: dict[str, str], manual_game: int, moods: None
) -> None:
    url = f"/api/me/games/{manual_game}"
    response = await client.put(
        url, json={"moods": ["zz_laughs", "zz_chill", "zz_laughs"]}, headers=auth
    )

    assert response.status_code == 200, response.text
    assert response.json()["moods"] == ["zz_chill", "zz_laughs"]

    response = await client.put(url, json={"moods": ["zz_laughs"]}, headers=auth)
    assert response.json()["moods"] == ["zz_laughs"]

    response = await client.put(url, json={"moods": []}, headers=auth)
    assert response.json()["moods"] == []


@pytest.mark.parametrize("mood", ["zz_new", "zz_nonexistent"])
async def test_only_taggable_moods_go_on_a_game(
    client: AsyncClient, auth: dict[str, str], manual_game: int, moods: None, mood: str
) -> None:
    response = await client.put(
        f"/api/me/games/{manual_game}", json={"moods": ["zz_chill", mood]}, headers=auth
    )

    assert response.status_code == 422
    assert mood in response.json()["detail"]
    assert await my_games(client, auth) == {}


async def test_unknown_games_cant_be_added(client: AsyncClient, auth: dict[str, str]) -> None:
    response = await client.put("/api/me/games/990199999", json={"rating": 5}, headers=auth)

    assert response.status_code == 404


async def test_moods_are_listed_in_order(
    client: AsyncClient, auth: dict[str, str], db_session: AsyncSession
) -> None:
    db_session.add_all(
        [
            Mood(id="zz_b", name="B", description="", taggable=False, sort_order=2),
            Mood(id="zz_a", name="A", description="", taggable=True, sort_order=1),
        ]
    )
    await db_session.commit()

    response = await client.get("/api/moods", headers=auth)

    assert [m["id"] for m in response.json()] == ["zz_a", "zz_b"]


@pytest.mark.usefixtures("with_bgg_username")
async def test_details_are_filled_in_for_pulled_games(
    client: AsyncClient, bgg: FakeBgg, auth: dict[str, str]
) -> None:
    await client.post(
        "/api/me/games/import", json=accept_all(await preview(client, auth)), headers=auth
    )

    response = await client.post("/api/me/games/fill-details", headers=auth)

    assert response.json() == {"filled": 3, "remaining": 0}
    assert sorted(bgg.thing_calls[0]) == [OWNED, WISHED, EXPANSION]
    assert (await my_games(client, auth))[OWNED]["game"]["weight"] == 2.0


@pytest.mark.usefixtures("with_bgg_username")
async def test_filling_details_stops_cleanly_when_bgg_is_down(
    client: AsyncClient, bgg: FakeBgg, auth: dict[str, str]
) -> None:
    await client.post(
        "/api/me/games/import", json=accept_all(await preview(client, auth)), headers=auth
    )
    bgg.error = BggError("down")

    response = await client.post("/api/me/games/fill-details", headers=auth)

    assert response.json() == {"filled": 0, "remaining": 3}


@pytest.fixture
async def base_with_expansions(db_session: AsyncSession) -> tuple[int, int, int]:
    base, expansion, unrelated = 990_100_010, 990_100_011, 990_100_012
    db_session.add_all(
        [
            Game(id=base, name="Zyxbase"),
            Game(id=expansion, name="Zyxbase: More", is_expansion=True, base_game_ids=[base]),
            Game(id=unrelated, name="Zyxother", is_expansion=True, base_game_ids=[OWNED]),
        ]
    )
    await db_session.commit()
    return base, expansion, unrelated


async def test_removing_a_game_can_take_its_expansions(
    client: AsyncClient, auth: dict[str, str], base_with_expansions: tuple[int, int, int]
) -> None:
    base, expansion, unrelated = base_with_expansions
    for game_id in base_with_expansions:
        await client.put(f"/api/me/games/{game_id}", json={"ownership": "owned"}, headers=auth)

    response = await client.delete(
        f"/api/me/games/{base}",
        params={"expansions": [expansion, unrelated]},
        headers=auth,
    )

    assert response.status_code == 204
    # The unrelated game was asked for but isn't an expansion of this one, so it stays.
    assert set(await my_games(client, auth)) == {unrelated}


async def test_removing_a_game_leaves_its_expansions_by_default(
    client: AsyncClient, auth: dict[str, str], base_with_expansions: tuple[int, int, int]
) -> None:
    base, expansion, _unrelated = base_with_expansions
    for game_id in (base, expansion):
        await client.put(f"/api/me/games/{game_id}", json={"ownership": "owned"}, headers=auth)

    await client.delete(f"/api/me/games/{base}", headers=auth)

    assert set(await my_games(client, auth)) == {expansion}


@pytest.mark.usefixtures("with_bgg_username")
async def test_games_removed_here_are_flagged_on_the_next_pull(
    client: AsyncClient, bgg: FakeBgg, auth: dict[str, str]
) -> None:
    await client.post(
        "/api/me/games/import", json=accept_all(await preview(client, auth)), headers=auth
    )
    await client.delete(f"/api/me/games/{WISHED}", headers=auth)

    body = await preview(client, auth)

    [wished] = body["games"]
    assert wished["game"]["id"] == WISHED
    assert (wished["is_new"], wished["removed_before"]) == (True, True)
    assert body["counts"]["new_games"] == 0
    assert body["counts"]["fills"] == 0
    assert body["counts"]["removed_before"] == 1


@pytest.mark.usefixtures("with_bgg_username")
async def test_keeping_a_removed_game_in_a_pull_adds_it_back_for_good(
    client: AsyncClient, bgg: FakeBgg, auth: dict[str, str]
) -> None:
    await client.post(
        "/api/me/games/import", json=accept_all(await preview(client, auth)), headers=auth
    )
    await client.delete(f"/api/me/games/{WISHED}", headers=auth)

    await client.post(
        "/api/me/games/import", json=accept_all(await preview(client, auth)), headers=auth
    )
    await client.delete(f"/api/me/games/{OWNED}", headers=auth)
    body = await preview(client, auth)

    assert {g["game"]["id"]: g["removed_before"] for g in body["games"]} == {OWNED: True}


async def test_adding_a_removed_game_by_hand_clears_the_removal(
    client: AsyncClient, auth: dict[str, str], manual_game: int, db_session: AsyncSession
) -> None:
    await client.put(f"/api/me/games/{manual_game}", json={"rating": 5}, headers=auth)
    await client.delete(f"/api/me/games/{manual_game}", headers=auth)
    assert len(list(await db_session.scalars(select(RemovedGame)))) == 1

    await client.put(f"/api/me/games/{manual_game}", json={"rating": 6}, headers=auth)

    assert list(await db_session.scalars(select(RemovedGame))) == []
