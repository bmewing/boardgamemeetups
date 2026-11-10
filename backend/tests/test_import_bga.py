from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.import_bga import BgaEntry, BgaFileError, import_games, parse, snapshot
from app.models import BgaGame, Game

PAGE = (Path(__file__).parent / "fixtures" / "bga" / "gamelist.html").read_text(encoding="utf-8")
DUEL, NEW, TOWERS = 990_400_101, 990_400_102, 990_400_103


def test_parse_reads_the_game_list_in_a_saved_page() -> None:
    entries = parse(PAGE)

    # In BGA's order of ids; the game with no player counts is left out.
    assert [e.slug for e in entries] == ["zyxduel", "zyxnew", "zyxnomatch", "zyxtowers"]
    assert entries[0] == BgaEntry(
        id=990_400_001,
        slug="zyxduel",
        name="Zyxquokka Duel",
        premium=True,
        player_counts=[2, 4],
        bgg_id=DUEL,
        status="public",
    )
    assert entries[1].name == "Zyxquokka & Friends"


def test_a_snapshot_reads_back_the_same() -> None:
    entries = parse(PAGE)

    written = snapshot(entries)

    assert parse(written) == entries
    assert written.count("\n") == len(entries) + 2  # a line per game, so diffs stay small


def test_a_page_without_the_list_is_refused() -> None:
    with pytest.raises(BgaFileError):
        parse("<html><body>Please sign in</body></html>")


@pytest.fixture
async def catalog_games(db_session: AsyncSession) -> None:
    db_session.add_all(
        [
            Game(id=DUEL, name="Zyxquokka Duel", year_published=2030),
            Game(id=TOWERS, name="Zyxquokka Towers", year_published=2031),
        ]
    )
    await db_session.commit()


async def _links(db_session: AsyncSession) -> dict[str, int | None]:
    db_session.expire_all()
    rows = await db_session.execute(select(BgaGame.slug, BgaGame.game_id))
    return {slug: game_id for slug, game_id in rows}


async def test_import_links_every_game_it_can(
    db_session: AsyncSession, catalog_games: None
) -> None:
    report = await import_games(db_session, parse(PAGE))
    await db_session.commit()

    assert await _links(db_session) == {
        "zyxduel": DUEL,  # BGA named the BGG game
        "zyxnew": NEW,  # BGA named a BGG game the catalog didn't have yet
        "zyxtowers": TOWERS,  # no BGG id, but the name is unambiguous
        "zyxnomatch": None,
    }
    stub = await db_session.get(Game, NEW)
    assert stub is not None
    assert (stub.name, stub.details_fetched_at) == ("Zyxquokka & Friends", None)
    assert (report.total, report.linked, report.stubs_added) == (4, 3, 1)
    assert [(e.slug, g) for e, g in report.matched_by_name] == [
        ("zyxtowers", f"{TOWERS} Zyxquokka Towers (2031)")
    ]
    assert [e.slug for e in report.unlinked] == ["zyxnomatch"]


async def test_importing_again_updates_and_removes(
    db_session: AsyncSession, catalog_games: None
) -> None:
    entries = parse(PAGE)
    await import_games(db_session, entries)
    # BGA dropped one game, made another free, and its BGG id was fixed by hand.
    entries = [e for e in entries if e.slug != "zyxnew"]
    entries[0].premium = False
    entries[1].bgg_id = TOWERS

    report = await import_games(db_session, entries)
    await db_session.commit()

    assert report.removed == 1
    links = await _links(db_session)
    assert links == {"zyxduel": DUEL, "zyxnomatch": TOWERS, "zyxtowers": TOWERS}
    duel = await db_session.scalar(select(BgaGame).where(BgaGame.slug == "zyxduel"))
    assert duel is not None
    assert duel.premium is False
    assert duel.game_url == "https://boardgamearena.com/gamepanel?game=zyxduel"
    assert duel.lobby_url == "https://boardgamearena.com/lobby?game=990400001"
