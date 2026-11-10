"""The hourly run keeps the games in people's collections up to date from BGG."""

from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app import catalog
from app.models import Game
from tests.conftest import MakePerson
from tests.test_games_api import BASE_ID, EXPANSION_ID, FakeBgg, bgg
from tests.test_groups_api import own

__all__ = ["bgg"]  # fixtures used here

FRESH, STALE, NOBODYS = 990_600_001, 990_600_002, 990_600_003


async def test_only_collection_games_that_are_due_are_refreshed(
    client: AsyncClient, person: MakePerson, db_session: AsyncSession, bgg: FakeBgg
) -> None:
    now = datetime.now(UTC)
    db_session.add_all(
        [
            Game(id=BASE_ID, name="Quokkazzyx"),  # never fetched
            Game(id=EXPANSION_ID, name="Quokkazzyx: Coastal Expansion"),  # in nobody's games
            Game(id=FRESH, name="Zyx Fresh", details_fetched_at=now - timedelta(days=2)),
            Game(id=STALE, name="Zyx Stale", details_fetched_at=now - timedelta(days=45)),
            Game(id=NOBODYS, name="Zyx Nobody's", details_fetched_at=now - timedelta(days=90)),
        ]
    )
    await db_session.commit()
    ann = await person("Ann")
    for game_id in (BASE_ID, FRESH, STALE):
        await own(client, ann, game_id)

    # One at a time: the game never fetched comes first, then the stalest.
    assert (
        await catalog.refresh_collection_games(
            db_session,
            bgg,  # type: ignore[arg-type]
            limit=1,
        )
        == 1
    )
    assert bgg.thing_calls == [[BASE_ID]]
    base = await db_session.get(Game, BASE_ID)
    assert base is not None
    assert (base.max_players, base.details_fetched_at is not None) == (5, True)

    assert (
        await catalog.refresh_collection_games(
            db_session,
            bgg,  # type: ignore[arg-type]
            limit=40,
        )
        == 1
    )
    assert bgg.thing_calls[-1] == [STALE]


async def test_the_hourly_run_refreshes_collection_games(
    client: AsyncClient, person: MakePerson, db_session: AsyncSession, bgg: FakeBgg
) -> None:
    db_session.add(Game(id=BASE_ID, name="Quokkazzyx"))
    await db_session.commit()
    await own(client, await person("Ann"), BASE_ID)

    first = (await client.post("/api/notifications/run")).json()
    second = (await client.post("/api/notifications/run")).json()

    assert (first["refreshed_games"], second["refreshed_games"]) == (1, 0)


async def test_bgg_being_down_doesnt_stop_the_hourly_run(
    client: AsyncClient, person: MakePerson, db_session: AsyncSession
) -> None:
    db_session.add(Game(id=BASE_ID, name="Quokkazzyx"))
    await db_session.commit()
    await own(client, await person("Ann"), BASE_ID)

    response = await client.post("/api/notifications/run")  # the offline stand-in fails

    assert response.status_code == 200
    assert response.json()["refreshed_games"] == 1  # asked for; tried again next run
