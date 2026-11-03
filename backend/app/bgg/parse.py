"""Turn BGG XML API2 responses into plain data."""

from dataclasses import dataclass, field
from xml.etree.ElementTree import Element

from defusedxml.ElementTree import fromstring

from app.models import PlayerCountVotes

VOTE_KEYS = {"Best": "best", "Recommended": "recommended", "Not Recommended": "not_recommended"}


@dataclass(frozen=True)
class SearchHit:
    id: int
    name: str
    year_published: int | None


@dataclass
class GameDetails:
    id: int
    name: str
    is_expansion: bool
    year_published: int | None = None
    base_game_ids: list[int] = field(default_factory=list)
    thumbnail_url: str | None = None
    image_url: str | None = None
    min_players: int | None = None
    max_players: int | None = None
    min_playtime: int | None = None
    max_playtime: int | None = None
    playing_time: int | None = None
    min_age: int | None = None
    weight: float | None = None
    bgg_rank: int | None = None
    bgg_rating: float | None = None
    bgg_users_rated: int | None = None
    categories: list[str] = field(default_factory=list)
    mechanics: list[str] = field(default_factory=list)
    player_count_votes: PlayerCountVotes = field(default_factory=dict)


def _int(value: str | None) -> int | None:
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def _float(value: str | None) -> float | None:
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None


def _value(item: Element | None, tag: str) -> str | None:
    if item is None:
        return None
    node = item.find(tag)
    return node.get("value") if node is not None else None


def _positive[N: (int, float)](value: N | None) -> N | None:
    """BGG uses 0 for "unknown" in years, counts, times, ages and weights."""
    return value if value else None


def _primary_name(item: Element) -> str | None:
    for name in item.iterfind("name"):
        if name.get("type") == "primary":
            return name.get("value")
    return None


def parse_search(xml: bytes) -> list[SearchHit]:
    hits: dict[int, SearchHit] = {}
    for item in fromstring(xml).iterfind("item"):
        bgg_id = _int(item.get("id"))
        name = _primary_name(item)
        if bgg_id is None or name is None:
            continue
        # The same item can be listed once per matching type; keep the first.
        hits.setdefault(bgg_id, SearchHit(bgg_id, name, _int(_value(item, "yearpublished"))))
    return list(hits.values())


def _player_count_votes(item: Element) -> PlayerCountVotes:
    votes: PlayerCountVotes = {}
    for poll in item.iterfind("poll"):
        if poll.get("name") != "suggested_numplayers":
            continue
        for results in poll.iterfind("results"):
            players = results.get("numplayers")
            if not players:
                continue
            counts = {key: 0 for key in VOTE_KEYS.values()}
            for result in results.iterfind("result"):
                key = VOTE_KEYS.get(result.get("value", ""))
                if key:
                    counts[key] = _int(result.get("numvotes")) or 0
            votes[players] = counts
    return votes


def _parse_thing(item: Element) -> GameDetails | None:
    bgg_id = _int(item.get("id"))
    name = _primary_name(item)
    if bgg_id is None or name is None:
        return None

    links = list(item.iterfind("link"))
    is_expansion = item.get("type") == "boardgameexpansion"
    ratings = item.find("statistics/ratings")
    rank = None
    if ratings is not None:
        for node in ratings.iterfind("ranks/rank"):
            if node.get("name") == "boardgame":
                rank = _int(node.get("value"))  # "Not Ranked" parses to None

    return GameDetails(
        id=bgg_id,
        name=name,
        is_expansion=is_expansion,
        year_published=_positive(_int(_value(item, "yearpublished"))),
        # On an expansion, inbound expansion links point at the games it expands.
        base_game_ids=[
            game_id
            for link in links
            if is_expansion
            and link.get("type") == "boardgameexpansion"
            and link.get("inbound") == "true"
            and (game_id := _int(link.get("id"))) is not None
        ],
        thumbnail_url=(item.findtext("thumbnail") or "").strip() or None,
        image_url=(item.findtext("image") or "").strip() or None,
        min_players=_positive(_int(_value(item, "minplayers"))),
        max_players=_positive(_int(_value(item, "maxplayers"))),
        min_playtime=_positive(_int(_value(item, "minplaytime"))),
        max_playtime=_positive(_int(_value(item, "maxplaytime"))),
        playing_time=_positive(_int(_value(item, "playingtime"))),
        min_age=_positive(_int(_value(item, "minage"))),
        weight=_positive(_float(_value(ratings, "averageweight"))),
        bgg_rank=rank,
        bgg_rating=_positive(_float(_value(ratings, "average"))),
        bgg_users_rated=_int(_value(ratings, "usersrated")),
        categories=[
            link.get("value", "") for link in links if link.get("type") == "boardgamecategory"
        ],
        mechanics=[
            link.get("value", "") for link in links if link.get("type") == "boardgamemechanic"
        ],
        player_count_votes=_player_count_votes(item),
    )


def parse_things(xml: bytes) -> list[GameDetails]:
    return [
        details
        for item in fromstring(xml).iterfind("item")
        if (details := _parse_thing(item)) is not None
    ]


class BggResponseError(Exception):
    """BGG answered with an <errors> document instead of data (e.g. an unknown username)."""


@dataclass
class CollectionEntry:
    """One game in a BGG user's collection: catalog basics plus what the user recorded.

    BGG lists a game once per copy, so `parse_collection` merges entries with the same id.
    """

    id: int
    name: str
    is_expansion: bool
    year_published: int | None = None
    thumbnail_url: str | None = None
    image_url: str | None = None
    min_players: int | None = None
    max_players: int | None = None
    min_playtime: int | None = None
    max_playtime: int | None = None
    playing_time: int | None = None
    bgg_rank: int | None = None
    bgg_rating: float | None = None
    bgg_users_rated: int | None = None

    own: bool = False
    prevowned: bool = False
    preordered: bool = False
    wishlist_priority: int | None = None  # set only when wishlisted
    want_to_play: bool = False
    rating: float | None = None
    plays: int = 0
    comment: str | None = None


def _attr(node: Element | None, key: str) -> str | None:
    return node.get(key) if node is not None else None


def _flag(status: Element | None, name: str) -> bool:
    return _attr(status, name) == "1"


def _text(item: Element, tag: str) -> str | None:
    return (item.findtext(tag) or "").strip() or None


def _parse_collection_item(item: Element) -> CollectionEntry | None:
    bgg_id = _int(item.get("objectid"))
    name = _text(item, "name")
    if bgg_id is None or name is None:
        return None
    stats = item.find("stats")
    rating = stats.find("rating") if stats is not None else None
    status = item.find("status")
    rank = None
    if rating is not None:
        for node in rating.iterfind("ranks/rank"):
            if node.get("name") == "boardgame":
                rank = _int(node.get("value"))
    wishlisted = _flag(status, "wishlist")
    return CollectionEntry(
        id=bgg_id,
        name=name,
        is_expansion=item.get("subtype") == "boardgameexpansion",
        year_published=_positive(_int(_text(item, "yearpublished"))),
        thumbnail_url=_text(item, "thumbnail"),
        image_url=_text(item, "image"),
        min_players=_positive(_int(_attr(stats, "minplayers"))),
        max_players=_positive(_int(_attr(stats, "maxplayers"))),
        min_playtime=_positive(_int(_attr(stats, "minplaytime"))),
        max_playtime=_positive(_int(_attr(stats, "maxplaytime"))),
        playing_time=_positive(_int(_attr(stats, "playingtime"))),
        bgg_rank=rank,
        bgg_rating=_positive(_float(_value(rating, "average"))),
        bgg_users_rated=_int(_value(rating, "usersrated")),
        own=_flag(status, "own"),
        prevowned=_flag(status, "prevowned"),
        preordered=_flag(status, "preordered"),
        wishlist_priority=_int(_attr(status, "wishlistpriority")) if wishlisted else None,
        want_to_play=_flag(status, "wanttoplay"),
        # "N/A" when the user hasn't rated it.
        rating=_positive(_float(_attr(rating, "value"))),
        plays=_int(_text(item, "numplays")) or 0,
        comment=_text(item, "comment"),
    )


def _merge_copies(first: CollectionEntry, other: CollectionEntry) -> None:
    """Fold a second copy of the same game into the first entry, in place."""
    first.own |= other.own
    first.prevowned |= other.prevowned
    first.preordered |= other.preordered
    first.want_to_play |= other.want_to_play
    priorities = [p for p in (first.wishlist_priority, other.wishlist_priority) if p]
    first.wishlist_priority = min(priorities) if priorities else None
    first.rating = first.rating or other.rating
    first.plays = max(first.plays, other.plays)
    first.comment = first.comment or other.comment
    for key in ("thumbnail_url", "image_url"):
        if getattr(first, key) is None:
            setattr(first, key, getattr(other, key))


def parse_collection(xml: bytes) -> list[CollectionEntry]:
    root = fromstring(xml)
    if root.tag == "errors":
        message = root.findtext("error/message") or "BGG returned an error"
        raise BggResponseError(message.strip())
    entries: dict[int, CollectionEntry] = {}
    for item in root.iterfind("item"):
        entry = _parse_collection_item(item)
        if entry is None:
            continue
        if entry.id in entries:
            _merge_copies(entries[entry.id], entry)
        else:
            entries[entry.id] = entry
    return list(entries.values())
