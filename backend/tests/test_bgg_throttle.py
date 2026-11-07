import asyncio
import time

from app.bgg import PostgresThrottle
from tests.conftest import test_engine


async def test_callers_are_spaced_apart_across_throttle_instances() -> None:
    # Two instances stand in for two separately running copies of the API.
    first, second = PostgresThrottle(test_engine), PostgresThrottle(test_engine)
    await first.hold_off(0)  # start from a clean slate

    started = time.monotonic()
    await asyncio.gather(first.reserve(0.3), second.reserve(0.3), first.reserve(0.3))

    # Three requests need two gaps between them.
    assert time.monotonic() - started >= 0.55


async def test_hold_off_delays_the_next_caller() -> None:
    throttle = PostgresThrottle(test_engine)
    await throttle.reserve(0)

    # Time from before the hold-off: its 0.3s counts from when the database ran it, and a
    # slow round trip back would otherwise eat into the wait being measured.
    started = time.monotonic()
    await throttle.hold_off(0.3)
    await throttle.reserve(0)

    assert time.monotonic() - started >= 0.25
