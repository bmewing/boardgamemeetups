"""Online dates on Board Game Arena: BGA's games, its player counts, and no bringing."""

from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BgaGame, Game
from tests.conftest import Person
from tests.test_games_api import FakeBgg, bgg
from tests.test_groups_api import BASE, Crew, crew, games, own
from tests.test_meetup_cycle_api import by_game, nominate, vote_state
from tests.test_meetup_rsvps import answer

__all__ = ["bgg", "crew", "games"]  # fixtures used here

# Catalog games: one on BGA for 2 or 4 (never 3), a Premium one, and one not on BGA.
PAIRS, PREMIUM, OFFLINE, TWIN = range(990_500_001, 990_500_005)


@pytest.fixture
async def on_bga(db_session: AsyncSession, games: None) -> None:
    fetched = datetime.now(UTC)  # so looking a game up never asks BGG
    db_session.add_all(
        [
            Game(id=PAIRS, name="Zyx Pairs", min_players=2, max_players=4),
            Game(id=PREMIUM, name="Zyx Grand Premium", min_players=1, max_players=5),
            Game(id=OFFLINE, name="Zyx Cardboard Only", min_players=2, max_players=4),
            Game(id=TWIN, name="Zyx Twin", details_fetched_at=fetched),
        ]
    )
    await db_session.flush()
    db_session.add_all(
        [
            BgaGame(
                id=990_500_101,
                slug="zyxpairs",
                name="Zyx Pairs",
                game_id=PAIRS,
                premium=False,
                player_counts=[2, 4],
                status="public",
            ),
            BgaGame(
                id=990_500_102,
                slug="zyxgrand",
                name="Zyx Grand Premium",
                game_id=PREMIUM,
                premium=True,
                player_counts=[1, 2, 3, 4, 5],
                status="public",
            ),
            # BGA lists Twin twice; the released, free one is the one shown.
            BgaGame(
                id=990_500_103,
                slug="zyxtwinbeta",
                name="Zyx Twin (beta)",
                game_id=TWIN,
                premium=False,
                player_counts=[2],
                status="beta",
            ),
            BgaGame(
                id=990_500_104,
                slug="zyxtwin",
                name="Zyx Twin",
                game_id=TWIN,
                premium=False,
                player_counts=[2, 3],
                status="public",
            ),
            BgaGame(
                id=990_500_105,
                slug="zyxunlinked",
                name="Zyx Unlinked",
                game_id=None,
                premium=False,
                player_counts=[2],
                status="public",
            ),
        ]
    )
    await db_session.commit()


async def add_online_date(
    client: AsyncClient, group: dict[str, Any], who: Person, **fields: Any
) -> dict[str, Any]:
    response = await client.post(
        f"/api/groups/{group['id']}/meetups",
        headers=who.headers,
        json={
            "local_date": (date.today() + timedelta(days=3)).isoformat(),
            "location": "Ignored online",
            "is_online": True,
            **fields,
        },
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


async def fitting(client: AsyncClient, meetup: str, who: Person) -> dict[str, Any]:
    response = await client.get(f"/api/meetups/{meetup}/games", headers=who.headers)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


async def want(client: AsyncClient, who: Person, game_id: int) -> None:
    response = await client.put(
        f"/api/me/games/{game_id}", headers=who.headers, json={"want_to_play": True}
    )
    assert response.status_code == 200, response.text


async def test_searching_bga_lists_linked_games(
    client: AsyncClient, crew: Crew, on_bga: None
) -> None:
    _group, (ann, *_rest) = crew

    found = await client.get("/api/bga/games", headers=ann.headers, params={"q": "zyx"})

    assert found.status_code == 200, found.text
    # Not the game BGA has that isn't linked to the catalog, and Twin once.
    slugs = sorted(g["slug"] for g in found.json())
    assert slugs == ["zyxgrand", "zyxpairs", "zyxtwin"]
    twin = next(g for g in found.json() if g["game"]["id"] == TWIN)
    assert twin["lobby_url"] == "https://boardgamearena.com/lobby?game=990500104"
    three = await client.get(
        "/api/bga/games", headers=ann.headers, params={"q": "zyx", "players": 3}
    )
    assert sorted(g["slug"] for g in three.json()) == ["zyxgrand", "zyxtwin"]  # Pairs skips 3


async def test_a_game_page_links_to_bga(
    client: AsyncClient, crew: Crew, on_bga: None, bgg: FakeBgg
) -> None:
    _group, (ann, *_rest) = crew

    game = (await client.get(f"/api/games/{TWIN}", headers=ann.headers)).json()

    assert game["bga"]["game_url"] == "https://boardgamearena.com/gamepanel?game=zyxtwin"


async def test_an_online_date_has_a_link_instead_of_a_place(
    client: AsyncClient, crew: Crew, on_bga: None
) -> None:
    group, (ann, ben, *_rest) = crew
    table = "https://boardgamearena.com/table?table=123"
    await client.patch(
        "/api/me", headers=ben.headers, json={"bga_username": "benplays", "bga_premium": True}
    )

    meetup = await add_online_date(client, group, ann, online_url=table)

    assert (meetup["is_online"], meetup["online_url"], meetup["location"]) == (True, table, None)
    answered = (await answer(client, meetup["id"], ben, "yes")).json()
    (rsvp,) = answered["rsvps"]
    assert (rsvp["bga_username"], rsvp["bga_premium"]) == ("benplays", True)
    bad = await client.patch(
        f"/api/meetups/{meetup['id']}", headers=ann.headers, json={"online_url": "ftp://x"}
    )
    assert bad.status_code == 422
    ics = await client.get(f"/api/meetups/{meetup['id']}/calendar.ics", headers=ben.headers)
    assert "LOCATION:Board Game Arena: https://boardgamearena.com/table?table=123" in ics.text

    # Back in person: the group's usual place, and no link.
    moved = await client.patch(
        f"/api/meetups/{meetup['id']}", headers=ann.headers, json={"is_online": False}
    )
    assert (moved.json()["is_online"], moved.json()["online_url"]) == (False, None)


async def test_games_that_fit_online_come_from_bga(
    client: AsyncClient, crew: Crew, on_bga: None
) -> None:
    group, (ann, ben, cat, dee, _eve) = crew
    meetup = (await add_online_date(client, group, ann))["id"]
    await want(client, ann, PAIRS)  # nobody owns it, but it's on BGA
    await want(client, ben, PREMIUM)
    await own(client, cat, OFFLINE)  # owned, but not on BGA
    await own(client, cat, BASE)  # nor this
    for who in (ann, ben, cat):
        await answer(client, meetup, who, "yes")

    three = await fitting(client, meetup, ann)

    assert three["online"] is True
    assert three["premium_host_going"] is False
    # Pairs seats 2 or 4 on BGA, so three people don't fit it (even though the box says 2-4).
    assert [g["game"]["id"] for g in three["games"]] == [PREMIUM]
    (grand,) = three["games"]
    assert (grand["bga"]["premium"], grand["bringers"]) == (True, [])

    await answer(client, meetup, dee, "yes")
    await client.patch("/api/me", headers=dee.headers, json={"bga_premium": True})
    four = await fitting(client, meetup, ann)
    assert sorted(g["game"]["id"] for g in four["games"]) == [PAIRS, PREMIUM]
    pairs = next(g for g in four["games"] if g["game"]["id"] == PAIRS)
    assert (pairs["min_players"], pairs["max_players"], pairs["fit"]) == (2, 4, "together")
    assert four["premium_host_going"] is True


async def test_voting_online_takes_any_bga_game_and_nobody_brings_it(
    client: AsyncClient, crew: Crew, on_bga: None, outbox: Any
) -> None:
    group, (ann, ben, *_rest) = crew
    meetup = (await add_online_date(client, group, ann))["id"]
    await want(client, ben, PAIRS)
    for who in (ann, ben):
        await answer(client, meetup, who, "yes")

    before = await vote_state(client, meetup, ann)
    assert before["online"] is True
    assert [g["id"] for g in before["nominatable"]] == [PAIRS]  # on BGA, and Ben has it

    assert (await nominate(client, meetup, ann, OFFLINE)).status_code == 422  # not on BGA
    state = (await nominate(client, meetup, ann, PREMIUM)).json()  # nobody owns it: fine
    grand = by_game(state)[PREMIUM]
    assert grand["bga"]["slug"] == "zyxgrand"
    assert (grand["fit"], grand["min_players"], grand["max_players"]) == ("together", 1, 5)

    locked = await client.post(
        f"/api/meetups/{meetup}/lock",
        headers=ann.headers,
        json={"nomination_ids": [grand["id"]]},
    )
    assert locked.status_code == 200, locked.text
    assert by_game(locked.json())[PREMIUM]["bring"] is None
    bring = await client.put(f"/api/meetups/{meetup}/bring/{PREMIUM}", headers=ann.headers, json={})
    assert bring.status_code == 409
    toggle = await client.patch(
        f"/api/meetups/{meetup}", headers=ann.headers, json={"is_online": False}
    )
    assert toggle.status_code == 409
    (picked,) = [e for e in outbox.to(ben.email) if e.subject.startswith("Picked")]
    assert "https://boardgamearena.com/gamepanel?game=zyxgrand" in picked.text


async def test_in_person_dates_still_need_someone_to_own_it(
    client: AsyncClient, crew: Crew, on_bga: None
) -> None:
    group, (ann, *_rest) = crew
    response = await client.post(
        f"/api/groups/{group['id']}/meetups",
        headers=ann.headers,
        json={"local_date": (date.today() + timedelta(days=3)).isoformat()},
    )
    meetup = response.json()["id"]
    await answer(client, meetup, ann, "yes")

    assert (await nominate(client, meetup, ann, PREMIUM)).status_code == 422
    assert (await fitting(client, meetup, ann))["online"] is False
