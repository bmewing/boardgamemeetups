import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import LAST_SEEN_GRANULARITY
from app.models import Group, GroupMember, GroupRole, User
from tests.conftest import MakePerson, Person, TokenFactory, bearer


async def make_admin(client: AsyncClient, make_token: TokenFactory, name: str) -> Person:
    """Someone whose Kinde token carries the admin permission."""
    email = f"{name.lower()}@example.com"
    headers = bearer(
        make_token(
            f"kp_{name.lower()}", email=email, given_name=name, permissions=["admin", "other"]
        )
    )
    me = (await client.get("/api/me", headers=headers)).json()
    return Person(id=me["id"], email=email, headers=headers)


@pytest.fixture
async def admin(client: AsyncClient, make_token: TokenFactory) -> Person:
    return await make_admin(client, make_token, "Boss")


async def test_only_admins_can_use_the_portal(
    client: AsyncClient, person: MakePerson, admin: Person
) -> None:
    sam = await person("Sam")

    assert (await client.get("/api/admin/stats", headers=sam.headers)).status_code == 403
    assert (await client.get("/api/admin/users", headers=sam.headers)).status_code == 403
    assert (await client.get("/api/admin/stats", headers=admin.headers)).status_code == 200
    assert (await client.get("/api/me", headers=admin.headers)).json()["is_admin"] is True
    assert (await client.get("/api/me", headers=sam.headers)).json()["is_admin"] is False


async def test_stats_count_users_and_signups(
    client: AsyncClient, person: MakePerson, admin: Person, db_session: AsyncSession
) -> None:
    await person("Sam")
    old = await person("Old")
    await db_session.execute(
        update(User)
        .where(User.id == uuid.UUID(old.id))
        .values(
            created_at=datetime.now(UTC) - timedelta(days=100),
            last_seen_at=datetime.now(UTC) - timedelta(days=100),
        )
    )
    await db_session.commit()

    stats = (await client.get("/api/admin/stats", headers=admin.headers)).json()

    assert stats["users"] == {
        "total": 3,
        "new_7d": 2,
        "new_30d": 2,
        "active_7d": 2,
        "active_30d": 2,
        "banned": 0,
        "admins": 1,
    }
    weeks = stats["signups_by_week"]
    assert len(weeks) == 12
    assert weeks[-1]["count"] == 2
    assert sum(week["count"] for week in weeks) == 2  # the 100-day-old signup is out of range
    assert datetime.fromisoformat(weeks[-1]["week_start"]).weekday() == 0


async def test_list_users_searches_and_filters(
    client: AsyncClient, person: MakePerson, admin: Person
) -> None:
    sam = await person("Sam")
    await person("Pat")
    await client.put(f"/api/admin/users/{sam.id}/ban", json={}, headers=admin.headers)

    def names(page: dict[str, list[dict[str, str]]]) -> list[str]:
        return [user["display_name"] for user in page["users"]]

    everyone = (await client.get("/api/admin/users", headers=admin.headers)).json()
    found = (await client.get("/api/admin/users?q=SAM@", headers=admin.headers)).json()
    banned = (await client.get("/api/admin/users?show=banned", headers=admin.headers)).json()
    admins = (await client.get("/api/admin/users?show=admins", headers=admin.headers)).json()

    assert sorted(names(everyone)) == ["Boss", "Pat", "Sam"]
    assert everyone["total"] == 3
    assert names(found) == ["Sam"]
    assert names(banned) == ["Sam"]
    assert names(admins) == ["Boss"]


async def test_a_banned_user_is_refused_until_unbanned(
    client: AsyncClient, person: MakePerson, admin: Person
) -> None:
    sam = await person("Sam")

    banned = await client.put(
        f"/api/admin/users/{sam.id}/ban", json={"reason": "  Spam  "}, headers=admin.headers
    )
    refused = await client.get("/api/me", headers=sam.headers)
    hidden = await client.get("/api/people/search?q=sam", headers=admin.headers)
    unbanned = await client.delete(f"/api/admin/users/{sam.id}/ban", headers=admin.headers)
    back = await client.get("/api/me", headers=sam.headers)

    assert banned.json()["banned_at"] is not None
    assert banned.json()["ban_reason"] == "Spam"
    assert refused.status_code == 403
    assert refused.json()["detail"] == "This account has been suspended."
    assert hidden.json() == []
    assert unbanned.json()["banned_at"] is None
    assert back.status_code == 200


async def test_deleting_a_user_hands_on_their_groups(
    client: AsyncClient, person: MakePerson, admin: Person, db_session: AsyncSession
) -> None:
    sam = await person("Sam")
    pat = await person("Pat")
    group = Group(name="Crew", time_zone="UTC")
    db_session.add(group)
    await db_session.flush()
    db_session.add_all(
        [
            GroupMember(group_id=group.id, user_id=uuid.UUID(sam.id), role=GroupRole.OWNER),
            GroupMember(group_id=group.id, user_id=uuid.UUID(pat.id), role=GroupRole.MEMBER),
        ]
    )
    await db_session.commit()

    response = await client.delete(f"/api/admin/users/{sam.id}", headers=admin.headers)

    assert response.status_code == 204
    assert await db_session.get(User, uuid.UUID(sam.id)) is None
    heir = await db_session.scalar(select(GroupMember).where(GroupMember.group_id == group.id))
    assert heir is not None
    assert heir.user_id == uuid.UUID(pat.id)
    assert heir.role == GroupRole.OWNER


async def test_admin_follows_the_kinde_permission(
    client: AsyncClient, make_token: TokenFactory
) -> None:
    def headers(*permissions: str) -> dict[str, str]:
        return bearer(make_token("kp_pat", email="pat@example.com", permissions=list(permissions)))

    granted = await client.get("/api/me", headers=headers("admin"))
    portal = await client.get("/api/admin/stats", headers=headers("admin"))
    revoked = await client.get("/api/me", headers=headers("view:stats"))
    refused = await client.get("/api/admin/stats", headers=headers())

    assert granted.json()["is_admin"] is True
    assert portal.status_code == 200
    assert revoked.json()["is_admin"] is False
    assert refused.status_code == 403


async def test_admins_are_protected(
    client: AsyncClient, make_token: TokenFactory, admin: Person
) -> None:
    other = await make_admin(client, make_token, "Other")

    ban_admin = await client.put(f"/api/admin/users/{other.id}/ban", json={}, headers=admin.headers)
    delete_admin = await client.delete(f"/api/admin/users/{other.id}", headers=admin.headers)
    ban_self = await client.put(f"/api/admin/users/{admin.id}/ban", json={}, headers=admin.headers)
    missing = await client.delete(f"/api/admin/users/{uuid.uuid4()}", headers=admin.headers)

    assert ban_admin.status_code == 409
    assert delete_admin.status_code == 409
    assert ban_self.status_code == 400
    assert missing.status_code == 404


async def test_last_seen_is_only_written_every_few_minutes(
    client: AsyncClient, person: MakePerson, db_session: AsyncSession
) -> None:
    sam = await person("Sam")
    user = await db_session.get(User, uuid.UUID(sam.id))
    assert user is not None and user.last_seen_at is not None
    stale = datetime.now(UTC) - LAST_SEEN_GRANULARITY - timedelta(seconds=1)
    recent = datetime.now(UTC) - timedelta(seconds=30)

    user.last_seen_at = recent
    await db_session.commit()
    await client.get("/api/me", headers=sam.headers)
    assert user.last_seen_at == recent

    user.last_seen_at = stale
    await db_session.commit()
    await client.get("/api/me", headers=sam.headers)
    assert user.last_seen_at > stale
