"""Serve the FastAPI app from a DigitalOcean web function (`web: raw`).

App Platform routes `/api/core/app/<rest>` to this function and passes `/<rest>` as
`http.path`, so the frontend's production API base is `/api/core/app` and FastAPI sees the
same `/api/...` paths as in local development.
"""

import asyncio
import base64
from contextlib import AbstractAsyncContextManager
from typing import Any

import httpx

from app.main import app

# Hop-by-hop or recomputed headers that must not be replayed into the ASGI request.
DROPPED_HEADERS = {"content-length", "transfer-encoding", "connection", "host"}
TEXT_TYPES = ("text/", "application/json", "application/problem+json")

# A warm function container handles one request at a time and keeps this module loaded, so
# one event loop and one app lifespan are reused across invocations.
_loop = asyncio.new_event_loop()
_lifespan: AbstractAsyncContextManager[Any] | None = None


async def handle(event: dict[str, Any]) -> dict[str, Any]:
    http = event.get("http", {})
    headers = {
        key.lower(): value
        for key, value in (http.get("headers") or {}).items()
        if key.lower() not in DROPPED_HEADERS
    }
    raw_body = http.get("body") or ""
    body = base64.b64decode(raw_body) if http.get("isBase64Encoded") else raw_body.encode()
    path = http.get("path") or "/"
    query = http.get("queryString") or ""
    host = (http.get("headers") or {}).get("host", "localhost")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=f"https://{host}") as client:
        response = await client.request(
            http.get("method", "GET"),
            f"{path}?{query}" if query else path,
            headers=headers,
            content=body,
        )

    content_type = response.headers.get("content-type", "")
    result: dict[str, Any] = {
        "statusCode": response.status_code,
        "headers": {
            key: value
            for key, value in response.headers.items()
            if key.lower() not in DROPPED_HEADERS
        },
    }
    if response.content:
        if content_type.startswith(TEXT_TYPES):
            result["body"] = response.text
        else:
            result["body"] = base64.b64encode(response.content).decode()
    return result


async def _start_app() -> None:
    global _lifespan
    if _lifespan is None:
        _lifespan = app.router.lifespan_context(app)
        await _lifespan.__aenter__()


def main(event: dict[str, Any], context: object = None) -> dict[str, Any]:
    """DigitalOcean Functions entry point."""
    _loop.run_until_complete(_start_app())
    return _loop.run_until_complete(handle(event))
