from httpx import AsyncClient

from tests.conftest import MakePerson, Person, TokenFactory, bearer


async def sign_in(client: AsyncClient, make_token: TokenFactory, sub: str, **claims: str) -> Person:
    headers = bearer(make_token(sub, **claims))
    me = (await client.get("/api/me", headers=headers)).json()
    return Person(id=me["id"], email=claims.get("email", ""), headers=headers)


async def name_of(client: AsyncClient, who: Person) -> str:
    name: str = (await client.get("/api/me", headers=who.headers)).json()["display_name"]
    return name


async def test_new_accounts_get_a_free_name(client: AsyncClient, make_token: TokenFactory) -> None:
    first = await sign_in(client, make_token, "kp_sam1", given_name="Sam", family_name="Lee")
    second = await sign_in(client, make_token, "kp_sam2", given_name="sam", family_name="lee")
    third = await sign_in(client, make_token, "kp_sam3", given_name="Sam", family_name="  Lee")

    assert await name_of(client, first) == "Sam Lee"
    assert await name_of(client, second) == "sam lee 2"
    assert await name_of(client, third) == "Sam Lee 3"


async def test_names_are_unique_ignoring_case(client: AsyncClient, person: MakePerson) -> None:
    ann, ben = await person("Ann"), await person("Ben")

    taken = await client.patch("/api/me", headers=ben.headers, json={"display_name": " ANN "})
    spaced = await client.patch("/api/me", headers=ben.headers, json={"display_name": "Big   Ben"})
    recased = await client.patch("/api/me", headers=ann.headers, json={"display_name": "ann"})

    assert taken.status_code == 409
    assert taken.json()["detail"] == "That name is taken. Try another."
    assert spaced.json()["display_name"] == "Big Ben"
    assert recased.json()["display_name"] == "ann"


async def search(client: AsyncClient, who: Person, q: str) -> list[tuple[str, str]]:
    response = await client.get("/api/people/search", headers=who.headers, params={"q": q})
    assert response.status_code == 200, response.text
    return [(m["person"]["display_name"], m["relation"]) for m in response.json()]


async def test_search_suggests_names_friends_first(client: AsyncClient, person: MakePerson) -> None:
    ann, *_ = [await person(n) for n in ("Ann", "Bea", "Bob", "Cat")]
    rebecca = await person("Rebecca")
    await client.patch("/api/me", headers=rebecca.headers, json={"display_name": "Rebecca Bell"})
    await client.post(
        "/api/friends/requests", headers=ann.headers, json={"email": "bob@example.com"}
    )

    # Bob first: Ann has asked him. Then names starting with "b", then a later word.
    assert await search(client, ann, "b") == []  # too short
    assert await search(client, ann, "be") == [("Bea", "none"), ("Rebecca Bell", "none")]
    assert await search(client, ann, "bo") == [("Bob", "outgoing")]
    # Never yourself, and percent signs are just characters.
    assert await search(client, ann, "an") == []
    assert await search(client, ann, "%%") == []


async def test_search_lists_friends_before_others(client: AsyncClient, person: MakePerson) -> None:
    ann, _bea, bex = await person("Ann"), await person("Bea"), await person("Bex")
    await client.post("/api/friends/requests", headers=ann.headers, json={"user_id": bex.id})
    await client.post(f"/api/friends/{ann.id}/accept", headers=bex.headers)

    assert await search(client, ann, "be") == [("Bex", "friends"), ("Bea", "none")]


async def test_emails_match_only_in_full(client: AsyncClient, person: MakePerson) -> None:
    ann, _ben = await person("Ann"), await person("Ben")

    assert await search(client, ann, "ben@example") == []
    assert await search(client, ann, "BEN@example.com") == [("Ben", "none")]


async def test_blocks_hide_people_both_ways(client: AsyncClient, person: MakePerson) -> None:
    ann, ben, bea = await person("Ann"), await person("Ben"), await person("Bea")
    await client.put(f"/api/blocks/{ann.id}", headers=ben.headers)
    await client.put(f"/api/blocks/{bea.id}", headers=ann.headers)

    assert await search(client, ann, "be") == []
    assert await search(client, ben, "an") == []


async def test_friend_request_to_someone_picked(client: AsyncClient, person: MakePerson) -> None:
    ann, ben = await person("Ann"), await person("Ben")

    sent = await client.post("/api/friends/requests", headers=ann.headers, json={"user_id": ben.id})
    nobody = await client.post(
        "/api/friends/requests",
        headers=ann.headers,
        json={"user_id": "00000000-0000-0000-0000-000000000000"},
    )
    neither = await client.post("/api/friends/requests", headers=ann.headers, json={})

    assert sent.json()["relation"] == "outgoing"
    assert nobody.status_code == 404
    assert neither.status_code == 422
