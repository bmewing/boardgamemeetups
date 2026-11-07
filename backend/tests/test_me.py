import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from tests.conftest import TokenFactory, bearer


async def count_users(session: AsyncSession, kinde_id: str) -> int:
    return (
        await session.scalar(
            select(func.count()).select_from(User).where(User.kinde_id == kinde_id)
        )
        or 0
    )


async def test_first_request_creates_the_user(
    client: AsyncClient, make_token: TokenFactory, db_session: AsyncSession
) -> None:
    token = make_token("kp_new", email="sam@example.com", given_name="Sam", family_name="Lee")

    response = await client.get("/api/me", headers=bearer(token))

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "sam@example.com"
    assert body["display_name"] == "Sam Lee"
    assert body["time_zone"] == "UTC"
    assert body["collection_visibility"] == "friends"
    assert await count_users(db_session, "kp_new") == 1


@pytest.mark.parametrize(
    ("sent", "stored"),
    [("America/Chicago", "America/Chicago"), ("Mars/Olympus_Mons", "UTC"), (None, "UTC")],
)
async def test_a_new_account_starts_in_the_browsers_time_zone(
    client: AsyncClient, make_token: TokenFactory, sent: str | None, stored: str
) -> None:
    headers = bearer(make_token("kp_zone"))
    if sent:
        headers["X-Time-Zone"] = sent

    first = await client.get("/api/me", headers=headers)
    # Only the first request sets it; later ones from elsewhere don't move it.
    later = await client.get("/api/me", headers={**headers, "X-Time-Zone": "Asia/Tokyo"})

    assert first.json()["time_zone"] == stored
    assert later.json()["time_zone"] == stored


async def test_display_name_falls_back_to_email(
    client: AsyncClient, make_token: TokenFactory
) -> None:
    token = make_token("kp_no_name", email="meeple.fan@example.com")

    response = await client.get("/api/me", headers=bearer(token))

    assert response.json()["display_name"] == "meeple.fan"


async def test_repeat_requests_reuse_the_user_and_follow_email_changes(
    client: AsyncClient, make_token: TokenFactory, db_session: AsyncSession
) -> None:
    first = await client.get("/api/me", headers=bearer(make_token("kp_x", email="old@example.com")))
    second = await client.get(
        "/api/me", headers=bearer(make_token("kp_x", email="new@example.com"))
    )

    assert first.json()["id"] == second.json()["id"]
    assert second.json()["email"] == "new@example.com"
    assert await count_users(db_session, "kp_x") == 1


async def test_update_profile(client: AsyncClient, make_token: TokenFactory) -> None:
    headers = bearer(make_token("kp_edit", email="e@example.com"))

    response = await client.patch(
        "/api/me",
        headers=headers,
        json={
            "display_name": "  Erin  ",
            "time_zone": "America/Chicago",
            "bgg_username": "erin_plays",
            "collection_visibility": "public",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["display_name"] == "Erin"
    assert body["time_zone"] == "America/Chicago"
    assert body["bgg_username"] == "erin_plays"
    assert body["collection_visibility"] == "public"
    assert (await client.get("/api/me", headers=headers)).json() == body


async def test_blank_bgg_username_clears_it(client: AsyncClient, make_token: TokenFactory) -> None:
    headers = bearer(make_token("kp_clear"))
    await client.patch("/api/me", headers=headers, json={"bgg_username": "someone"})

    response = await client.patch("/api/me", headers=headers, json={"bgg_username": "  "})

    assert response.json()["bgg_username"] is None


@pytest.mark.parametrize(
    "changes",
    [
        pytest.param({"display_name": "   "}, id="blank display name"),
        pytest.param({"display_name": "x" * 81}, id="long display name"),
        pytest.param({"time_zone": "Mars/Olympus_Mons"}, id="unknown time zone"),
        pytest.param({"collection_visibility": "everyone"}, id="unknown visibility"),
    ],
)
async def test_invalid_profile_changes_are_rejected(
    client: AsyncClient, make_token: TokenFactory, changes: dict[str, str]
) -> None:
    response = await client.patch("/api/me", headers=bearer(make_token("kp_bad")), json=changes)

    assert response.status_code == 422


async def test_delete_account(
    client: AsyncClient, make_token: TokenFactory, db_session: AsyncSession
) -> None:
    headers = bearer(make_token("kp_leaving"))
    await client.get("/api/me", headers=headers)

    response = await client.delete("/api/me", headers=headers)

    assert response.status_code == 204
    assert await count_users(db_session, "kp_leaving") == 0


async def test_pick_a_game_piece(client: AsyncClient, make_token: TokenFactory) -> None:
    headers = bearer(make_token("kp_piece"))
    fresh = (await client.get("/api/me", headers=headers)).json()
    assert (fresh["piece"], fresh["piece_color"]) == (None, None)

    picked = await client.patch(
        "/api/me", headers=headers, json={"piece": "top_hat", "piece_color": "plum"}
    )
    assert picked.status_code == 200, picked.text
    assert (picked.json()["piece"], picked.json()["piece_color"]) == ("top_hat", "plum")

    # Other changes leave it alone; null goes back to the meeple.
    renamed = await client.patch("/api/me", headers=headers, json={"display_name": "Hatter"})
    assert renamed.json()["piece"] == "top_hat"
    cleared = await client.patch("/api/me", headers=headers, json={"piece": None})
    assert (cleared.json()["piece"], cleared.json()["piece_color"]) == (None, "plum")

    unknown = await client.patch("/api/me", headers=headers, json={"piece": "spaceship"})
    assert unknown.status_code == 422
