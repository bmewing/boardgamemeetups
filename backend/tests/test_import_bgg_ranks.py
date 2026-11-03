import io

from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog import upsert_details, upsert_rank_rows
from app.import_bgg_ranks import CHUNK_SIZE, parse_rows
from app.models import Game
from tests.test_games_api import BASE_ID, quokka_details

CSV = """\
id,name,yearpublished,rank,bayesaverage,average,usersrated,is_expansion,abstracts_rank
990000001,Quokkazzyx,2030,38,7.8,7.99,116394,0,
990000002,Quokkazzyx: Coastal Expansion,2031,0,0,7.5,120,1,
,No id,2020,1,1,1,1,0,
990000003,,2020,1,1,1,1,0,
"""


def test_parse_rows_reads_the_ranks_csv() -> None:
    rows = list(parse_rows(io.StringIO(CSV)))

    assert rows == [
        {
            "id": 990000001,
            "name": "Quokkazzyx",
            "year_published": 2030,
            "is_expansion": False,
            "bgg_rank": 38,
            "bgg_rating": 7.99,
            "bgg_users_rated": 116394,
        },
        {
            "id": 990000002,
            "name": "Quokkazzyx: Coastal Expansion",
            "year_published": 2031,
            "is_expansion": True,
            "bgg_rank": None,
            "bgg_rating": 7.5,
            "bgg_users_rated": 120,
        },
    ]


async def test_a_full_import_batch_fits_in_one_statement(db_session: AsyncSession) -> None:
    rows = [
        {
            "id": 990_100_000 + i,
            "name": f"Batch game {i}",
            "year_published": 2030,
            "is_expansion": False,
            "bgg_rank": None,
            "bgg_rating": None,
            "bgg_users_rated": None,
        }
        for i in range(CHUNK_SIZE)
    ]

    await upsert_rank_rows(db_session, rows)

    assert await db_session.get(Game, 990_100_000 + CHUNK_SIZE - 1) is not None


async def test_importing_ranks_keeps_fetched_details(db_session: AsyncSession) -> None:
    await upsert_details(db_session, [quokka_details()[BASE_ID]])

    await upsert_rank_rows(db_session, list(parse_rows(io.StringIO(CSV))))

    game = await db_session.get(Game, BASE_ID)
    assert game is not None
    await db_session.refresh(game)
    assert game.bgg_rank == 38  # from the CSV
    assert game.thumbnail_url == "https://example.com/quokka.jpg"  # kept
    assert game.details_fetched_at is not None
