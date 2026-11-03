from collections.abc import Iterable, Iterator
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.games import get_bgg_client
from app.bgg import GameDetails
from app.main import app
from app.models import Game
from tests.conftest import TokenFactory, bearer

# Names and ids no real BGG game has, so a local catalog can't interfere.
QUOKKA, QUOKKA_OLD, QUOKKA_NEW, FOXES, STUB = (
    990_200_001,
    990_200_002,
    990_200_003,
    990_200_004,
    990_200_005,
)


class FakeBgg:
    def __init__(self) -> None:
        self.thing_calls: list[list[int]] = []

    async def things(self, ids: Iterable[int]) -> list[GameDetails]:
        ids = list(ids)
        self.thing_calls.append(ids)
        return [GameDetails(id=i, name=f"Zyxlooked up {i}", is_expansion=False) for i in ids]


@pytest.fixture
def bgg() -> Iterator[FakeBgg]:
    fake = FakeBgg()
    app.dependency_overrides[get_bgg_client] = lambda: fake
    yield fake


@pytest.fixture
def auth(make_token: TokenFactory) -> dict[str, str]:
    return bearer(make_token("kp_uploader"))


@pytest.fixture(autouse=True)
async def catalog(db_session: AsyncSession) -> None:
    db_session.add_all(
        [
            Game(id=QUOKKA, name="Zyxquokka Quest", year_published=2020, bgg_users_rated=5000),
            # Two games share a name, and neither is clearly the one people mean.
            Game(id=QUOKKA_OLD, name="Zyxwombat", year_published=1990, bgg_users_rated=300),
            Game(id=QUOKKA_NEW, name="Zyxwombat", year_published=2022, bgg_users_rated=200),
            Game(id=FOXES, name="The Zyxfox Experiment", year_published=2023),
        ]
    )
    await db_session.commit()


CSV = (
    "Name,Year,My Rating,Status\n"
    "Zyxquokka Quest,,8,Stack\n"
    "Zyxwombat,,7,\n"
    "Zyxwombat,2022,6,\n"
    '"Zyxfox Experiment, The",,,Small\n'
    "Zyxquoka Qest,,,\n"
)


async def upload(
    client: AsyncClient, auth: dict[str, str], path: str, data: bytes, **params: Any
) -> Any:
    response = await client.post(
        path,
        params={"filename": "games.csv", **params},
        content=data,
        headers={**auth, "Content-Type": "application/octet-stream"},
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_columns_are_shown_with_samples_and_guesses(
    client: AsyncClient, auth: dict[str, str]
) -> None:
    body = await upload(client, auth, "/api/me/games/file-import/columns", CSV.encode())

    assert body["kind"] == "table"
    assert body["headers"] == ["Name", "Year", "My Rating", "Status"]
    assert body["suggested"] == ["name", "year", "rating", None]
    assert body["samples"][0] == ["Zyxquokka Quest", "", "8", "Stack"]
    assert body["row_count"] == 5


async def test_rows_are_matched_with_the_chosen_columns(
    client: AsyncClient, bgg: FakeBgg, auth: dict[str, str]
) -> None:
    body = await upload(
        client,
        auth,
        "/api/me/games/file-import",
        CSV.encode(),
        columns=["name", "year", "rating", "notes"],
        whole_file="owned",
    )

    rows = body["rows"]
    quest, wombat, wombat_2022, foxes, typo = rows
    assert (quest["status"], quest["match"]["id"]) == ("matched", QUOKKA)
    assert quest["values"] == {"rating": 8.0, "notes": "Stack", "ownership": "owned"}
    # Same name, no year, no clear favourite: the user picks.
    assert wombat["status"] == "review"
    assert {c["game"]["id"] for c in wombat["candidates"]} >= {QUOKKA_OLD, QUOKKA_NEW}
    assert (wombat_2022["status"], wombat_2022["match"]["id"]) == ("matched", QUOKKA_NEW)
    assert (foxes["status"], foxes["match"]["id"]) == ("matched", FOXES)  # "…, The"
    assert (typo["status"], typo["match"]["id"]) == ("review", QUOKKA)
    assert bgg.thing_calls == []


@pytest.mark.usefixtures("bgg")
async def test_matching_needs_the_shelf_when_no_column_says(
    client: AsyncClient, auth: dict[str, str]
) -> None:
    response = await client.post(
        "/api/me/games/file-import",
        params={"filename": "games.csv", "columns": ["name", "year", "rating", "notes"]},
        content=CSV.encode(),
        headers={**auth, "Content-Type": "application/octet-stream"},
    )

    assert response.status_code == 422
    assert "owned or on your wishlist" in response.json()["detail"]


async def test_unknown_bgg_ids_are_looked_up(
    client: AsyncClient, bgg: FakeBgg, auth: dict[str, str]
) -> None:
    body = await upload(
        client,
        auth,
        "/api/me/games/file-import",
        f"BGG ID\n{QUOKKA}\n{STUB}\n".encode(),
        columns=["bgg_id"],
        whole_file="neither",
    )

    assert [(r["status"], r["match"]["id"]) for r in body["rows"]] == [
        ("matched", QUOKKA),
        ("matched", STUB),
    ]
    assert bgg.thing_calls == [[STUB]]


@pytest.mark.usefixtures("bgg")
async def test_a_bgg_export_needs_no_columns(client: AsyncClient, auth: dict[str, str]) -> None:
    export = f"objectname,objectid,own,rating\nZyxexport,{STUB},1,7.5\n".encode()

    body = await upload(client, auth, "/api/me/games/file-import", export)

    [row] = body["rows"]
    assert body["kind"] == "bgg_export"
    assert row["status"] == "matched"
    assert row["values"]["ownership"] == "owned"
    assert row["values"]["rating"] == 7.5


async def test_the_preview_never_clears_answers_from_a_partial_file(
    client: AsyncClient, auth: dict[str, str]
) -> None:
    await client.put(
        f"/api/me/games/{QUOKKA}", json={"ownership": "owned", "rating": 9}, headers=auth
    )
    await client.put(f"/api/me/games/{FOXES}", json={"ownership": "owned"}, headers=auth)

    response = await client.post(
        "/api/me/games/file-import/preview",
        json={
            "games": [
                {"game_id": QUOKKA, "values": {"rating": 7}},
                {"game_id": QUOKKA_NEW, "values": {"ownership": "owned"}},
            ]
        },
        headers=auth,
    )

    body = response.json()
    changes = {g["game"]["id"]: g["changes"] for g in body["games"]}
    assert changes[QUOKKA] == [
        {"field": "rating", "current": 9.0, "incoming": 7.0, "kind": "overwrite"}
    ]
    assert QUOKKA_NEW in changes
    assert FOXES not in changes  # not in the file, but a file isn't the whole collection
    assert body["source"] == "file"
    assert body["counts"]["not_on_source"] == 0


async def test_files_over_the_size_limit_are_refused(
    client: AsyncClient, auth: dict[str, str]
) -> None:
    response = await client.post(
        "/api/me/games/file-import/columns",
        params={"filename": "games.csv"},
        content=b"x" * 1_000_001,
        headers={**auth, "Content-Type": "application/octet-stream"},
    )

    assert response.status_code == 413
