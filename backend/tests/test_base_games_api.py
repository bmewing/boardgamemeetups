from collections.abc import Iterable, Iterator
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.games import get_bgg_client
from app.bgg import GameDetails
from app.main import app
from app.models import Game
from tests.conftest import TokenFactory, bearer

NOW = datetime.now(UTC)
# Ids far outside BGG's range, so a local catalog can't interfere.
BASE, OWNED_BASE, EXP_A, EXP_B, EXP_OWNED_BASE, MULTI, FIT_1, FIT_2, UNFETCHED, LATE_BASE = range(
    990_300_001, 990_300_011
)


class FakeBgg:
    def __init__(self) -> None:
        self.thing_calls: list[list[int]] = []

    async def things(self, ids: Iterable[int]) -> list[GameDetails]:
        ids = list(ids)
        self.thing_calls.append(ids)
        found = []
        for i in ids:
            if i == UNFETCHED:
                found.append(
                    GameDetails(
                        id=i,
                        name="Zyxlate: Expansion",
                        is_expansion=True,
                        base_game_ids=[LATE_BASE],
                    )
                )
            elif i == LATE_BASE:
                found.append(GameDetails(id=i, name="Zyxlate", is_expansion=False))
        return found


@pytest.fixture
def bgg() -> Iterator[FakeBgg]:
    fake = FakeBgg()
    app.dependency_overrides[get_bgg_client] = lambda: fake
    yield fake


@pytest.fixture
def auth(make_token: TokenFactory) -> dict[str, str]:
    return bearer(make_token("kp_expansions"))


def expansion(game_id: int, name: str, bases: list[int]) -> Game:
    return Game(
        id=game_id, name=name, is_expansion=True, base_game_ids=bases, details_fetched_at=NOW
    )


@pytest.fixture
async def collection(client: AsyncClient, auth: dict[str, str], db_session: AsyncSession) -> None:
    db_session.add_all(
        [
            Game(id=BASE, name="Zyxbase", bgg_users_rated=900, details_fetched_at=NOW),
            Game(id=OWNED_BASE, name="Zyxowned", details_fetched_at=NOW),
            Game(id=FIT_1, name="Zyxfit One", bgg_users_rated=10),
            Game(id=FIT_2, name="Zyxfit Two", bgg_users_rated=5000),
            expansion(EXP_A, "Zyxbase: Alpha", [BASE]),
            expansion(EXP_B, "Zyxbase: Beta", [BASE]),
            expansion(EXP_OWNED_BASE, "Zyxowned: More", [OWNED_BASE]),
            expansion(MULTI, "Zyxfit: Adventures", [FIT_1, FIT_2]),
            Game(id=UNFETCHED, name="Zyxlate: Expansion", is_expansion=True),
        ]
    )
    await db_session.commit()
    for game_id in (OWNED_BASE, EXP_A, EXP_B, EXP_OWNED_BASE, MULTI, UNFETCHED):
        await client.put(f"/api/me/games/{game_id}", json={"ownership": "owned"}, headers=auth)
    # On the wishlist, not owned: still suggested, and marked as wishlisted.
    await client.put(f"/api/me/games/{BASE}", json={"wishlist_priority": 2}, headers=auth)


@pytest.mark.usefixtures("collection")
async def test_suggests_base_games_of_owned_expansions(
    client: AsyncClient, bgg: FakeBgg, auth: dict[str, str]
) -> None:
    response = await client.post("/api/me/games/missing-base-games", headers=auth)

    body = response.json()
    by_id = {s["game"]["id"]: s for s in body["suggestions"]}
    assert list(by_id) == [BASE, LATE_BASE]  # two expansions before one
    assert [e["name"] for e in by_id[BASE]["expansions"]] == ["Zyxbase: Alpha", "Zyxbase: Beta"]
    assert by_id[BASE]["on_wishlist"] is True
    assert by_id[BASE]["ownership"] is None
    # The unfetched expansion was looked up, and its base game recorded from BGG.
    assert bgg.thing_calls == [[UNFETCHED], [LATE_BASE]]
    assert body["unchecked"] == 0
    [choice] = body["choices"]
    assert choice["expansion"]["id"] == MULTI
    assert [g["id"] for g in choice["options"]] == [FIT_2, FIT_1]  # best known first
    assert choice["option_count"] == 2


@pytest.mark.usefixtures("collection", "bgg")
async def test_not_interested_hides_a_suggestion(client: AsyncClient, auth: dict[str, str]) -> None:
    # Not in the list (only wishlisted here, so remove it first) and then marked unwanted.
    await client.delete(f"/api/me/games/{BASE}", headers=auth)

    body = (await client.post("/api/me/games/missing-base-games", headers=auth)).json()

    assert BASE not in {s["game"]["id"] for s in body["suggestions"]}
    assert body["hidden"] == 1


@pytest.mark.usefixtures("collection", "bgg")
async def test_a_game_not_in_the_list_can_be_marked_not_interested(
    client: AsyncClient, auth: dict[str, str]
) -> None:
    response = await client.delete(f"/api/me/games/{FIT_2}", headers=auth)
    body = (await client.post("/api/me/games/missing-base-games", headers=auth)).json()

    assert response.status_code == 204
    [choice] = body["choices"]
    assert [g["id"] for g in choice["options"]] == [FIT_1]
