"""Find base games a user probably owns but hasn't listed: those of expansions they own.

An expansion's base games come from BGG (`games.base_game_ids`), which is only known once
the expansion's details have been fetched; each call fetches a batch of the missing ones and
says how many are still unchecked, so the caller can ask again.

Most expansions fit one base game, and those are suggested by base game. Some fit many
(Dice Throne: Adventures works with any of 29 Dice Throne boxes): suggesting each would
bury the list, so such an expansion is offered once, with its best-known base games to
pick from.
"""

import logging
import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import catalog
from app.bgg import BggClient, BggError
from app.models import Game, Ownership, RemovedGame, UserGame

logger = logging.getLogger(__name__)

OWNED = (Ownership.OWNED, Ownership.PREORDERED)
# Two BGG requests of 20, as for filling in details: well inside the function's time limit.
DETAILS_PER_CALL = 40
OPTIONS_SHOWN = 5


@dataclass
class Suggestion:
    """A base game that the user's expansions need."""

    game: Game
    expansions: list[Game] = field(default_factory=list)
    row: UserGame | None = None  # the user's row for the base game, if any (e.g. wishlisted)


@dataclass
class Choice:
    """An expansion that fits several base games, none of which the user owns."""

    expansion: Game
    options: list[Game]  # the best known first
    option_count: int


@dataclass
class MissingBaseGames:
    suggestions: list[Suggestion]
    choices: list[Choice]
    unchecked: int  # owned expansions whose base games aren't known yet
    hidden: int  # left out because the user removed those games here


def _popularity(game: Game) -> int:
    return game.bgg_users_rated or 0


async def find_missing_base_games(
    session: AsyncSession, bgg: BggClient, user_id: uuid.UUID
) -> MissingBaseGames:
    rows = {
        row.game_id: (row, game)
        for row, game in await session.execute(
            select(UserGame, Game)
            .join(Game, Game.id == UserGame.game_id)
            .where(UserGame.user_id == user_id)
        )
    }
    owned = {game_id for game_id, (row, _game) in rows.items() if row.ownership in OWNED}
    expansions = [
        game for game_id, (_row, game) in rows.items() if game_id in owned and game.is_expansion
    ]

    await catalog.refresh_details(
        session,
        bgg,
        [g for g in expansions if g.details_fetched_at is None][:DETAILS_PER_CALL],
        only_missing=True,
    )
    unchecked = sum(g.details_fetched_at is None for g in expansions)

    removed = set(
        await session.scalars(select(RemovedGame.game_id).where(RemovedGame.user_id == user_id))
    )
    needing = [e for e in expansions if e.base_game_ids and not owned & set(e.base_game_ids)]
    wanted = {base_id for e in needing for base_id in e.base_game_ids}
    known = {g.id: g for g in await session.scalars(select(Game).where(Game.id.in_(wanted)))}
    single = {e.base_game_ids[0] for e in needing if len(e.base_game_ids) == 1}
    if unknown := [i for i in single - known.keys() if i not in removed]:
        # BGG names a base game we've never seen (not in the ranks file): look it up.
        try:
            await catalog.upsert_details(session, await bgg.things(unknown[:DETAILS_PER_CALL]))
            await session.commit()
        except BggError:
            logger.exception("Could not look up %d base games", len(unknown))
        else:
            known |= {
                g.id: g for g in await session.scalars(select(Game).where(Game.id.in_(unknown)))
            }

    by_base: dict[int, Suggestion] = {}
    choices: list[Choice] = []
    hidden: set[int] = set()  # base games left out because the user removed them
    for expansion in needing:
        bases = [known[i] for i in expansion.base_game_ids if i in known and i not in removed]
        hidden |= removed & set(expansion.base_game_ids)
        if not bases:
            continue
        if len(expansion.base_game_ids) == 1:
            base = bases[0]
            suggestion = by_base.setdefault(
                base.id, Suggestion(base, row=rows.get(base.id, (None, None))[0])
            )
            suggestion.expansions.append(expansion)
        else:
            bases.sort(key=_popularity, reverse=True)
            choices.append(Choice(expansion, bases[:OPTIONS_SHOWN], len(bases)))

    suggestions = list(by_base.values())
    # The base games with the most expansions first, then the best known.
    suggestions.sort(key=lambda s: (-len(s.expansions), -_popularity(s.game)))
    for suggestion in suggestions:
        suggestion.expansions.sort(key=lambda g: g.name)
    choices.sort(key=lambda c: c.expansion.name)
    return MissingBaseGames(suggestions, choices, unchecked, len(hidden))
