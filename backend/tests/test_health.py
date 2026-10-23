from collections.abc import AsyncIterator

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import Settings
from app.db import get_session
from app.main import app


async def test_health_reports_database_ok(client: AsyncClient) -> None:
    response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


async def test_health_reports_degraded_when_database_unreachable(client: AsyncClient) -> None:
    unreachable = create_async_engine(
        "postgresql+asyncpg://nobody:nothing@127.0.0.1:1/none", connect_args={"timeout": 1}
    )

    async def broken_session() -> AsyncIterator[AsyncSession]:
        async with AsyncSession(unreachable) as session:
            yield session

    app.dependency_overrides[get_session] = broken_session
    response = await client.get("/api/health")
    await unreachable.dispose()

    assert response.status_code == 200
    assert response.json() == {"status": "degraded", "database": "unavailable"}


def test_supabase_url_is_adapted_for_asyncpg() -> None:
    settings = Settings(
        database_url="postgresql://postgres.ref:pw@aws-0-us-east-1.pooler.supabase.com:5432/postgres?sslmode=require"
    )

    assert settings.database_url == (
        "postgresql+asyncpg://postgres.ref:pw@aws-0-us-east-1.pooler.supabase.com:5432/postgres"
        "?ssl=require"
    )
