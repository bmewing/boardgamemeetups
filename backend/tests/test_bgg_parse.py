from pathlib import Path

import pytest

from app.bgg.parse import BggResponseError, parse_collection, parse_search, parse_things

FIXTURES = Path(__file__).parent / "fixtures" / "bgg"


def test_parse_things_reads_a_base_game() -> None:
    games = {g.id: g for g in parse_things((FIXTURES / "thing_wingspan.xml").read_bytes())}
    wingspan = games[266192]

    assert wingspan.name == "Wingspan"
    assert wingspan.is_expansion is False
    assert wingspan.base_game_ids == []
    assert wingspan.year_published == 2019
    assert (wingspan.min_players, wingspan.max_players) == (1, 5)
    assert (wingspan.min_playtime, wingspan.max_playtime, wingspan.playing_time) == (40, 70, 70)
    assert wingspan.min_age == 10
    assert wingspan.weight is not None and 2.4 < wingspan.weight < 2.6
    assert wingspan.bgg_rank == 38
    assert wingspan.bgg_users_rated == 116394
    assert wingspan.thumbnail_url and wingspan.thumbnail_url.startswith("https://cf.geekdo-images")
    assert "Animals" in wingspan.categories
    assert "Hand Management" in wingspan.mechanics
    assert wingspan.player_count_votes["3"] == {
        "best": 1270,
        "recommended": 611,
        "not_recommended": 26,
    }
    assert "5+" in wingspan.player_count_votes


def test_parse_things_links_expansions_to_their_base_games() -> None:
    games = {g.id: g for g in parse_things((FIXTURES / "thing_wingspan.xml").read_bytes())}
    promo = games[290837]

    assert promo.is_expansion is True
    assert promo.base_game_ids == [266192, 366161]
    assert promo.bgg_rank is None  # "Not Ranked"


def test_parse_search_lists_each_item_once() -> None:
    hits = parse_search((FIXTURES / "search_wingspan.xml").read_bytes())

    ids = [hit.id for hit in hits]
    assert len(ids) == len(set(ids))
    wingspan = next(hit for hit in hits if hit.id == 266192)
    assert (wingspan.name, wingspan.year_published) == ("Wingspan", 2019)


def test_parse_ignores_items_without_ids_or_names() -> None:
    xml = b'<items><item type="boardgame"><name type="primary" value="No id"/></item></items>'

    assert parse_things(xml) == []
    assert parse_search(xml) == []


def test_parse_collection_merges_copies_and_reads_the_users_answers() -> None:
    entries = {
        e.id: e for e in parse_collection((FIXTURES / "collection_boardgames.xml").read_bytes())
    }

    assert sorted(entries) == [167791, 224517, 266192]
    wingspan = entries[266192]  # listed twice: an owned copy and one for trade
    assert wingspan.own is True
    assert wingspan.rating == 8.5
    assert wingspan.plays == 12
    assert wingspan.comment == "Sleeved."
    assert (wingspan.min_players, wingspan.max_players, wingspan.playing_time) == (1, 5, 70)
    assert wingspan.bgg_rank == 38
    assert wingspan.thumbnail_url == "https://cf.geekdo-images.com/wingspan_small.jpg"
    assert wingspan.is_expansion is False

    mars = entries[167791]
    assert (mars.own, mars.prevowned, mars.want_to_play) == (False, True, True)
    assert mars.rating == 7.25

    brass = entries[224517]
    assert brass.rating is None  # "N/A"
    assert brass.wishlist_priority == 2
    assert brass.comment is None  # only a wishlist comment


def test_parse_collection_reads_expansions() -> None:
    [oceania] = parse_collection((FIXTURES / "collection_expansions.xml").read_bytes())

    assert oceania.is_expansion is True
    assert oceania.preordered is True
    assert oceania.bgg_rank is None  # "Not Ranked"


def test_parse_collection_raises_on_bgg_errors() -> None:
    xml = b"<errors><error><message>Invalid username specified</message></error></errors>"

    with pytest.raises(BggResponseError, match="Invalid username"):
        parse_collection(xml)
