import time
from collections.abc import AsyncIterator, Callable, Iterator
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_jwks_client
from app.config import get_settings
from app.db import engine, get_session
from app.main import app

TEST_ISSUER = "https://test.kinde.com"
TEST_AUDIENCE = "https://api.test"
TEST_KID = "test-key"

TokenFactory = Callable[..., str]


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


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """A session whose commits land in savepoints that are rolled back after the test."""
    async with engine.connect() as connection:
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
