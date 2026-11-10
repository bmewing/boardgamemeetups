from collections.abc import Iterable, Iterator

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.games import get_bgg_client
from app.bgg import BggError, RpgSystemDetails, RpgSystemStub, SearchHit
from app.main import app
from app.models import RpgSystem
from tests.conftest import MakePerson

# Ids and names far outside anything on RPGGeek.
GLOOM, MIRE, SHARD = 990_500_001, 990_500_002, 990_500_003
BOOK, OTHER_BOOK = 990_600_001, 990_600_002


class FakeRpgGeek:
    """Two books: one named like its system, one ("Wayfarer's Lantern") that isn't."""

    def __init__(self) -> None:
        self.books = [
            SearchHit(BOOK, "Gloomzyx Core Rules", 2030),
            SearchHit(OTHER_BOOK, "Wayfarer's Lantern", 2031),
        ]
        self.systems = {
            BOOK: RpgSystemStub(GLOOM, "Gloomzyx"),
            OTHER_BOOK: RpgSystemStub(MIRE, "Mirequoll"),
        }
        self.details = {
            GLOOM: RpgSystemDetails(GLOOM, "Gloomzyx", "Grim & dark", "https://e.com/t.jpg"),
            MIRE: RpgSystemDetails(MIRE, "Mirequoll", None, "https://e.com/m.jpg"),
        }
        self.searches: list[str] = []
        self.family_calls: list[list[int]] = []
        self.fail = False

    async def search_rpg_items(self, query: str) -> list[SearchHit]:
        self.searches.append(query)
        if self.fail:
            raise BggError("down")
        words = query.lower().split()
        return [b for b in self.books if any(w in b.name.lower() for w in words)]

    async def rpg_item_systems(self, ids: Iterable[int]) -> list[RpgSystemStub]:
        return [self.systems[i] for i in ids if i in self.systems]

    async def rpg_families(self, ids: Iterable[int]) -> list[RpgSystemDetails]:
        ids = list(ids)
        self.family_calls.append(ids)
        if self.fail:
            raise BggError("down")
        return [self.details[i] for i in ids if i in self.details]


@pytest.fixture
def rpggeek() -> Iterator[FakeRpgGeek]:
    fake = FakeRpgGeek()
    app.dependency_overrides[get_bgg_client] = lambda: fake
    yield fake


async def search(client: AsyncClient, headers: dict[str, str], q: str) -> list[dict[str, object]]:
    response = await client.get("/api/rpg-systems/search", headers=headers, params={"q": q})
    assert response.status_code == 200, response.text
    body: list[dict[str, object]] = response.json()
    return body


async def test_an_unknown_system_is_found_through_its_books_and_remembered(
    client: AsyncClient, person: MakePerson, rpggeek: FakeRpgGeek
) -> None:
    ann = await person("Ann")

    found = await search(client, ann.headers, "gloomzyx")

    assert [(s["id"], s["name"], s["thumbnail_url"]) for s in found] == [
        (GLOOM, "Gloomzyx", "https://e.com/t.jpg")
    ]
    assert rpggeek.family_calls == [[GLOOM]]  # details filled in for the listing
    # Now it's local: no more RPGGeek searches.
    again = await search(client, ann.headers, "gloomz")
    assert [s["id"] for s in again] == [GLOOM]
    assert rpggeek.searches == ["gloomzyx"]


async def test_a_book_named_unlike_its_system_still_finds_the_system(
    client: AsyncClient, person: MakePerson, rpggeek: FakeRpgGeek
) -> None:
    ann = await person("Ann")

    found = await search(client, ann.headers, "lantern")

    assert [s["name"] for s in found] == ["Mirequoll"]


async def test_rpggeek_being_down_finds_nothing_new(
    client: AsyncClient, person: MakePerson, rpggeek: FakeRpgGeek
) -> None:
    ann = await person("Ann")
    rpggeek.fail = True

    assert await search(client, ann.headers, "gloomzyx") == []


async def test_reading_a_system_fetches_its_details(
    client: AsyncClient, person: MakePerson, rpggeek: FakeRpgGeek
) -> None:
    ann = await person("Ann")

    response = await client.get(f"/api/rpg-systems/{GLOOM}", headers=ann.headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["name"], body["description"], body["is_custom"]) == (
        "Gloomzyx",
        "Grim & dark",
        False,
    )
    assert body["rpggeek_url"] == f"https://rpggeek.com/rpg/{GLOOM}"
    assert (await client.get(f"/api/rpg-systems/{SHARD}", headers=ann.headers)).status_code == 404


async def test_custom_systems_are_yours_to_edit_and_found_by_people_who_use_them(
    client: AsyncClient, person: MakePerson, rpggeek: FakeRpgGeek
) -> None:
    ann, ben = await person("Ann"), await person("Ben")

    added = await client.post(
        "/api/rpg-systems",
        headers=ann.headers,
        json={"name": "Hearthquill Homebrew", "description": "Our own"},
    )

    assert added.status_code == 201, added.text
    system = added.json()
    assert system["id"] < 0 and system["is_custom"] and system["rpggeek_url"] is None
    mine = (await client.get("/api/me/rpg-systems", headers=ann.headers)).json()
    assert [(m["system"]["id"], m["knows"]) for m in mine] == [(system["id"], True)]
    assert [s["id"] for s in await search(client, ann.headers, "hearthquill")] == [system["id"]]
    # Ben hasn't come across it, and RPGGeek doesn't know it.
    assert await search(client, ben.headers, "hearthquill") == []
    edit = {"name": "Hearthquill 2e"}
    assert (
        await client.put(f"/api/rpg-systems/{system['id']}", headers=ben.headers, json=edit)
    ).status_code == 403
    edited = await client.put(f"/api/rpg-systems/{system['id']}", headers=ann.headers, json=edit)
    assert (edited.json()["name"], edited.json()["description"]) == ("Hearthquill 2e", None)


async def test_my_systems_keep_answers_and_gm_means_knowing_it(
    client: AsyncClient, person: MakePerson, db_session: AsyncSession
) -> None:
    ann = await person("Ann")
    db_session.add(RpgSystem(id=GLOOM, name="Gloomzyx"))
    await db_session.commit()
    url = f"/api/me/rpg-systems/{GLOOM}"

    first = await client.put(url, headers=ann.headers, json={"want_to_play": True})
    assert first.status_code == 200, first.text
    assert (first.json()["knows"], first.json()["want_to_play"]) == (False, True)

    second = (
        await client.put(url, headers=ann.headers, json={"can_gm": True, "notes": "Hmm"})
    ).json()

    assert (second["knows"], second["can_gm"], second["want_to_play"], second["notes"]) == (
        True,
        True,
        True,
        "Hmm",
    )
    assert (
        await client.put(f"/api/me/rpg-systems/{SHARD}", headers=ann.headers, json={})
    ).status_code == 404
    assert (await client.delete(url, headers=ann.headers)).status_code == 204
    assert (await client.get("/api/me/rpg-systems", headers=ann.headers)).json() == []
