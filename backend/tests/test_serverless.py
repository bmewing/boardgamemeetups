import asyncio
import base64
import json
from typing import Any

from httpx import AsyncClient

from app import serverless
from app.api.games import get_bgg_client
from app.main import app
from tests.conftest import TokenFactory


def web_event(
    method: str,
    path: str,
    *,
    query: str = "",
    body: str = "",
    headers: dict[str, str] | None = None,
    base64_body: bool = False,
) -> dict[str, Any]:
    """A request shaped like DigitalOcean's `web: raw` function event."""
    return {
        "http": {
            "method": method,
            "path": path,
            "queryString": query,
            "body": base64.b64encode(body.encode()).decode() if base64_body else body,
            "isBase64Encoded": base64_body,
            "headers": {
                "host": "boardgamemeetups.example",
                "x-forwarded-proto": "https",
                "content-length": str(len(body)),
                **(headers or {}),
            },
        }
    }


async def test_requests_reach_the_app_and_return_json(client: AsyncClient) -> None:
    result = await serverless.handle(web_event("GET", "/api/health"))

    assert result["statusCode"] == 200
    assert result["headers"]["content-type"] == "application/json"
    assert json.loads(result["body"]) == {"status": "ok", "database": "ok"}


async def test_auth_failures_keep_their_status_and_headers(client: AsyncClient) -> None:
    result = await serverless.handle(web_event("GET", "/api/me"))

    assert result["statusCode"] == 401
    assert result["headers"]["www-authenticate"] == "Bearer"


async def test_query_strings_are_passed_through(
    client: AsyncClient, make_token: TokenFactory
) -> None:
    auth = {"authorization": f"Bearer {make_token('kp_fn')}"}
    app.dependency_overrides[get_bgg_client] = object  # never reached: q fails validation

    result = await serverless.handle(
        web_event("GET", "/api/games/search", query="q=a&limit=5", headers=auth)
    )

    assert result["statusCode"] == 422  # parsed q, and rejected it as too short
    assert json.loads(result["body"])["detail"][0]["loc"] == ["query", "q"]


async def test_json_bodies_are_passed_through(
    client: AsyncClient, make_token: TokenFactory
) -> None:
    headers = {
        "authorization": f"Bearer {make_token('kp_fn')}",
        "content-type": "application/json",
    }
    payload = json.dumps({"display_name": "Functions Fan"})

    plain = await serverless.handle(web_event("PATCH", "/api/me", body=payload, headers=headers))
    encoded = await serverless.handle(
        web_event("PATCH", "/api/me", body=payload, headers=headers, base64_body=True)
    )

    assert plain["statusCode"] == encoded["statusCode"] == 200
    assert json.loads(encoded["body"])["display_name"] == "Functions Fan"


async def test_empty_responses_have_no_body(client: AsyncClient, make_token: TokenFactory) -> None:
    auth = {"authorization": f"Bearer {make_token('kp_leaving_fn')}"}
    await serverless.handle(web_event("GET", "/api/me", headers=auth))

    result = await serverless.handle(web_event("DELETE", "/api/me", headers=auth))

    assert result["statusCode"] == 204
    assert "body" not in result


async def test_entry_point_starts_the_app_and_serves_requests() -> None:
    # The Functions runtime calls main() synchronously, so run it off the test's event loop.
    result = await asyncio.to_thread(serverless.main, web_event("GET", "/api/nope"), None)

    assert result["statusCode"] == 404
