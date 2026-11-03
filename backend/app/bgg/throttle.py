"""Spacing between BGG requests, shared by every process that talks to BGG.

Deployed as functions, several copies of the API can run at once, so the spacing lives in
Postgres: each caller atomically reserves the next free slot and then waits for it.
"""

import asyncio
import time
from typing import Protocol

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


class Throttle(Protocol):
    async def reserve(self, spacing: float) -> None:
        """Wait for our turn, and keep the next caller at least `spacing` seconds behind us."""

    async def hold_off(self, seconds: float) -> None:
        """Make every caller wait at least `seconds` from now (BGG said it's busy)."""


class LocalThrottle:
    """In-process spacing; enough for a single process such as tests or scripts."""

    def __init__(self) -> None:
        self._next = 0.0
        self._lock = asyncio.Lock()

    async def reserve(self, spacing: float) -> None:
        async with self._lock:
            now = time.monotonic()
            slot = max(now, self._next)
            self._next = slot + spacing
        if slot > now:
            await asyncio.sleep(slot - now)

    async def hold_off(self, seconds: float) -> None:
        async with self._lock:
            self._next = max(self._next, time.monotonic() + seconds)


# One row (id 1) holds the earliest time the next request may start.
RESERVE = text("""
    INSERT INTO bgg_throttle AS t (id, next_request_at)
    VALUES (1, clock_timestamp() + make_interval(secs => CAST(:spacing AS double precision)))
    ON CONFLICT (id) DO UPDATE
        SET next_request_at = GREATEST(t.next_request_at, clock_timestamp())
            + make_interval(secs => CAST(:spacing AS double precision))
    RETURNING GREATEST(
        EXTRACT(EPOCH FROM t.next_request_at - clock_timestamp())
            - CAST(:spacing AS double precision),
        0
    ) AS wait_seconds
""")

HOLD_OFF = text("""
    INSERT INTO bgg_throttle AS t (id, next_request_at)
    VALUES (1, clock_timestamp() + make_interval(secs => CAST(:seconds AS double precision)))
    ON CONFLICT (id) DO UPDATE
        SET next_request_at = GREATEST(
            t.next_request_at,
            clock_timestamp() + make_interval(secs => CAST(:seconds AS double precision))
        )
""")


class PostgresThrottle:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def reserve(self, spacing: float) -> None:
        # A short transaction of its own, so nothing stays locked while we wait.
        async with self._engine.begin() as connection:
            wait = (await connection.execute(RESERVE, {"spacing": spacing})).scalar_one()
        if wait > 0:
            await asyncio.sleep(float(wait))

    async def hold_off(self, seconds: float) -> None:
        async with self._engine.begin() as connection:
            await connection.execute(HOLD_OFF, {"seconds": seconds})
