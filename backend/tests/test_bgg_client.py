import time
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
import respx

from app.bgg import BggClient, BggError, BggStillPreparing, BggUnknownUser, create_http_client

THING_XML = (Path(__file__).parent / "fixtures" / "bgg" / "thing_wingspan.xml").read_bytes()
EMPTY_ITEMS = b"<items></items>"


@pytest.fixture
async def http() -> AsyncIterator[httpx.AsyncClient]:
    async with create_http_client("test-token") as client:
        yield client


@respx.mock
async def test_requests_carry_the_application_token(http: httpx.AsyncClient) -> None:
    route = respx.get("https://boardgamegeek.com/xmlapi2/thing").respond(content=EMPTY_ITEMS)

    await BggClient(http, min_interval=0).things([1])

    assert route.calls.last.request.headers["Authorization"] == "Bearer test-token"


@respx.mock
async def test_busy_responses_are_retried(http: httpx.AsyncClient) -> None:
    route = respx.get("https://boardgamegeek.com/xmlapi2/thing")
    route.side_effect = [
        httpx.Response(429),
        httpx.Response(503),
        httpx.Response(200, content=THING_XML),
    ]

    games = await BggClient(http, min_interval=0).things([266192])

    assert route.call_count == 3
    assert any(game.name == "Wingspan" for game in games)


@respx.mock
async def test_gives_up_after_max_retries(http: httpx.AsyncClient) -> None:
    route = respx.get("https://boardgamegeek.com/xmlapi2/thing").respond(503)

    with pytest.raises(BggError):
        await BggClient(http, min_interval=0, max_retries=2).things([1])

    assert route.call_count == 3


@respx.mock
async def test_other_errors_fail_without_retrying(http: httpx.AsyncClient) -> None:
    route = respx.get("https://boardgamegeek.com/xmlapi2/thing").respond(401)

    with pytest.raises(BggError):
        await BggClient(http, min_interval=0).things([1])

    assert route.call_count == 1


@respx.mock
async def test_network_errors_are_retried(http: httpx.AsyncClient) -> None:
    route = respx.get("https://boardgamegeek.com/xmlapi2/thing")
    route.side_effect = [httpx.ConnectError("down"), httpx.Response(200, content=EMPTY_ITEMS)]

    await BggClient(http, min_interval=0).things([1])

    assert route.call_count == 2


@respx.mock
async def test_thing_lookups_are_batched_twenty_at_a_time(http: httpx.AsyncClient) -> None:
    route = respx.get("https://boardgamegeek.com/xmlapi2/thing").respond(content=EMPTY_ITEMS)

    await BggClient(http, min_interval=0).things([*range(1, 46), 1, 2])

    batches = [call.request.url.params["id"].split(",") for call in route.calls]
    assert [len(batch) for batch in batches] == [20, 20, 5]


@respx.mock
async def test_requests_are_spaced_apart(http: httpx.AsyncClient) -> None:
    respx.get("https://boardgamegeek.com/xmlapi2/thing").respond(content=EMPTY_ITEMS)
    client = BggClient(http, min_interval=0.2)

    started = time.monotonic()
    await client.things([1])
    await client.things([2])

    assert time.monotonic() - started >= 0.2


COLLECTION_URL = "https://boardgamegeek.com/xmlapi2/collection"
FIXTURES = Path(__file__).parent / "fixtures" / "bgg"


@respx.mock
async def test_collection_asks_for_base_games_and_expansions_apart(
    http: httpx.AsyncClient,
) -> None:
    base = respx.get(COLLECTION_URL, params={"subtype": "boardgame"}).respond(
        content=(FIXTURES / "collection_boardgames.xml").read_bytes()
    )
    expansions = respx.get(COLLECTION_URL, params={"subtype": "boardgameexpansion"}).respond(
        content=(FIXTURES / "collection_expansions.xml").read_bytes()
    )

    entries = await BggClient(http, min_interval=0).collection("someone")

    assert base.calls.last.request.url.params["excludesubtype"] == "boardgameexpansion"
    assert base.calls.last.request.url.params["username"] == "someone"
    assert expansions.called
    assert {e.id for e in entries} == {167791, 224517, 266192, 290837}


@respx.mock
async def test_collection_reports_an_unknown_user(http: httpx.AsyncClient) -> None:
    respx.get(COLLECTION_URL).respond(
        content=b"<errors><error><message>Invalid username specified</message></error></errors>"
    )

    with pytest.raises(BggUnknownUser):
        await BggClient(http, min_interval=0).collection("nobody")


@respx.mock
async def test_collection_still_queued_after_retries(http: httpx.AsyncClient) -> None:
    respx.get(COLLECTION_URL).respond(202)

    with pytest.raises(BggStillPreparing):
        await BggClient(http, min_interval=0, max_retries=1).collection("someone")
