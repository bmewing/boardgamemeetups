import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.achievements import COLOR_UNLOCKED_BY, GOALS, PIECE_UNLOCKED_BY
from app.models import Game, User
from app.pieces import Achievement, Piece, PieceColor
from tests.conftest import MakePerson, Person
from tests.test_friends_api import make_link
from tests.test_groups_api import DUO, Crew, crew, games, invite, join, make_group, own
from tests.test_meetup_cycle_api import by_game, nominate
from tests.test_meetup_rsvps import add_date, answer

__all__ = ["crew", "games"]  # fixtures used here

STARTER_PIECES = {"meeple", "pawn", "cube", "die"}
STARTER_COLORS = {"teal", "coral", "gold", "cream"}


async def me(client: AsyncClient, who: Person) -> dict[str, Any]:
    body: dict[str, Any] = (await client.get("/api/me", headers=who.headers)).json()
    return body


async def earned(client: AsyncClient, who: Person) -> set[str]:
    return {a["achievement"] for a in (await me(client, who))["achievements"] if a["earned_at"]}


async def log(client: AsyncClient, meetup: str, runner: Person, **body: Any) -> None:
    saved = await client.put(
        f"/api/meetups/{meetup}/log", headers=runner.headers, json={"plays": [], **body}
    )
    assert saved.status_code == 200, saved.text


async def age(db_session: AsyncSession, who: Person, days: int) -> None:
    """Make an account look older than it is."""
    await db_session.execute(
        update(User)
        .where(User.id == uuid.UUID(who.id))
        .values(created_at=datetime.now(UTC) - timedelta(days=days))
    )
    await db_session.commit()


def test_rewards_are_one_each_and_the_starters_are_free() -> None:
    rewards = [*PIECE_UNLOCKED_BY.values(), *COLOR_UNLOCKED_BY.values()]
    assert len(rewards) == len(set(rewards))
    assert {p.value for p in Piece} - {p.value for p in PIECE_UNLOCKED_BY} == STARTER_PIECES
    assert {c.value for c in PieceColor} - {c.value for c in COLOR_UNLOCKED_BY} == STARTER_COLORS


async def test_a_new_account_starts_with_the_starters(
    client: AsyncClient, person: MakePerson
) -> None:
    ann = await person("Ann")

    body = await me(client, ann)

    assert [a["achievement"] for a in body["achievements"]] == [a.value for a in Achievement]
    assert not any(a["earned_at"] for a in body["achievements"])
    assert {p["piece"] for p in body["pieces"] if p["unlocked"]} == STARTER_PIECES
    assert {c["color"] for c in body["colors"] if c["unlocked"]} == STARTER_COLORS
    crown = next(p for p in body["pieces"] if p["piece"] == "crown")
    assert crown == {"piece": "crown", "unlocked_by": "win_game", "unlocked": False}
    standing = {a["achievement"]: a for a in body["achievements"]}
    assert (standing["attend_5"]["progress"], standing["attend_5"]["goal"]) == (0, 5)
    assert standing["win_game"]["goal"] is None


async def test_locked_pieces_and_colors_cant_be_picked_until_unlocked(
    client: AsyncClient, person: MakePerson
) -> None:
    ann = await person("Ann")

    rook = await client.patch("/api/me", headers=ann.headers, json={"piece": "rook"})
    sky = await client.patch("/api/me", headers=ann.headers, json={"piece_color": "sky"})
    gold = await client.patch("/api/me", headers=ann.headers, json={"piece_color": "gold"})
    assert (rook.status_code, sky.status_code, gold.status_code) == (403, 403, 200)

    await make_group(client, ann)
    await client.post("/api/me/calendar-feed", headers=ann.headers)
    picked = await client.patch(
        "/api/me", headers=ann.headers, json={"piece": "rook", "piece_color": "sky"}
    )

    assert picked.status_code == 200, picked.text
    assert (picked.json()["piece"], picked.json()["piece_color"]) == ("rook", "sky")


async def test_new_achievements_stay_new_until_seen(
    client: AsyncClient, person: MakePerson
) -> None:
    ann = await person("Ann")
    await make_group(client, ann)

    new = [a["achievement"] for a in (await me(client, ann))["achievements"] if a["new"]]
    assert new == ["start_group"]

    seen = await client.post("/api/me/achievements/seen", headers=ann.headers)

    assert seen.status_code == 200
    assert not any(a["new"] for a in seen.json()["achievements"])
    assert "start_group" in await earned(client, ann)


async def test_the_group_and_meetup_firsts(client: AsyncClient, crew: Crew, games: None) -> None:
    group, (ann, ben, cat, dee, _eve) = crew
    await own(client, ben, DUO, can_teach=True, teach_minutes=10)
    meetup = await add_date(client, group, ann, date.today() + timedelta(days=3))
    for who in (ben, cat):
        await answer(client, meetup, who, "yes")
    await answer(client, meetup, dee, "maybe")
    nominated = (await nominate(client, meetup, ben, DUO)).json()
    nomination = by_game(nominated)[DUO]["id"]
    await client.put(f"/api/meetups/{meetup}/nominations/{nomination}/vote", headers=cat.headers)
    locked = await client.post(
        f"/api/meetups/{meetup}/lock", headers=ann.headers, json={"nomination_ids": [nomination]}
    )
    assert locked.status_code == 200, locked.text

    anns, bens, cats, dees = [await earned(client, p) for p in (ann, ben, cat, dee)]

    runs = {"start_group", "schedule_meetup", "group_of_4", "lock_pick"}
    assert runs <= anns
    assert not runs & bens
    # Ben is the only owner going, so the lock hands him Duo to bring.
    assert {"join_group", "add_game", "can_teach", "nominate_picked", "bring_game"} <= bens
    assert {"rsvp_yes", "vote"} <= cats
    assert "vote" not in bens  # voting for your own nomination isn't it
    assert "rsvp_yes" not in dees  # a maybe isn't a yes


async def test_a_group_needs_four_members_for_its_runners(
    client: AsyncClient, person: MakePerson
) -> None:
    ann, ben, cat, dee = [await person(n) for n in ("Ann", "Ben", "Cat", "Dee")]
    group = await make_group(client, ann)
    await join(client, group, ann, ben, cat)
    assert "group_of_4" not in await earned(client, ann)
    standing = {a["achievement"]: a for a in (await me(client, ann))["achievements"]}
    assert (standing["group_of_4"]["progress"], standing["group_of_4"]["goal"]) == (3, 4)

    await join(client, group, ann, dee)

    assert "group_of_4" in await earned(client, ann)
    assert "group_of_4" not in await earned(client, ben)


async def test_giving_a_group_a_schedule_counts_as_scheduling(
    client: AsyncClient, person: MakePerson
) -> None:
    ann = await person("Ann")
    group = await make_group(client, ann)

    response = await client.patch(
        f"/api/groups/{group['id']}",
        headers=ann.headers,
        json={"schedule": {"kind": "weekly", "weekday": 3, "starts_on": date.today().isoformat()}},
    )

    assert response.status_code == 200, response.text
    assert "schedule_meetup" in await earned(client, ann)


async def test_a_play_log_records_wins_nights_and_the_logger(
    client: AsyncClient, crew: Crew, games: None
) -> None:
    group, (ann, ben, cat, *_rest) = crew
    past = await add_date(client, group, ann, date.today() - timedelta(days=2))

    await log(
        client,
        past,
        ann,
        attendees=[ann.id, ben.id, cat.id],
        plays=[
            {"game_id": DUO, "coop": False, "players": [ann.id, ben.id], "winners": [ben.id]},
            {"game_id": DUO, "coop": True, "coop_won": True, "players": [cat.id]},
        ],
    )

    anns, bens, cats = [await earned(client, p) for p in (ann, ben, cat)]
    assert {"attend_1", "log_night"} <= anns
    assert not {"win_game", "coop_win"} & anns
    assert {"attend_1", "win_game"} <= bens
    assert not {"coop_win", "log_night"} & bens
    assert {"attend_1", "win_game", "coop_win"} <= cats


async def test_unlocks_stay_when_what_earned_them_is_undone(
    client: AsyncClient, crew: Crew, games: None
) -> None:
    group, (ann, ben, *_rest) = crew
    past = await add_date(client, group, ann, date.today() - timedelta(days=2))
    play = {"game_id": DUO, "coop": False, "players": [ann.id, ben.id], "winners": [ben.id]}
    await log(client, past, ann, attendees=[ann.id, ben.id], plays=[play])

    await log(client, past, ann, attendees=[ann.id, ben.id])

    assert "win_game" in await earned(client, ben)


async def test_game_nights_count_up_through_the_tiers(client: AsyncClient, crew: Crew) -> None:
    group, (ann, ben, *_rest) = crew
    five = GOALS[Achievement.ATTEND_5][1]
    for days_ago in range(1, five + 1):
        assert "attend_5" not in await earned(client, ben)
        past = await add_date(client, group, ann, date.today() - timedelta(days=days_ago))
        await log(client, past, ann, attendees=[ann.id, ben.id])

    standing = {a["achievement"]: a for a in (await me(client, ben))["achievements"]}
    assert standing["attend_5"]["earned_at"] is not None
    assert (standing["attend_20"]["progress"], standing["attend_20"]["earned_at"]) == (five, None)


async def test_friends_count_up_to_a_full_table(client: AsyncClient, person: MakePerson) -> None:
    ann = await person("Ann")
    others = [await person(name) for name in ("Ben", "Cat", "Dee", "Eve", "Fay")]
    for i, other in enumerate(others):
        asked = await client.post(
            "/api/friends/requests", headers=ann.headers, json={"user_id": other.id}
        )
        assert asked.status_code == 200, asked.text
        if i == 0:
            assert "make_friend" not in await earned(client, ann)  # asking isn't enough
        await client.post(f"/api/friends/{ann.id}/accept", headers=other.headers)
        assert "make_friend" in await earned(client, other)
        assert ("friends_5" in await earned(client, ann)) == (i == len(others) - 1)


async def test_rating_ten_games_makes_a_critic(
    client: AsyncClient, person: MakePerson, db_session: AsyncSession
) -> None:
    ann = await person("Ann")
    ids = range(990_400_001, 990_400_011)
    db_session.add_all(Game(id=i, name=f"Zyx Rated {i}") for i in ids)
    await db_session.commit()

    for n, game_id in enumerate(ids, start=1):
        await client.put(f"/api/me/games/{game_id}", headers=ann.headers, json={"rating": 7})
        assert ("rate_games" in await earned(client, ann)) == (n == len(ids))


async def test_a_new_person_through_your_link_is_a_recruit(
    client: AsyncClient, person: MakePerson, db_session: AsyncSession
) -> None:
    ann = await person("Ann")
    link = await make_link(client, ann)
    ben = await person("Ben")  # signed up after the link was made

    accepted = await client.post(f"/api/invites/{link['token']}/accept", headers=ben.headers)

    assert accepted.status_code == 200, accepted.text
    assert {"recruit", "make_friend"} <= await earned(client, ann)
    assert {"joined_by_invite", "make_friend"} <= await earned(client, ben)
    referred_by = await db_session.scalar(
        select(User.referred_by_id).where(User.id == uuid.UUID(ben.id))
    )
    assert referred_by == uuid.UUID(ann.id)


async def test_someone_already_on_the_app_isnt_a_recruit(
    client: AsyncClient, person: MakePerson, db_session: AsyncSession
) -> None:
    ann, ben = await person("Ann"), await person("Ben")
    await age(db_session, ben, days=30)
    link = await make_link(client, ann)

    await client.post(f"/api/invites/{link['token']}/accept", headers=ben.headers)

    assert "recruit" not in await earned(client, ann)
    assert "joined_by_invite" in await earned(client, ben)  # the welcome is still theirs


async def test_a_group_invite_recruits_and_the_recruit_coming_counts_too(
    client: AsyncClient, person: MakePerson, db_session: AsyncSession
) -> None:
    ann, ben = await person("Ann"), await person("Ben")
    await age(db_session, ben, days=30)  # already on the app: nobody's recruit
    group = await make_group(client, ann)
    await join(client, group, ann, ben)
    promoted = await client.patch(
        f"/api/groups/{group['id']}/members/{ben.id}", headers=ann.headers, json={"role": "admin"}
    )
    assert promoted.status_code == 200, promoted.text
    await invite(client, group, ben, "cat@example.com")  # someone not on the app yet
    cat = await person("Cat")
    pending = (await client.get("/api/groups", headers=cat.headers)).json()["invites"]
    await client.post(f"/api/group-invites/{pending[0]['id']}/accept", headers=cat.headers)
    assert "recruit" in await earned(client, ben)
    assert "recruit" not in await earned(client, ann)
    assert "recruit_attends" not in await earned(client, ben)

    past = await add_date(client, group, ann, date.today() - timedelta(days=1))
    await log(client, past, ann, attendees=[ann.id, cat.id])

    assert "recruit_attends" in await earned(client, ben)
    assert "recruit_attends" not in await earned(client, ann)  # Ann didn't bring Cat


async def test_people_see_how_many_achievements_someone_has(
    client: AsyncClient, person: MakePerson
) -> None:
    ann, ben = await person("Ann"), await person("Ben")
    await make_group(client, ann)
    await client.post("/api/me/calendar-feed", headers=ann.headers)

    profile = (await client.get(f"/api/people/{ann.id}", headers=ben.headers)).json()

    assert profile["achievement_count"] == 2
    assert sorted(profile["recent_achievements"]) == ["start_group", "stay_in_loop"]
