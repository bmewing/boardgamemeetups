import time

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import AsyncClient

from tests.conftest import TokenFactory, bearer


async def test_missing_token_is_rejected(client: AsyncClient) -> None:
    response = await client.get("/api/me")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


async def test_garbage_token_is_rejected(client: AsyncClient) -> None:
    response = await client.get("/api/me", headers=bearer("not-a-jwt"))

    assert response.status_code == 401


async def test_token_signed_by_another_key_is_rejected(
    client: AsyncClient, make_token: TokenFactory
) -> None:
    impostor = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    response = await client.get("/api/me", headers=bearer(make_token(key=impostor)))

    assert response.status_code == 401


@pytest.mark.parametrize(
    "claims",
    [
        pytest.param({"aud": ["https://some-other-api"]}, id="wrong audience"),
        pytest.param({"iss": "https://evil.kinde.com"}, id="wrong issuer"),
        pytest.param({"exp": int(time.time()) - 60}, id="expired"),
    ],
)
async def test_token_with_bad_claims_is_rejected(
    client: AsyncClient, make_token: TokenFactory, claims: dict[str, object]
) -> None:
    response = await client.get("/api/me", headers=bearer(make_token(**claims)))

    assert response.status_code == 401
