"""Client for the BoardGameGeek XML API2.

BGG asks callers to space requests about five seconds apart and answers 429/5xx when they
don't, so every request waits its turn on a shared throttle and retries with backoff.
"""

import logging
from collections.abc import Iterable

import httpx

from app.bgg.parse import GameDetails, SearchHit, parse_search, parse_things
from app.bgg.throttle import LocalThrottle, Throttle

logger = logging.getLogger(__name__)

BGG_BASE_URL = "https://boardgamegeek.com"  # no www: BGG rejects tokens there
THING_BATCH_SIZE = 20  # BGG's maximum ids per thing request
RETRY_STATUSES = {202, 429, 500, 502, 503, 504}


class BggError(Exception):
    """BGG could not be reached or kept refusing the request."""


class BggClient:
    def __init__(
        self,
        http: httpx.AsyncClient,
        *,
        min_interval: float = 5.0,
        max_retries: int = 3,
        throttle: Throttle | None = None,
    ) -> None:
        self._http = http
        self._min_interval = min_interval
        self._max_retries = max_retries
        self._throttle = throttle or LocalThrottle()

    async def _get(self, path: str, params: dict[str, str]) -> bytes:
        for attempt in range(self._max_retries + 1):
            await self._throttle.reserve(self._min_interval)
            try:
                response = await self._http.get(path, params=params)
            except httpx.TransportError as exc:
                status: int | str = type(exc).__name__
            else:
                status = response.status_code
                if status == 200:
                    return response.content
                if status not in RETRY_STATUSES:
                    raise BggError(f"BGG returned {status} for {path}")
            backoff = self._min_interval * 2**attempt
            await self._throttle.hold_off(backoff)
            logger.warning("BGG %s for %s; retrying in %.0fs", status, path, backoff)
        raise BggError(f"BGG kept refusing {path}")

    async def search(self, query: str) -> list[SearchHit]:
        xml = await self._get(
            "/xmlapi2/search", {"query": query, "type": "boardgame,boardgameexpansion"}
        )
        return parse_search(xml)

    async def things(self, ids: Iterable[int]) -> list[GameDetails]:
        unique = list(dict.fromkeys(ids))
        details: list[GameDetails] = []
        for start in range(0, len(unique), THING_BATCH_SIZE):
            batch = unique[start : start + THING_BATCH_SIZE]
            xml = await self._get(
                "/xmlapi2/thing",
                {
                    "id": ",".join(map(str, batch)),
                    "type": "boardgame,boardgameexpansion",
                    "stats": "1",
                },
            )
            details.extend(parse_things(xml))
        return details


def create_http_client(token: str) -> httpx.AsyncClient:
    headers = {"User-Agent": "BoardGameGroup/0.1"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return httpx.AsyncClient(base_url=BGG_BASE_URL, headers=headers, timeout=30)
