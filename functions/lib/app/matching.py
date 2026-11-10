"""Match rows of an uploaded game list to catalog games.

Rows with a BGG id match directly. Rows with only a name are compared with every catalog
name (pg_trgm), so typos still find candidates; only an exact, unambiguous name (or an exact
name plus the right year) is matched without asking the user.
"""

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import catalog
from app.bgg import BggClient, BggError, SearchHit
from app.file_import import FileRow
from app.models import Game

logger = logging.getLogger(__name__)

CANDIDATES_SHOWN = 5
CANDIDATES_FETCHED = 10
# Ids BGG has to be asked about (not in the catalog, no name in the file): two requests.
MAX_UNKNOWN_IDS = 40


class MatchStatus(StrEnum):
    MATCHED = "matched"  # sure enough to use without asking
    REVIEW = "review"  # likely candidates; the user picks
    UNMATCHED = "unmatched"  # nothing close; the user searches


@dataclass
class Candidate:
    game: Game
    score: float  # 0-1, how well the name (and year) fit


@dataclass
class RowMatch:
    row: FileRow
    status: MatchStatus
    confidence: float
    game: Game | None = None  # the match, or the best candidate to suggest
    candidates: list[Candidate] = field(default_factory=list)


# Curly quotes, as word processors type them, compare equal to straight ones.
CURLY_QUOTES = {0x2018: "'", 0x2019: "'", 0x201C: '"', 0x201D: '"'}


# "Fox Experiment, The" is how libraries and spreadsheets often sort "The Fox Experiment".
TRAILING_ARTICLE = re.compile(r"^(.*),\s*(the|a|an|la|le|el|les|los|las|der|die|das|il)$")


def normalize(name: str) -> str:
    """Lowercase with tidy spaces and straight quotes, and a trailing article moved back."""
    name = re.sub(r"\s+", " ", name.translate(CURLY_QUOTES)).strip().lower()
    if match := TRAILING_ARTICLE.match(name):
        name = f"{match.group(2)} {match.group(1)}"
    return name


def loose_key(name: str) -> str:
    """The name's letters and digits only: "Fire-Mountain" and "Fire Mountain" are the same."""
    return re.sub(r"[^0-9a-z]+", "", normalize(name))


# With several games of the same name, the best known is taken without asking when it has
# this many times the ratings of the next one (and enough ratings to mean something).
CLEAR_FAVOURITE = 10
MIN_RATINGS = 100
# How well "X" fits a base game named "X: Some Subtitle".
SUBTITLED_SCORE = 0.9


async def _by_id(session: AsyncSession, bgg: BggClient, rows: Sequence[FileRow]) -> dict[int, Game]:
    ids = {row.bgg_id for row in rows if row.bgg_id and row.bgg_id > 0}
    if not ids:
        return {}
    known = set(await session.scalars(select(Game.id).where(Game.id.in_(ids))))
    unknown = [row for row in rows if row.bgg_id in ids - known]
    # A name in the file is enough for a stub; details are fetched later, as for pulls.
    named = {r.bgg_id: r for r in unknown if r.name and r.bgg_id}
    await catalog.insert_search_hits(
        session, [SearchHit(i, r.name or "", r.year) for i, r in named.items()]
    )
    nameless = sorted({r.bgg_id for r in unknown if r.bgg_id and r.bgg_id not in named})
    if nameless:
        try:
            details = await bgg.things(nameless[:MAX_UNKNOWN_IDS])
        except BggError:
            logger.exception("Could not look up %d BGG ids from a file", len(nameless))
        else:
            await catalog.upsert_details(session, details)
    await session.commit()
    return {g.id: g for g in await session.scalars(select(Game).where(Game.id.in_(ids)))}


def _like_prefix(text: str) -> str:
    """A LIKE pattern for names starting with `text`, with LIKE's wildcards escaped."""
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return escaped + "%"


def _is_subtitled(game: Game, q: str) -> bool:
    """A base game whose name is the file's name plus a subtitle ("X: A Deck-Building Game")."""
    return not game.is_expansion and normalize(game.name).startswith(f"{q}:")


async def _candidates(session: AsyncSession, name: str, year: int | None) -> list[Candidate]:
    q = normalize(name)
    lowered = func.lower(Game.name)
    similarity = func.similarity(lowered, q)
    # Two small queries, each served by the name index. Combined with OR, Postgres gives up
    # on the index and scans every game, about 200 ms a row. Games people added themselves
    # (negative ids) never match: an import is only ever matched against BGG's games.
    close = await session.execute(
        select(Game, similarity)
        .where(or_(lowered == q, lowered.op("%")(q)), Game.id > 0)
        .order_by(
            (lowered == q).desc(), similarity.desc(), Game.bgg_users_rated.desc().nulls_last()
        )
        .limit(CANDIDATES_FETCHED)
    )
    # "X: Subtitle" names, best known first; expansions are left out in Python, since
    # filtering them here would also cost the index.
    prefixed = await session.execute(
        select(Game, similarity)
        .where(lowered.like(_like_prefix(f"{q}:"), escape="\\"), Game.id > 0)
        .order_by(Game.bgg_users_rated.desc().nulls_last())
        .limit(CANDIDATES_FETCHED)
    )
    found: dict[int, tuple[Game, float]] = {}
    for game, sim in [*close, *prefixed]:
        found.setdefault(game.id, (game, sim))
    candidates = []
    for game, sim in found.values():
        if loose_key(game.name) == loose_key(q):
            score = 1.0
        elif _is_subtitled(game, q):
            score = SUBTITLED_SCORE
        else:
            score = float(sim)
        if year and game.year_published and game.year_published != year:
            score -= 0.15
        candidates.append(Candidate(game, max(round(score, 2), 0.0)))
    # Best fit first; among equals, the game more people know.
    candidates.sort(key=lambda c: (-c.score, -(c.game.bgg_users_rated or 0)))
    return candidates[:CANDIDATES_SHOWN]


def _clear_favourite(candidates: list[Candidate]) -> Candidate | None:
    """The best-known of these, if it's far better known than the rest."""
    ranked = sorted(candidates, key=lambda c: -(c.game.bgg_users_rated or 0))
    top = ranked[0].game.bgg_users_rated or 0
    runner_up = (ranked[1].game.bgg_users_rated or 0) if len(ranked) > 1 else 0
    if top >= MIN_RATINGS and top >= CLEAR_FAVOURITE * runner_up:
        return ranked[0]
    return None


def _decide(row: FileRow, candidates: list[Candidate]) -> RowMatch:
    if not candidates:
        return RowMatch(row, MatchStatus.UNMATCHED, 0.0)
    q = normalize(row.name or "")
    exact = [c for c in candidates if loose_key(c.game.name) == loose_key(q)]
    fits_year = [c for c in exact if row.year and c.game.year_published == row.year]
    if len(fits_year) == 1:
        return RowMatch(row, MatchStatus.MATCHED, 1.0, fits_year[0].game, candidates)
    if len(exact) == 1 and not row.year:
        return RowMatch(row, MatchStatus.MATCHED, 1.0, exact[0].game, candidates)
    if len(exact) > 1 and not row.year and (favourite := _clear_favourite(exact)):
        return RowMatch(row, MatchStatus.MATCHED, 0.95, favourite.game, candidates)
    subtitled = [c for c in candidates if _is_subtitled(c.game, q)]
    if not exact and subtitled and not row.year and (favourite := _clear_favourite(subtitled)):
        # "Clank! In! Space!" for "Clank! In! Space!: A Deck-Building Adventure".
        return RowMatch(row, MatchStatus.MATCHED, SUBTITLED_SCORE, favourite.game, candidates)
    # Several games share the name, or it's only close: suggest the best and ask.
    best = exact[0] if exact else candidates[0]
    return RowMatch(row, MatchStatus.REVIEW, best.score, best.game, candidates)


async def match_name(session: AsyncSession, name: str) -> Game | None:
    """The catalog game a bare name means, only when it's sure enough to use unasked."""
    row = FileRow(line=0, name=name)
    match = _decide(row, await _candidates(session, name, None))
    return match.game if match.status == MatchStatus.MATCHED else None


async def match_rows(
    session: AsyncSession, bgg: BggClient, rows: Sequence[FileRow]
) -> list[RowMatch]:
    by_id = await _by_id(session, bgg, rows)
    matches = []
    for row in rows:
        if row.bgg_id:
            game = by_id.get(row.bgg_id)
            if game is not None:
                matches.append(RowMatch(row, MatchStatus.MATCHED, 1.0, game))
                continue
            row.problems.append(f"BGG has no game with id {row.bgg_id}")
            if not row.name:
                matches.append(RowMatch(row, MatchStatus.UNMATCHED, 0.0))
                continue
        matches.append(_decide(row, await _candidates(session, row.name or "", row.year)))
    return matches
