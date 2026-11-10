"""The local RPG system catalog: a cache of RPGGeek's systems, plus ones people add.

RPGGeek's search finds books, not systems, so a search it hasn't seen before costs three
throttled requests: the books, the systems those books link to, then the systems' details.
`app.import_rpg_systems` loads the popular systems up front so most searches stay local.
"""

import logging
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Numeric, case, cast, func, literal, or_, select, union
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.bgg import BggClient, BggError, RpgSystemDetails, RpgSystemStub, SearchHit
from app.config import get_settings
from app.models import Character, Group, GroupMember, RpgSystem, UserRpgSystem

logger = logging.getLogger(__name__)

# Books to look up per RPGGeek search: one `thing` request's worth.
BOOKS_PER_SEARCH = 20


async def upsert_system_details(session: AsyncSession, details: Sequence[RpgSystemDetails]) -> None:
    if not details:
        return
    now = datetime.now(UTC)
    rows = [
        {
            "id": d.id,
            "name": d.name[:512],
            "description": d.description,
            "thumbnail_url": d.thumbnail_url,
            "image_url": d.image_url,
            "details_fetched_at": now,
        }
        for d in details
    ]
    stmt = insert(RpgSystem).values(rows)
    await session.execute(
        stmt.on_conflict_do_update(
            index_elements=[RpgSystem.id],
            set_={column: stmt.excluded[column] for column in rows[0] if column != "id"},
        )
    )


async def insert_system_stubs(session: AsyncSession, stubs: Sequence[RpgSystemStub]) -> None:
    """Remember systems RPGGeek named, without touching ones we already know."""
    if not stubs:
        return
    rows = [{"id": s.id, "name": s.name[:512]} for s in stubs]
    await session.execute(
        insert(RpgSystem).values(rows).on_conflict_do_nothing(index_elements=[RpgSystem.id])
    )


def _is_stale(system: RpgSystem, now: datetime) -> bool:
    if system.details_fetched_at is None:
        return True
    return now - system.details_fetched_at > timedelta(days=get_settings().game_refresh_days)


async def refresh_details(
    session: AsyncSession,
    bgg: BggClient,
    systems: Sequence[RpgSystem],
    *,
    only_missing: bool = False,
) -> None:
    """Fetch details from RPGGeek for systems that lack them (or are stale), in place.

    RPGGeek being down is not fatal: callers get whatever we already had.
    """
    now = datetime.now(UTC)
    wanted = [
        s.id
        for s in systems
        if not s.is_custom and (s.details_fetched_at is None if only_missing else _is_stale(s, now))
    ]
    if not wanted:
        return
    try:
        details = await bgg.rpg_families(wanted)
    except BggError:
        logger.exception("Could not fetch %d RPG systems from RPGGeek", len(wanted))
        return
    await upsert_system_details(session, details)
    await session.commit()
    for system in systems:
        if system.id in wanted:
            await session.refresh(system)


def _search_statement(query: str, limit: int) -> Any:
    q = query.strip().lower()
    name = func.lower(RpgSystem.name)
    # Exact name, then names starting with the query, then containing it, then typo matches.
    tier = case(
        (name == q, 0),
        (name.startswith(q, autoescape=True), 1),
        (name.contains(q, autoescape=True), 2),
        else_=3,
    )
    closeness = func.greatest(func.similarity(name, q), func.word_similarity(q, name))
    return (
        select(RpgSystem)
        .where(
            or_(
                name.contains(q, autoescape=True),
                name.op("%")(q),
                literal(q).op("<%")(name),
            ),
            RpgSystem.id > 0,  # systems people added are found through who uses them
        )
        .order_by(tier, func.round(cast(closeness, Numeric), 1).desc(), RpgSystem.name)
        .limit(limit)
    )


def _known_custom_ids(user_id: uuid.UUID) -> Any:
    """Ids of systems people added that this user has come across: ones they added, said
    something about, have a character in, or that one of their groups plays."""
    my_groups = select(GroupMember.group_id).where(GroupMember.user_id == user_id)
    return union(
        select(RpgSystem.id).where(RpgSystem.created_by_id == user_id),
        select(UserRpgSystem.system_id).where(UserRpgSystem.user_id == user_id),
        select(Character.system_id).where(Character.user_id == user_id),
        select(Group.rpg_system_id).where(
            Group.id.in_(my_groups), Group.rpg_system_id.is_not(None)
        ),
    )


async def _custom_systems(session: AsyncSession, user_id: uuid.UUID, query: str) -> list[RpgSystem]:
    stmt = (
        select(RpgSystem)
        .where(
            RpgSystem.id < 0,
            RpgSystem.id.in_(_known_custom_ids(user_id)),
            func.lower(RpgSystem.name).contains(query.strip().lower(), autoescape=True),
        )
        .order_by(RpgSystem.name)
    )
    return list((await session.scalars(stmt)).all())


def _likely_books(hits: Sequence[SearchHit], query: str) -> list[int]:
    """BGG lists books alphabetically; put the ones named most like the query first."""
    q = query.strip().lower()

    def rank(hit: SearchHit) -> int:
        name = hit.name.lower()
        if name == q:
            return 0
        if name.startswith(q):
            return 1
        return 2 if q in name else 3

    return [hit.id for hit in sorted(hits, key=rank)[:BOOKS_PER_SEARCH]]


async def search_systems(
    session: AsyncSession,
    bgg: BggClient,
    query: str,
    *,
    limit: int = 20,
    user_id: uuid.UUID | None = None,
) -> list[RpgSystem]:
    """Search RPGGeek's systems, plus, for `user_id`, the added systems they've come across."""
    custom = await _custom_systems(session, user_id, query) if user_id else []
    stmt = _search_statement(query, limit)
    systems = list((await session.scalars(stmt)).all())
    if not systems:
        # Unknown locally: find books on RPGGeek, then the systems they belong to.
        try:
            hits = await bgg.search_rpg_items(query.strip())
            stubs = await bgg.rpg_item_systems(_likely_books(hits, query))
        except BggError:
            logger.exception("RPGGeek search failed for %r", query)
            return custom[:limit]
        await insert_system_stubs(session, stubs)
        await session.commit()
        found = {stub.id for stub in stubs}
        systems = list((await session.scalars(stmt)).all())
        # A book can match the query while its system's name doesn't ("Alone in the Dark"
        # is a Blades in the Dark book), so keep the systems the books led to as well.
        missing = found - {s.id for s in systems}
        if missing:
            systems += (
                await session.scalars(
                    select(RpgSystem).where(RpgSystem.id.in_(missing)).order_by(RpgSystem.name)
                )
            ).all()
    systems = systems[:limit]
    await refresh_details(session, bgg, systems, only_missing=True)
    return (custom + systems)[:limit]


async def get_system(session: AsyncSession, bgg: BggClient, system_id: int) -> RpgSystem | None:
    system = await session.get(RpgSystem, system_id)
    if system is None and system_id < 0:
        return None
    if system is None:
        try:
            details = await bgg.rpg_families([system_id])
        except BggError:
            logger.exception("Could not fetch RPG system %d from RPGGeek", system_id)
            raise
        if not details:
            return None
        await upsert_system_details(session, details)
        await session.commit()
        return await session.get(RpgSystem, system_id)
    await refresh_details(session, bgg, [system])
    return system
