"""What a group thinks of a game, and how well it suits a meetup.

Everything here works on plain data (a game and the answers of the people in scope), so the
scoring can be tested without a database. Groups are small, so roll-ups are worked out on
every request rather than stored. The weights live in `app.recommend_config`.
"""

import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal, Self

from app import recommend_config as cfg
from app.models import Game, Ownership, PlayerCountVote, PlaytimeFeel, UserGame

Tone = Literal["good", "bad", "info"]
VOTES = (PlayerCountVote.BEST, PlayerCountVote.RECOMMENDED, PlayerCountVote.NOT_RECOMMENDED)
NO_PREFERENCE = "no_preference"


@dataclass(frozen=True)
class Person:
    id: uuid.UUID
    name: str


@dataclass(frozen=True)
class Answer:
    """One person's answers about one game."""

    person: Person
    ownership: Ownership | None = None
    wishlist_priority: int | None = None
    want_to_play: bool = False
    rating: float | None = None
    weight_vote: int | None = None
    playtime_feel: PlaytimeFeel | None = None
    can_teach: bool | None = None
    teach_minutes: int | None = None
    plays: int = 0
    player_counts: Mapping[int, PlayerCountVote] = field(default_factory=dict)
    moods: frozenset[str] = frozenset()

    @classmethod
    def of(cls, row: UserGame, person: Person) -> Self:
        return cls(
            person=person,
            ownership=row.ownership,
            wishlist_priority=row.wishlist_priority,
            want_to_play=row.want_to_play,
            rating=row.rating,
            weight_vote=row.weight_vote,
            playtime_feel=row.playtime_feel,
            can_teach=row.can_teach,
            teach_minutes=row.teach_minutes,
            plays=row.plays,
            player_counts={pc.players: pc.vote for pc in row.player_counts},
            moods=frozenset(m.mood_id for m in row.moods),
        )

    @property
    def teaches(self) -> bool:
        """Said they can teach it, or owns it and hasn't said they can't."""
        if self.can_teach is not None:
            return self.can_teach
        return self.ownership == Ownership.OWNED

    @property
    def is_new(self) -> bool:
        """Never owned it, no plays, and no rating (rating a game means you've played it)."""
        owned = self.ownership in (Ownership.OWNED, Ownership.PREVIOUSLY_OWNED)
        return not owned and self.plays == 0 and self.rating is None


@dataclass(frozen=True)
class Rollup:
    """The group's combined view of a game, over the people in scope."""

    rating: float | None  # None until someone in scope has rated it
    rated_by: int
    lowest_rating: float | None
    weight: float | None  # None until someone in scope has voted
    best_at: list[int]
    fit: float | None  # 0 (not recommended) to 1 (best) at the headcount; None if unknown
    fit_vote: PlayerCountVote | None  # what most votes say at the headcount
    length_minutes: int | None  # to play, by BGG's time and how long it feels to people
    teach_minutes: int | None  # added when someone new is coming and someone can teach
    teachers: list[Person]
    new_to_it: list[Person]
    moods: dict[str, list[Person]]  # mood id -> who tagged the game with it
    want_to_play: list[Person]
    wishlist: list[Person]
    vetoes: list[tuple[Person, float]]  # people who rated it at or below the soft-veto mark


@dataclass(frozen=True)
class Reason:
    text: str
    tone: Tone


def _blend(answers: Sequence[float], bgg: float | None) -> float | None:
    """The group's average, pulled toward BGG's value while only a few have answered."""
    if not answers:
        return None
    if bgg is None:
        return sum(answers) / len(answers)
    return (sum(answers) + cfg.PRIOR * bgg) / (len(answers) + cfg.PRIOR)


def combined_votes(
    game: Game, answers: Iterable[Answer]
) -> dict[str, dict[PlayerCountVote, float]]:
    """BGG's poll, scaled down to a few votes in all, plus each person's own votes at full
    weight. Keys are player counts as BGG writes them ("3", or "5+" for more than listed)."""
    votes: dict[str, dict[PlayerCountVote, float]] = {}
    for key, counts in (game.player_count_votes or {}).items():
        total = sum(counts.get(v, 0) for v in VOTES)
        if total:
            votes[key] = {v: cfg.BGG_PLAYER_COUNT_VOTES * counts.get(v, 0) / total for v in VOTES}
    for answer in answers:
        for players, vote in answer.player_counts.items():
            votes.setdefault(str(players), dict.fromkeys(VOTES, 0.0))[vote] += 1
    return votes


def _votes_at(
    votes: Mapping[str, Mapping[PlayerCountVote, float]], players: int
) -> Mapping[PlayerCountVote, float] | None:
    if str(players) in votes:
        return votes[str(players)]
    above = [
        (int(key[:-1]), slot)
        for key, slot in votes.items()
        if key.endswith("+") and key[:-1].isdigit() and int(key[:-1]) <= players
    ]
    return max(above, key=lambda pair: pair[0])[1] if above else None


def rollup(
    game: Game,
    scope: Sequence[Person],
    answers: Mapping[uuid.UUID, Answer],
    players: int | None = None,
) -> Rollup:
    """Combine the answers of everyone in scope. Someone in scope with no answers at all is
    new to the game. `players` is the headcount, when there is one."""
    mine = [answers[p.id] for p in scope if p.id in answers]
    rated = [a for a in mine if a.rating is not None]
    ratings = [a.rating for a in rated if a.rating is not None]

    votes = combined_votes(game, mine)
    best_at = sorted(
        int(key)
        for key, slot in votes.items()
        if key.isdigit()
        and slot[PlayerCountVote.BEST] > slot[PlayerCountVote.RECOMMENDED]
        and slot[PlayerCountVote.BEST] > slot[PlayerCountVote.NOT_RECOMMENDED]
    )
    fit: float | None = None
    fit_vote: PlayerCountVote | None = None
    if players:
        slot = _votes_at(votes, players)
        total = sum(slot.values()) if slot else 0
        if slot and total:
            fit = (slot[PlayerCountVote.BEST] + 0.5 * slot[PlayerCountVote.RECOMMENDED]) / total
            fit_vote = max(VOTES, key=lambda v: slot[v])

    listed = game.playing_time or game.max_playtime or game.min_playtime
    feels = [a.playtime_feel for a in mine if a.playtime_feel is not None]
    length = None
    if listed:
        net = (feels.count(PlaytimeFeel.LONGER) - feels.count(PlaytimeFeel.SHORTER)) / max(
            len(feels), 1
        )
        length = round(listed * (1 + cfg.LENGTH_FEEL * net))

    new_to_it = [p for p in scope if p.id not in answers or answers[p.id].is_new]
    teachers = [a for a in mine if a.teaches]
    teach_times = [a.teach_minutes for a in teachers if a.teach_minutes]
    moods: dict[str, list[Person]] = {}
    for answer in mine:
        for mood in sorted(answer.moods):
            moods.setdefault(mood, []).append(answer.person)

    return Rollup(
        rating=_blend(ratings, game.bgg_rating),
        rated_by=len(ratings),
        lowest_rating=min(ratings) if ratings else None,
        weight=_blend([a.weight_vote for a in mine if a.weight_vote is not None], game.weight),
        best_at=best_at,
        fit=fit,
        fit_vote=fit_vote,
        length_minutes=length,
        teach_minutes=min(teach_times) if new_to_it and teach_times else None,
        teachers=[a.person for a in teachers],
        new_to_it=new_to_it,
        moods=moods,
        want_to_play=[a.person for a in mine if a.want_to_play],
        wishlist=[a.person for a in mine if a.wishlist_priority is not None],
        vetoes=[
            (a.person, a.rating)
            for a in rated
            if a.rating is not None and a.rating <= cfg.SOFT_VETO_AT
        ],
    )


def _names(people: Sequence[Person]) -> str:
    if len(people) == 1:
        return people[0].name
    if len(people) == 2:
        return f"{people[0].name} and {people[1].name}"
    return str(len(people))


def score(
    roll: Rollup,
    *,
    players: int,
    fits_maybes: bool,
    tonight_moods: Iterable[str],
    mood_names: Mapping[str, str],
    recently_played: bool = False,
) -> tuple[float, list[Reason]]:
    """How well the game suits tonight, and the reasons, best first. `tonight_moods` are the
    moods the people coming picked; only ones they've tagged the game with count."""
    total = cfg.PLAYER_COUNT_FIT * (roll.fit if roll.fit is not None else 0.5)
    reasons: list[Reason] = []

    if roll.want_to_play:
        total += cfg.WANT_TO_PLAY * len(roll.want_to_play)
        verb = "wants" if len(roll.want_to_play) == 1 else "want"
        reasons.append(Reason(f"{_names(roll.want_to_play)} {verb} to play", "good"))
    if roll.wishlist:
        total += cfg.WISHLIST * len(roll.wishlist)
        who = roll.wishlist
        text = (
            f"On {who[0].name}'s wishlist"
            if len(who) == 1
            else f"On {who[0].name}'s and {who[1].name}'s wishlists"
            if len(who) == 2
            else f"On {len(who)} wishlists"
        )
        reasons.append(Reason(text, "good"))

    if roll.fit_vote == PlayerCountVote.BEST:
        reasons.append(Reason(f"Best at {players}", "good"))
    elif roll.fit_vote == PlayerCountVote.RECOMMENDED:
        reasons.append(Reason(f"Good at {players}", "info"))
    elif roll.fit_vote == PlayerCountVote.NOT_RECOMMENDED:
        reasons.append(Reason(f"Not great at {players}", "bad"))

    if fits_maybes:
        total += cfg.FITS_THE_MAYBES
        reasons.append(Reason("Fits the maybes too", "good"))

    matched = [m for m in dict.fromkeys(tonight_moods) if m != NO_PREFERENCE and roll.moods.get(m)]
    if matched:
        total += cfg.MOOD_MATCH * len(matched)
        names = ", ".join(mood_names.get(m, m) for m in matched)
        reasons.append(Reason(f"Matches {names}", "good"))

    if roll.new_to_it:
        if roll.teachers:
            teacher = roll.teachers[0].name
            minutes = f" ({roll.teach_minutes} min)" if roll.teach_minutes else ""
            reasons.append(Reason(f"{teacher} can teach{minutes}", "info"))
        else:
            total += cfg.NOBODY_TO_TEACH
            reasons.append(Reason(f"New to {_names(roll.new_to_it)}, nobody to teach", "bad"))

    if roll.rating is not None and roll.rated_by:
        part = (roll.rating - cfg.RATING_MIDPOINT) / cfg.RATING_SPREAD
        total += cfg.RATING * max(-1.0, min(1.0, part))
        reasons.append(Reason(f"Group rating {roll.rating:.1f}", "info"))
    for person, rating in roll.vetoes:
        total += cfg.SOFT_VETO
        reasons.append(Reason(f"{person.name} isn't keen ({rating:g})", "bad"))

    if recently_played:
        total += cfg.RECENTLY_PLAYED
        reasons.append(Reason("Played last time", "bad"))
    return total, reasons
