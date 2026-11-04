import time
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator, Sequence
from dataclasses import dataclass
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.auth import get_jwks_client
from app.config import get_settings
from app.db import get_session
from app.email import Email, get_mailer
from app.main import app
from app.models import Base

TEST_ISSUER = "https://test.kinde.com"
TEST_AUDIENCE = "https://api.test"
TEST_KID = "test-key"

TokenFactory = Callable[..., str]

# Tests get their own schema, rebuilt empty each run, so data in the dev database (such as
# an imported BGG catalog) can't change their results. pg_trgm stays reachable in public.
TEST_SCHEMA = "pytest"
test_engine = create_async_engine(
    get_settings().database_url,
    connect_args={"server_settings": {"search_path": f"{TEST_SCHEMA}, public"}},
)


@pytest.fixture(scope="session", autouse=True)
async def test_schema() -> AsyncIterator[None]:
    # Create the schema before test_engine first connects: SQLAlchemy fixes an engine's
    # default schema on its first connection, and would otherwise settle on public.
    setup_engine = create_async_engine(get_settings().database_url)
    async with setup_engine.begin() as connection:
        await connection.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm SCHEMA public"))
        await connection.execute(text(f"DROP SCHEMA IF EXISTS {TEST_SCHEMA} CASCADE"))
        await connection.execute(text(f"CREATE SCHEMA {TEST_SCHEMA}"))
    await setup_engine.dispose()
    async with test_engine.begin() as connection:
        # No existence check: it counts any visible table, including the dev ones in public.
        await connection.run_sync(Base.metadata.create_all, checkfirst=False)
    yield
    await test_engine.dispose()


@pytest.fixture(scope="session")
def signing_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


class StaticJWKSClient:
    """Stands in for PyJWKClient, serving the test public key instead of Kinde's."""

    def __init__(self, private_key: rsa.RSAPrivateKey) -> None:
        jwk = jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key(), as_dict=True)
        self.key = jwt.PyJWK({**jwk, "kid": TEST_KID, "alg": "RS256"})

    def get_signing_key_from_jwt(self, token: str) -> jwt.PyJWK:
        if jwt.get_unverified_header(token).get("kid") != TEST_KID:
            raise jwt.PyJWKClientError("Unknown signing key")
        return self.key


@pytest.fixture(autouse=True)
def kinde_settings(signing_key: rsa.RSAPrivateKey) -> Iterator[None]:
    settings = get_settings()
    original = (settings.kinde_domain, settings.kinde_audience)
    settings.kinde_domain, settings.kinde_audience = TEST_ISSUER, TEST_AUDIENCE
    app.dependency_overrides[get_jwks_client] = lambda: StaticJWKSClient(signing_key)
    yield
    settings.kinde_domain, settings.kinde_audience = original


@pytest.fixture
def make_token(signing_key: rsa.RSAPrivateKey) -> TokenFactory:
    def factory(
        sub: str = "kp_test_user",
        *,
        key: rsa.RSAPrivateKey | None = None,
        **claims: Any,
    ) -> str:
        now = int(time.time())
        payload = {
            "iss": TEST_ISSUER,
            "aud": [TEST_AUDIENCE],
            "sub": sub,
            "iat": now,
            "exp": now + 300,
            **claims,
        }
        return jwt.encode(payload, key or signing_key, algorithm="RS256", headers={"kid": TEST_KID})

    return factory


class Outbox:
    """Stands in for Resend: keeps what would have been sent."""

    def __init__(self) -> None:
        self.sent: list[Email] = []
        self.failing = False

    async def send(self, emails: Sequence[Email]) -> bool:
        if self.failing:
            return False
        self.sent.extend(emails)
        return True

    def to(self, address: str) -> list[Email]:
        return [email for email in self.sent if email.to == address]


@pytest.fixture(autouse=True)
def outbox() -> Outbox:
    """No test ever sends a real email."""
    box = Outbox()
    app.dependency_overrides[get_mailer] = lambda: box
    return box


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """A session whose commits land in savepoints that are rolled back after the test."""
    async with test_engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        )
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    async def test_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_session] = test_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@dataclass
class Person:
    id: str
    email: str
    headers: dict[str, str]


MakePerson = Callable[[str], Awaitable[Person]]


@pytest.fixture
def person(client: AsyncClient, make_token: TokenFactory) -> MakePerson:
    async def make(name: str) -> Person:
        email = f"{name.lower()}@example.com"
        headers = bearer(make_token(f"kp_{name.lower()}", email=email, given_name=name))
        me = (await client.get("/api/me", headers=headers)).json()
        return Person(id=me["id"], email=email, headers=headers)

    return make
