from datetime import date, time

import pytest

from app.groups import table_fit
from app.schedule import DayOfMonth, EveryNWeeks, NthWeekdayOfMonth, instant, next_dates

MON, THU, FRI = 0, 3, 4


def test_every_two_weeks_counts_from_the_first_matching_day() -> None:
    # Sunday the 1st, on Thursdays: the 5th, not the 12th.
    schedule = EveryNWeeks(every_weeks=2, weekday=THU, starts_on=date(2026, 11, 1))

    assert next_dates(schedule, date(2026, 11, 1), 3) == [
        date(2026, 11, 5),
        date(2026, 11, 19),
        date(2026, 12, 3),
    ]
    # Starting later keeps the same rhythm.
    assert next_dates(schedule, date(2026, 11, 6), 1) == [date(2026, 11, 19)]


def test_weekly_includes_today() -> None:
    schedule = EveryNWeeks(weekday=MON, starts_on=date(2026, 11, 2))

    assert next_dates(schedule, date(2026, 11, 9), 2) == [date(2026, 11, 9), date(2026, 11, 16)]


def test_nth_and_last_weekday_of_the_month() -> None:
    second_thursday = NthWeekdayOfMonth(nth=2, weekday=THU, starts_on=date(2026, 11, 1))
    last_friday = NthWeekdayOfMonth(nth=-1, weekday=FRI, starts_on=date(2026, 11, 1))

    assert next_dates(second_thursday, date(2026, 11, 1), 2) == [
        date(2026, 11, 12),
        date(2026, 12, 10),
    ]
    assert next_dates(last_friday, date(2026, 11, 1), 2) == [
        date(2026, 11, 27),
        date(2026, 12, 25),
    ]


def test_day_of_month_skips_months_without_it() -> None:
    schedule = DayOfMonth(day=31, starts_on=date(2026, 11, 1))

    assert next_dates(schedule, date(2026, 11, 1), 3) == [
        date(2026, 12, 31),
        date(2027, 1, 31),
        date(2027, 3, 31),
    ]


def test_local_time_holds_across_daylight_saving() -> None:
    before = instant(date(2026, 10, 29), time(19), "America/Chicago")
    after = instant(date(2026, 11, 5), time(19), "America/Chicago")

    assert before.utcoffset() != after.utcoffset()
    assert before.hour == after.hour == 19


@pytest.mark.parametrize(
    ("players", "confirmed", "split", "expected"),
    [
        pytest.param((2, 4), 3, False, "together", id="seats everyone"),
        pytest.param((2, 4), 5, False, None, id="too many for one table"),
        pytest.param((4, 6), 3, False, None, id="too few"),
        pytest.param((2, 4), 5, True, "split", id="a table of 2 or 3"),
        pytest.param((4, 4), 5, True, None, id="4 of 5 leaves one alone"),
        pytest.param((4, 4), 6, True, "split", id="4 of 6 leaves two"),
        pytest.param((1, 1), 3, True, None, id="solo game"),
        pytest.param((1, 4), 1, True, "together", id="one person coming"),
        pytest.param((2, 4), 0, True, None, id="nobody coming"),
        pytest.param((None, 4), 3, False, "together", id="unknown minimum"),
        pytest.param((2, None), 3, True, None, id="unknown maximum"),
    ],
)
def test_table_fit(
    players: tuple[int | None, int | None], confirmed: int, split: bool, expected: str | None
) -> None:
    assert table_fit(*players, confirmed, split) == expected
