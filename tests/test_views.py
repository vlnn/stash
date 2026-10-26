import time

import pytest

from stash.views import VIEWS, admits, age, freshness, is_view, iso, stamp_for, window


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
        ("grocery", False),
        ("", False),
    ],
)
def test_is_view_knows_the_seven_names_and_any_date(name, expected):
    assert is_view(name) is expected, "a view is one of the reserved names or a YYYY-MM-DD date"


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
    assert admits(view, date, MONDAY) is expected, (
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
        ("2026-10-20", "2026-10-20"),
        ("week", "2026-10-26"),
        ("decade", "2026-10-26"),
        ("", "2026-10-26"),
        ("grocery", "2026-10-26"),
    ],
)
def test_stamp_for_is_the_view_date_for_yesterday_and_date_views_and_today_otherwise(view, expected):
    assert stamp_for(view, MONDAY) == expected, "adding under yesterday/ or a date backdates, everything else is today"


def test_iso_formats_now_as_a_stamp_date():
    assert iso(MONDAY) == "2026-10-26", "iso should write dates the way stamps are written"


def test_freshness_orders_today_then_undated_then_older_newest_first():
    dates = ["2026-10-20", "", "2026-10-26", "2026-10-25", "", "2026-10-27"]

    ordered = sorted(dates, key=lambda date: freshness(date, "2026-10-26"))

    assert ordered == ["2026-10-27", "2026-10-26", "", "", "2026-10-25", "2026-10-20"], (
        "today (and anything hand-dated in the future) first, undated next, then older lines newest first"
    )


def test_freshness_is_stable_for_equal_dates():
    assert freshness("2026-10-20", "2026-10-26") == freshness("2026-10-20", "2026-10-26"), (
        "equal dates must compare equal so file order decides"
    )
