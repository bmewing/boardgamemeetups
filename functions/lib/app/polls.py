"""Find-a-time polls: the half-hour slots a poll offers and the best times among the answers.

A slot is named by its local start time in the poll's time zone, "2026-11-19T19:00". No
conversion to UTC ever happens to the name, so days and labels stay put for everyone and a
daylight-saving change can't move them.
"""

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, time

SLOT_MINUTES = 30
MINUTES_IN_DAY = 24 * 60


def clock(minute: int) -> str:
    """ "19:30", or "24:00" for the midnight that ends a day."""
    return f"{minute // 60:02d}:{minute % 60:02d}"


def slot_id(day: date, minute: int) -> str:
    return f"{day.isoformat()}T{clock(minute)}"


def parse_slot(slot: str) -> tuple[date, int]:
    """The date and minute of day a slot starts; raises ValueError if it isn't one."""
    day, _, hhmm = slot.partition("T")
    hours, _, minutes = hhmm.partition(":")
    return date.fromisoformat(day), int(hours) * 60 + int(minutes)


def day_slots(day: date, start_minute: int, end_minute: int) -> list[str]:
    """Every half hour from `start_minute` up to, not including, `end_minute`."""
    return [slot_id(day, minute) for minute in range(start_minute, end_minute, SLOT_MINUTES)]


def slot_start(slot: str) -> tuple[date, time]:
    day, minute = parse_slot(slot)
    return day, time(minute // 60, minute % 60)


def slot_end(slot: str, minutes: int) -> str:
    """The "HH:MM" a stretch starting at `slot` ends, "24:00" at midnight."""
    _, minute = parse_slot(slot)
    return clock(min(minute + minutes, MINUTES_IN_DAY))


def sorted_slots(slots: Collection[str]) -> list[str]:
    """Deduplicated, in time order (the names sort the same as the times)."""
    return sorted(set(slots))


@dataclass(frozen=True)
class Stretch[P]:
    start: str
    slots: list[str]
    available: list[P]  # who can make all of it
    missing: list[P]  # respondents who can't


def best_stretches[P](
    days: Sequence[Sequence[str]],
    answers: Mapping[P, Collection[str]],
    duration: int,
    limit: int = 5,
) -> list[Stretch[P]]:
    """The times that suit the most people for the whole of `duration` minutes.

    Candidates are ranked by how many people are free for all of it, then earliest. Picks
    never overlap: without that, the top five would be one evening shifted by half an hour.
    A day shorter than the duration offers its whole window. Times nobody can make are left
    out.
    """
    length = -(-duration // SLOT_MINUTES)
    free = {person: set(slots) for person, slots in answers.items()}
    candidates: list[tuple[int, int, int, list[str], list[P]]] = []
    for d, day in enumerate(days):
        span = min(length, len(day))
        for i in range(len(day) - span + 1):
            window = list(day[i : i + span])
            who = [person for person, slots in free.items() if slots.issuperset(window)]
            if who:
                candidates.append((-len(who), d, i, window, who))
    candidates.sort(key=lambda c: c[:3])

    taken: set[str] = set()
    picked: list[Stretch[P]] = []
    for _, _, _, window, who in candidates:
        if taken.intersection(window):
            continue
        taken.update(window)
        picked.append(Stretch(window[0], window, who, []))
        if len(picked) == limit:
            break
    for stretch in picked:
        stretch.missing.extend(person for person in free if person not in stretch.available)
    return picked
