import time
from datetime import date, timedelta

import pytest

from stash.views import (
    NO_HORIZON,
    VIEWS,
    Horizon,
    admits,
    age,
    civil,
    freshness,
    horizon_at,
    is_view,
    iso,
    ordinal,
    stamp_for,
    window,
)


def day(text):
    return time.strptime(text, "%Y-%m-%d")


MONDAY = day("2026-10-26")


@pytest.mark.parametrize(
    "name, expected",
    [
        *[(name, True) for name in VIEWS],
        ("2026-10-20", True),
        ("2028-02-29", True),
        ("2026-13-01", False),
        ("2026-10-32", False),
        ("26-10-20", False),
        ("todays", False),
        ("Today", False),
        ("nextweek", False),
        ("next-decade", False),
        ("grocery", False),
        ("", False),
    ],
)
def test_is_view_knows_the_reserved_names_and_any_date(name, expected):
    assert is_view(name) is expected, "a view is one of the reserved names or a YYYY-MM-DD date"


def test_views_are_listed_in_their_natural_order():
    assert VIEWS == (
        "today",
        "yesterday",
        "tomorrow",
        "week",
        "last-week",
        "next-week",
        "month",
        "last-month",
        "next-month",
        "quarter",
        "last-quarter",
        "next-quarter",
        "year",
        "last-year",
        "next-year",
        "decade",
    ), "rows for a typed prefix come out in this order: the current period, then last, then next"


@pytest.mark.parametrize(
    "view, now, first, last",
    [
        ("today", "2026-10-26", "2026-10-26", "2026-10-26"),
        ("yesterday", "2026-10-26", "2026-10-25", "2026-10-25"),
        ("yesterday", "2026-01-01", "2025-12-31", "2025-12-31"),
        ("yesterday", "2026-03-01", "2026-02-28", "2026-02-28"),
        ("yesterday", "2028-03-01", "2028-02-29", "2028-02-29"),
        ("week", "2026-10-26", "2026-10-26", "2026-11-01"),
        ("week", "2026-10-28", "2026-10-26", "2026-11-01"),
        ("week", "2026-11-01", "2026-10-26", "2026-11-01"),
        ("week", "2026-12-30", "2026-12-28", "2027-01-03"),
        ("week", "2027-01-01", "2026-12-28", "2027-01-03"),
        ("month", "2026-10-26", "2026-10-01", "2026-10-31"),
        ("month", "2026-02-10", "2026-02-01", "2026-02-28"),
        ("month", "2028-02-10", "2028-02-01", "2028-02-29"),
        ("month", "2026-12-31", "2026-12-01", "2026-12-31"),
        ("quarter", "2026-10-26", "2026-10-01", "2026-12-31"),
        ("quarter", "2026-05-05", "2026-04-01", "2026-06-30"),
        ("quarter", "2026-01-01", "2026-01-01", "2026-03-31"),
        ("quarter", "2026-09-30", "2026-07-01", "2026-09-30"),
        ("year", "2026-10-26", "2026-01-01", "2026-12-31"),
        ("year", "2026-01-01", "2026-01-01", "2026-12-31"),
        ("decade", "2026-10-26", "2020-01-01", "2029-12-31"),
        ("decade", "2030-01-01", "2030-01-01", "2039-12-31"),
        ("decade", "2029-12-31", "2020-01-01", "2029-12-31"),
        ("2026-10-20", "2026-10-26", "2026-10-20", "2026-10-20"),
        ("tomorrow", "2026-10-26", "2026-10-27", "2026-10-27"),
        ("tomorrow", "2026-10-31", "2026-11-01", "2026-11-01"),
        ("tomorrow", "2026-12-31", "2027-01-01", "2027-01-01"),
        ("tomorrow", "2028-02-28", "2028-02-29", "2028-02-29"),
        ("last-week", "2026-10-26", "2026-10-19", "2026-10-25"),
        ("last-week", "2027-01-01", "2026-12-21", "2026-12-27"),
        ("next-week", "2026-10-26", "2026-11-02", "2026-11-08"),
        ("next-week", "2026-10-25", "2026-10-26", "2026-11-01"),
        ("next-week", "2026-12-30", "2027-01-04", "2027-01-10"),
        ("last-month", "2026-10-26", "2026-09-01", "2026-09-30"),
        ("last-month", "2026-01-15", "2025-12-01", "2025-12-31"),
        ("last-month", "2026-03-31", "2026-02-01", "2026-02-28"),
        ("next-month", "2026-10-26", "2026-11-01", "2026-11-30"),
        ("next-month", "2026-12-15", "2027-01-01", "2027-01-31"),
        ("next-month", "2028-01-31", "2028-02-01", "2028-02-29"),
        ("last-quarter", "2026-10-26", "2026-07-01", "2026-09-30"),
        ("last-quarter", "2026-02-01", "2025-10-01", "2025-12-31"),
        ("next-quarter", "2026-10-26", "2027-01-01", "2027-03-31"),
        ("next-quarter", "2026-05-05", "2026-07-01", "2026-09-30"),
        ("last-year", "2026-10-26", "2025-01-01", "2025-12-31"),
        ("next-year", "2026-10-26", "2027-01-01", "2027-12-31"),
    ],
)
def test_window_is_the_calendar_period_around_now(view, now, first, last):
    assert window(view, day(now)) == (first, last), (
        f"{view}/ on {now} should span {first}..{last}: calendar periods, weeks starting on Monday"
    )


@pytest.mark.parametrize(
    "view, date, expected",
    [
        ("today", "2026-10-26", True),
        ("today", "2026-10-25", False),
        ("today", "2026-10-27", False),
        ("today", "", True),
        ("week", "2026-10-26", True),
        ("week", "2026-11-01", True),
        ("week", "2026-11-02", False),
        ("week", "2026-10-25", False),
        ("week", "", True),
        ("year", "2026-01-01", True),
        ("year", "2025-12-31", False),
        ("year", "", True),
        ("2026-10-20", "2026-10-20", True),
        ("2026-10-20", "2026-10-21", False),
        ("2026-10-20", "", True),
    ],
)
def test_admits_dated_lines_inside_the_window_and_undated_lines_always(view, date, expected):
    assert admits(window(view, MONDAY), date) is expected, (
        "a view holds every line stamped inside its window and every line without a stamp"
    )


@pytest.mark.parametrize(
    "date, expected",
    [
        ("2026-10-26", "today"),
        ("2026-10-25", "1d"),
        ("2026-10-20", "6d"),
        ("2026-10-19", "1w"),
        ("2026-09-29", "3w"),
        ("2026-09-28", "4w"),
        ("2026-09-26", "1mo"),
        ("2026-04-29", "6mo"),
        ("2025-10-27", "12mo"),
        ("2025-10-26", "1y"),
        ("2016-01-01", "10y"),
        ("2026-10-27", "2026-10-27"),
        ("2027-01-01", "2027-01-01"),
    ],
)
def test_age_is_a_short_word_for_how_long_ago(date, expected):
    assert age(date, MONDAY) == expected, "age reads today, Nd, Nw, Nmo, Ny; a date in the future shows as is"


@pytest.mark.parametrize(
    "view, expected",
    [
        ("today", "2026-10-26"),
        ("yesterday", "2026-10-25"),
        ("tomorrow", "2026-10-27"),
        ("2026-10-20", "2026-10-20"),
        ("2026-11-03", "2026-11-03"),
        ("week", "2026-10-26"),
        ("last-week", "2026-10-19"),
        ("next-week", "2026-11-02"),
        ("month", "2026-10-26"),
        ("last-month", "2026-09-01"),
        ("next-month", "2026-11-01"),
        ("quarter", "2026-10-26"),
        ("next-quarter", "2027-01-01"),
        ("year", "2026-10-26"),
        ("last-year", "2025-01-01"),
        ("next-year", "2027-01-01"),
        ("decade", "2026-10-26"),
        ("", "2026-10-26"),
        ("grocery", "2026-10-26"),
    ],
)
def test_stamp_for_is_the_first_day_of_a_shifted_view_and_today_for_the_current_ones(view, expected):
    assert stamp_for(view, MONDAY) == expected, (
        "last-*, next-*, yesterday, tomorrow and a date stamp their window's first day; the current period means today"
    )


def test_iso_formats_now_as_a_stamp_date():
    assert iso(MONDAY) == "2026-10-26", "iso should write dates the way stamps are written"


ROOT = Horizon("2026-10-26", "2026-10-26", "2026-11-08")
DATES = ["2026-10-20", "", "2026-12-24", "2026-10-26", "2026-11-08", "2026-10-25", "", "2026-10-27", "2027-03-01"]


def ordered_by(horizon, dates=DATES):
    return sorted(dates, key=lambda date: freshness(date, horizon))


def test_freshness_at_the_root_lifts_today_and_the_near_future_above_the_evergreens():
    assert ordered_by(ROOT) == [
        "2026-10-26",
        "2026-10-27",
        "2026-11-08",
        "",
        "",
        "2026-12-24",
        "2027-03-01",
        "2026-10-25",
        "2026-10-20",
    ], "today, up to the end of next week soonest first, undated, the far future soonest first, the past newest first"


def test_freshness_inside_a_view_keeps_the_window_ahead_of_the_evergreens():
    week = Horizon("2026-10-28", "2026-10-26", "2026-11-01")
    dates = ["2026-10-26", "", "2026-11-01", "2026-10-28", "2026-10-27", "2026-10-30"]

    assert ordered_by(week, dates) == ["2026-10-28", "2026-10-30", "2026-11-01", "2026-10-27", "2026-10-26", ""], (
        "on a Wednesday, week/ reads today, the rest of the week, the days already gone newest first, then evergreens"
    )


def test_freshness_inside_a_past_view_puts_its_lines_before_the_evergreens():
    assert ordered_by(Horizon("2026-10-26", "2026-10-25", "2026-10-25"), ["", "2026-10-25", ""]) == [
        "2026-10-25",
        "",
        "",
    ], "yesterday/ starts with yesterday's lines, not with every evergreen"


def test_freshness_without_a_horizon_ignores_dates():
    assert ordered_by(NO_HORIZON) == DATES, "with no reference day, dates play no part and the order given stands"


def test_freshness_is_stable_for_equal_dates():
    assert freshness("2026-10-20", ROOT) == freshness("2026-10-20", ROOT), (
        "equal dates must compare equal so file order decides"
    )


def test_horizon_at_the_root_reaches_the_end_of_next_week():
    assert horizon_at(MONDAY) == ROOT, "a bare search lifts lines up to next Sunday"
    assert horizon_at(day("2026-10-25")) == Horizon("2026-10-25", "2026-10-25", "2026-11-01"), (
        "on a Sunday that is one week out, on a Monday thirteen days"
    )


def test_horizon_at_inside_a_view_is_its_window():
    assert horizon_at(MONDAY, ("2026-10-19", "2026-10-25")) == Horizon("2026-10-26", "2026-10-19", "2026-10-25"), (
        "a view ranks its own window as near, whatever it spans"
    )


@pytest.mark.parametrize("start", ["1999-12-25", "2026-10-26", "2099-12-25", "2400-02-20"])
def test_ordinal_and_civil_agree_with_the_calendar_across_leap_years(start):
    first = date.fromisoformat(start)

    for offset in range(0, 1500, 7):
        current = first + timedelta(days=offset)
        days = ordinal(current.year, current.month, current.day)

        assert days - ordinal(first.year, first.month, first.day) == offset, "ordinal counts days like the calendar"
        assert civil(days) == (current.year, current.month, current.day), "civil inverts ordinal"
