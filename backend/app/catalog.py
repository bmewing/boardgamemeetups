"""The local game catalog: a cache of BGG data that fills itself in as games are looked at."""

import logging
from collections.abc import Sequence
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import case, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.bgg import BggClient, BggError, CollectionEntry, GameDetails, SearchHit
from app.config import get_settings
from app.models import Game

logger = logging.getLogger(__name__)

# Columns the ranks CSV and BGG searches know about; details overwrite everything.
RANK_COLUMNS = (
    "name",
    "year_published",
    "is_expansion",
    "bgg_rank",
    "bgg_rating",
    "bgg_users_rated",
)


async def upsert_details(session: AsyncSession, details: Sequence[GameDetails]) -> None:
    if not details:
        return
    now = datetime.now(UTC)
    rows = [{**asdict(d), "details_fetched_at": now} for d in details]
    stmt = insert(Game).values(rows)
    await session.execute(
        stmt.on_conflict_do_update(
            index_elements=[Game.id],
            set_={column: stmt.excluded[column] for column in rows[0] if column != "id"},
        )
    )


async def insert_search_hits(session: AsyncSession, hits: Sequence[SearchHit]) -> None:
    """Remember games BGG told us about, without touching ones we already know."""
    if not hits:
        return
    rows = [{"id": h.id, "name": h.name, "year_published": h.year_published} for h in hits]
    await session.execute(
        insert(Game).values(rows).on_conflict_do_nothing(index_elements=[Game.id])
    )


async def upsert_rank_rows(session: AsyncSession, rows: Sequence[dict[str, Any]]) -> None:
    """Load rows from BGG's ranks CSV, keeping any details already fetched."""
    if not rows:
        return
    stmt = insert(Game).values(list(rows))
    await session.execute(
        stmt.on_conflict_do_update(
            index_elements=[Game.id],
            set_={column: stmt.excluded[column] for column in RANK_COLUMNS},
        )
    )


# Catalog columns a BGG collection listing includes. It lacks weight, categories, mechanics
# and the player-count poll, so rows it creates are still stubs until details are fetched.
COLLECTION_COLUMNS = (
    "name",
    "year_published",
    "is_expansion",
    "thumbnail_url",
    "image_url",
    "min_players",
    "max_players",
    "min_playtime",
    "max_playtime",
    "playing_time",
    "bgg_rank",
    "bgg_rating",
    "bgg_users_rated",
)
# Postgres allows 32,767 parameters per statement; stay well under it.
COLLECTION_BATCH = 1000


async def upsert_collection_games(
    session: AsyncSession, entries: Sequence[CollectionEntry]
) -> None:
    """Make sure every game in a BGG collection is in the catalog, filling in blank columns."""
    for start in range(0, len(entries), COLLECTION_BATCH):
        batch = entries[start : start + COLLECTION_BATCH]
        rows = [{"id": e.id, **{c: getattr(e, c) for c in COLLECTION_COLUMNS}} for e in batch]
        stmt = insert(Game).values(rows)
        await session.execute(
            stmt.on_conflict_do_update(
                index_elements=[Game.id],
                # Keep what we have (fetched details win); only fill gaps.
                set_={
                    c: func.coalesce(getattr(Game, c), stmt.excluded[c])
                    for c in COLLECTION_COLUMNS
                    if c not in ("name", "is_expansion")
                },
            )
        )


def _is_stale(game: Game, now: datetime) -> bool:
    if game.details_fetched_at is None:
        return True
    return now - game.details_fetched_at > timedelta(days=get_settings().game_refresh_days)


async def refresh_details(
    session: AsyncSession, bgg: BggClient, games: Sequence[Game], *, only_missing: bool = False
) -> None:
    """Fetch details from BGG for games that lack them (or are stale), in place.

    BGG being down is not fatal: callers get whatever we already had.
    """
    now = datetime.now(UTC)
    wanted = [
        g.id for g in games if (g.details_fetched_at is None if only_missing else _is_stale(g, now))
    ]
    if not wanted:
        return
    try:
        details = await bgg.things(wanted)
    except BggError:
        logger.exception("Could not fetch details for %d games from BGG", len(wanted))
        return
    await upsert_details(session, details)
    await session.commit()
    # Reload the instances so callers see the new values.
    for game in games:
        if game.id in wanted:
            await session.refresh(game)


def _search_statement(query: str, limit: int, include_expansions: bool) -> Any:
    q = query.strip().lower()
    name = func.lower(Game.name)
    # Exact name, then names starting with the query, then containing it, then typo matches.
    tier = case(
        (name == q, 0),
        (name.startswith(q, autoescape=True), 1),
        (name.contains(q, autoescape=True), 2),
        else_=3,
    )
    stmt = (
        select(Game)
        .where(or_(name.contains(q, autoescape=True), name.op("%")(q)))
        .order_by(
            tier,
            # Among real matches the popular game is the likely one ("brass" -> Brass:
            # Birmingham, not Brass Empire); among typo matches, the closest spelling is.
            case((tier < 3, Game.bgg_users_rated)).desc().nulls_last(),
            func.similarity(name, q).desc(),
            Game.bgg_users_rated.desc().nulls_last(),
        )
        .limit(limit)
    )
    if not include_expansions:
        stmt = stmt.where(Game.is_expansion.is_(False))
    return stmt


async def search_games(
    session: AsyncSession,
    bgg: BggClient,
    query: str,
    *,
    limit: int = 20,
    include_expansions: bool = True,
) -> list[Game]:
    stmt = _search_statement(query, limit, include_expansions)
    games = list((await session.scalars(stmt)).all())
    if not games:
        # Unknown locally: ask BGG, remember what it says, and search again.
        try:
            hits = await bgg.search(query.strip())
        except BggError:
            logger.exception("BGG search failed for %r", query)
            return []
        await insert_search_hits(session, hits)
        await session.commit()
        games = list((await session.scalars(stmt)).all())
    # Search results show thumbnails and player counts, so fill in any stubs.
    await refresh_details(session, bgg, games, only_missing=True)
    return games


async def get_game(session: AsyncSession, bgg: BggClient, game_id: int) -> Game | None:
    game = await session.get(Game, game_id)
    if game is None:
        try:
            details = await bgg.things([game_id])
        except BggError:
            logger.exception("Could not fetch game %d from BGG", game_id)
            raise
        if not details:
            return None
        await upsert_details(session, details)
        await session.commit()
        return await session.get(Game, game_id)
    await refresh_details(session, bgg, [game])
    return game
