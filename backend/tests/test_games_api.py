from collections.abc import Iterable, Iterator
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.games import get_bgg_client
from app.bgg import BggError, GameDetails, SearchHit
from app.main import app
from app.models import Game
from tests.conftest import TokenFactory, bearer

# Ids and names far outside anything in a real BGG catalog, so a local database that already
# holds imported BGG data can't change what these tests see.
BASE_ID, EXPANSION_ID = 990_000_001, 990_000_002


def quokka_details() -> dict[int, GameDetails]:
    return {
        BASE_ID: GameDetails(
            id=BASE_ID,
            name="Quokkazzyx",
            is_expansion=False,
            year_published=2030,
            thumbnail_url="https://example.com/quokka.jpg",
            min_players=1,
            max_players=5,
            min_playtime=40,
            max_playtime=70,
            weight=2.5,
            categories=["Animals"],
            mechanics=["Hand Management"],
            player_count_votes={
                "2": {"best": 10, "recommended": 50, "not_recommended": 5},
                "3": {"best": 80, "recommended": 20, "not_recommended": 1},
                "5": {"best": 1, "recommended": 10, "not_recommended": 60},
                "5+": {"best": 0, "recommended": 0, "not_recommended": 90},
            },
        ),
        EXPANSION_ID: GameDetails(
            id=EXPANSION_ID,
            name="Quokkazzyx: Coastal Expansion",
            is_expansion=True,
            base_game_ids=[BASE_ID],
        ),
    }


class FakeBgg:
    def __init__(self) -> None:
        self.details = quokka_details()
        self.hits = [SearchHit(d.id, d.name, d.year_published) for d in self.details.values()]
        self.searches: list[str] = []
        self.thing_calls: list[list[int]] = []
        self.fail = False

    async def search(self, query: str) -> list[SearchHit]:
        self.searches.append(query)
        if self.fail:
            raise BggError("down")
        return [hit for hit in self.hits if query.lower() in hit.name.lower()]

    async def things(self, ids: Iterable[int]) -> list[GameDetails]:
        ids = list(ids)
        self.thing_calls.append(ids)
        if self.fail:
            raise BggError("down")
        return [self.details[i] for i in ids if i in self.details]


@pytest.fixture
def bgg() -> Iterator[FakeBgg]:
    fake = FakeBgg()
    app.dependency_overrides[get_bgg_client] = lambda: fake
    yield fake


@pytest.fixture
def auth(make_token: TokenFactory) -> dict[str, str]:
    return bearer(make_token("kp_gamer"))


async def test_search_requires_sign_in(client: AsyncClient, bgg: FakeBgg) -> None:
    response = await client.get("/api/games/search", params={"q": "quokkazzyx"})

    assert response.status_code == 401
    assert bgg.searches == []


async def test_search_falls_back_to_bgg_and_fills_in_details(
    client: AsyncClient, bgg: FakeBgg, auth: dict[str, str]
) -> None:
    response = await client.get("/api/games/search", params={"q": "quokkazzyx"}, headers=auth)

    assert response.status_code == 200
    results = response.json()
    assert [r["id"] for r in results] == [BASE_ID, EXPANSION_ID]
    base = results[0]
    assert base["thumbnail_url"] == "https://example.com/quokka.jpg"
    assert (base["min_players"], base["max_players"]) == (1, 5)
    assert base["best_with"] == [3]
    assert results[1]["is_expansion"] is True
    assert bgg.searches == ["quokkazzyx"]
    assert sorted(bgg.thing_calls[0]) == [BASE_ID, EXPANSION_ID]


async def test_known_games_are_searched_locally(
    client: AsyncClient, bgg: FakeBgg, auth: dict[str, str]
) -> None:
    await client.get("/api/games/search", params={"q": "quokkazzyx"}, headers=auth)

    response = await client.get("/api/games/search", params={"q": "quokkazz"}, headers=auth)

    assert response.json()[0]["id"] == BASE_ID
    assert bgg.searches == ["quokkazzyx"]  # no second BGG search
    assert len(bgg.thing_calls) == 1  # details already cached


async def test_search_tolerates_typos(
    client: AsyncClient, bgg: FakeBgg, auth: dict[str, str]
) -> None:
    await client.get("/api/games/search", params={"q": "quokkazzyx"}, headers=auth)

    response = await client.get("/api/games/search", params={"q": "quokazzyx"}, headers=auth)

    assert BASE_ID in [r["id"] for r in response.json()]


async def test_search_can_leave_out_expansions(
    client: AsyncClient, bgg: FakeBgg, auth: dict[str, str]
) -> None:
    await client.get("/api/games/search", params={"q": "quokkazzyx"}, headers=auth)

    response = await client.get(
        "/api/games/search",
        params={"q": "quokkazzyx", "include_expansions": "false"},
        headers=auth,
    )

    assert [r["id"] for r in response.json()] == [BASE_ID]


async def test_search_returns_nothing_when_bgg_is_down(
    client: AsyncClient, bgg: FakeBgg, auth: dict[str, str]
) -> None:
    bgg.fail = True

    response = await client.get("/api/games/search", params={"q": "quokkazzyx"}, headers=auth)

    assert response.status_code == 200
    assert response.json() == []


async def test_game_detail_fetches_unknown_games(
    client: AsyncClient, bgg: FakeBgg, auth: dict[str, str]
) -> None:
    response = await client.get(f"/api/games/{BASE_ID}", headers=auth)

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Quokkazzyx"
    assert body["best_with"] == [3]
    assert body["recommended_with"] == [2, 3]
    assert {"players": "5+", "best": 0, "recommended": 0, "not_recommended": 90} in body[
        "player_count_votes"
    ]
    assert body["bgg_url"] == f"https://boardgamegeek.com/boardgame/{BASE_ID}"


async def test_expansions_name_their_base_game(
    client: AsyncClient, bgg: FakeBgg, auth: dict[str, str]
) -> None:
    response = await client.get(f"/api/games/{EXPANSION_ID}", headers=auth)

    assert response.json()["base_game_ids"] == [BASE_ID]


async def test_fresh_details_are_served_from_cache(
    client: AsyncClient, bgg: FakeBgg, auth: dict[str, str]
) -> None:
    await client.get(f"/api/games/{BASE_ID}", headers=auth)

    await client.get(f"/api/games/{BASE_ID}", headers=auth)

    assert bgg.thing_calls == [[BASE_ID]]


async def test_stale_details_are_refreshed(
    client: AsyncClient, bgg: FakeBgg, auth: dict[str, str], db_session: AsyncSession
) -> None:
    await client.get(f"/api/games/{BASE_ID}", headers=auth)
    await db_session.execute(
        update(Game)
        .where(Game.id == BASE_ID)
        .values(details_fetched_at=datetime.now(UTC) - timedelta(days=90))
    )
    bgg.details[BASE_ID].max_players = 6

    response = await client.get(f"/api/games/{BASE_ID}", headers=auth)

    assert response.json()["max_players"] == 6
    assert len(bgg.thing_calls) == 2


async def test_stale_details_are_still_served_when_bgg_is_down(
    client: AsyncClient, bgg: FakeBgg, auth: dict[str, str], db_session: AsyncSession
) -> None:
    await client.get(f"/api/games/{BASE_ID}", headers=auth)
    await db_session.execute(update(Game).where(Game.id == BASE_ID).values(details_fetched_at=None))
    bgg.fail = True

    response = await client.get(f"/api/games/{BASE_ID}", headers=auth)

    assert response.status_code == 200
    assert response.json()["name"] == "Quokkazzyx"


async def test_unknown_game_is_404(client: AsyncClient, bgg: FakeBgg, auth: dict[str, str]) -> None:
    response = await client.get("/api/games/990000999", headers=auth)

    assert response.status_code == 404


async def test_uncached_game_is_502_when_bgg_is_down(
    client: AsyncClient, bgg: FakeBgg, auth: dict[str, str]
) -> None:
    bgg.fail = True

    response = await client.get(f"/api/games/{BASE_ID}", headers=auth)

    assert response.status_code == 502
