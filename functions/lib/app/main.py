import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import api_router
from app.bgg import BggClient, PostgresThrottle, create_http_client
from app.config import get_settings
from app.db import engine

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    if not settings.bgg_api_token:
        logger.warning("BGG_API_TOKEN is not set; BoardGameGeek requests will be refused")
    async with create_http_client(settings.bgg_api_token) as http:
        # The throttle lives in Postgres so every running copy of the API shares BGG's spacing.
        app.state.bgg = BggClient(
            http,
            min_interval=settings.bgg_min_interval_seconds,
            throttle=PostgresThrottle(engine),
        )
        yield


# Everything lives under /api so the SPA and API can share one origin in production.
app = FastAPI(
    title="Board Game Group API",
    openapi_url="/api/openapi.json",
    docs_url="/api/docs",
    redoc_url=None,
    lifespan=lifespan,
)
app.include_router(api_router, prefix="/api")
