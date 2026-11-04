"""How a group's combined view of a game, and the reasons it's recommended, are sent."""

import uuid
from collections.abc import Mapping, Sequence
from typing import Self

from pydantic import BaseModel

from app.api.friends import PersonRead
from app.recommend import Person, Reason, Rollup, Tone


class MoodTally(BaseModel):
    mood: str
    people: list[PersonRead]  # who tagged the game with it


class RollupRead(BaseModel):
    """What the people in scope think of a game, combined. Ratings and weights lean on BGG's
    while only a few have answered; both are null until someone in scope has."""

    rating: float | None
    rated_by: int
    lowest_rating: float | None
    weight: float | None
    best_at: list[int]  # BGG's poll plus the group's own votes
    length_minutes: int | None  # BGG's time, adjusted by how long it feels to people
    teach_minutes: int | None  # on top, when someone new is coming and someone can teach
    teachers: list[PersonRead]
    new_to_it: list[PersonRead]
    moods: list[MoodTally]
    want_to_play: list[PersonRead]
    wishlist: list[PersonRead]

    @classmethod
    def of(cls, roll: Rollup, people: Mapping[uuid.UUID, PersonRead]) -> Self:
        def read(group: Sequence[Person]) -> list[PersonRead]:
            return [people[p.id] for p in group]

        return cls(
            rating=round(roll.rating, 2) if roll.rating is not None else None,
            rated_by=roll.rated_by,
            lowest_rating=roll.lowest_rating,
            weight=round(roll.weight, 2) if roll.weight is not None else None,
            best_at=roll.best_at,
            length_minutes=roll.length_minutes,
            teach_minutes=roll.teach_minutes,
            teachers=read(roll.teachers),
            new_to_it=read(roll.new_to_it),
            moods=[MoodTally(mood=m, people=read(who)) for m, who in roll.moods.items()],
            want_to_play=read(roll.want_to_play),
            wishlist=read(roll.wishlist),
        )


class ReasonRead(BaseModel):
    text: str
    tone: Tone

    @classmethod
    def of(cls, reason: Reason) -> Self:
        return cls(text=reason.text, tone=reason.tone)
