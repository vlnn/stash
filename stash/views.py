from __future__ import annotations

import re
import time
from typing import NamedTuple

from .entries import DATE

DAY, WEEK, MONTH, QUARTER, YEAR, DECADE = "day", "week", "month", "quarter", "year", "decade"
TODAY, NEXT_WEEK = "today", "next-week"
PERIODS = {
    TODAY: (DAY, 0),
    "yesterday": (DAY, -1),
    "tomorrow": (DAY, 1),
    WEEK: (WEEK, 0),
    "last-week": (WEEK, -1),
    NEXT_WEEK: (WEEK, 1),
    MONTH: (MONTH, 0),
    "last-month": (MONTH, -1),
    "next-month": (MONTH, 1),
    QUARTER: (QUARTER, 0),
    "last-quarter": (QUARTER, -1),
    "next-quarter": (QUARTER, 1),
    YEAR: (YEAR, 0),
    "last-year": (YEAR, -1),
    "next-year": (YEAR, 1),
    DECADE: (DECADE, 0),
}
VIEWS = tuple(PERIODS)
NAME_PREFIX, NAMED_LIMIT = 2, 2
DATE_NAME = re.compile(rf"^{DATE}$")
DATE_FORMAT = "%Y-%m-%d"
EPOCH_SHIFT = 719468

Window = tuple[str, str]


class Horizon(NamedTuple):
    today: str
    floor: str
    last: str


NO_HORIZON = Horizon("", "", "")


def named(typed: str) -> list[str]:
    if len(typed) < NAME_PREFIX:
        return []
    return [view for view in VIEWS if view.startswith(typed)][:NAMED_LIMIT]


def is_view(name: str) -> bool:
    return name in PERIODS or DATE_NAME.match(name) is not None


def iso(now: time.struct_time) -> str:
    return time.strftime(DATE_FORMAT, now)


# Proleptic Gregorian day counts (Hinnant's days_from_civil), so no clock, time zone or DST is involved
def ordinal(year: int, month: int, mday: int) -> int:
    year -= month <= 2
    era = year // 400
    year_of_era = year - era * 400
    day_of_year = (153 * (month - 3 if month > 2 else month + 9) + 2) // 5 + mday - 1
    day_of_era = year_of_era * 365 + year_of_era // 4 - year_of_era // 100 + day_of_year
    return era * 146097 + day_of_era - EPOCH_SHIFT


def civil(days: int) -> tuple[int, int, int]:
    days += EPOCH_SHIFT
    era = days // 146097
    day_of_era = days - era * 146097
    year_of_era = (day_of_era - day_of_era // 1460 + day_of_era // 36524 - day_of_era // 146096) // 365
    day_of_year = day_of_era - (365 * year_of_era + year_of_era // 4 - year_of_era // 100)
    shifted_month = (5 * day_of_year + 2) // 153
    mday = day_of_year - (153 * shifted_month + 2) // 5 + 1
    month = shifted_month + 3 if shifted_month < 10 else shifted_month - 9
    return year_of_era + era * 400 + (month <= 2), month, mday


def day(year: int, month: int, mday: int) -> str:
    # month 13 is next January and mday 0 is the last day of the month before, as with mktime
    year, month = year + (month - 1) // 12, (month - 1) % 12 + 1
    year, month, mday = civil(ordinal(year, month, 1) + mday - 1)
    return f"{year:04d}-{month:02d}-{mday:02d}"


def window(view: str, now: time.struct_time) -> Window:
    if view not in PERIODS:
        return view, view
    period, offset = PERIODS[view]
    year, month, mday, weekday = now.tm_year, now.tm_mon, now.tm_mday, now.tm_wday
    if period == DAY:
        return day(year, month, mday + offset), day(year, month, mday + offset)
    if period == WEEK:
        monday = mday - weekday + 7 * offset
        return day(year, month, monday), day(year, month, monday + 6)
    if period == MONTH:
        return day(year, month + offset, 1), day(year, month + offset + 1, 0)
    if period == QUARTER:
        first = (month - 1) // 3 * 3 + 1 + 3 * offset
        return day(year, first, 1), day(year, first + 3, 0)
    if period == YEAR:
        return day(year + offset, 1, 1), day(year + offset, 12, 31)
    first = year - year % 10
    return day(first, 1, 1), day(first + 9, 12, 31)


def admits(span: Window, date: str, today: str) -> bool:
    first, last = span
    if not date:
        return holds_undated(span, today)
    return first <= date <= last


def holds_undated(span: Window, today: str) -> bool:
    _, last = span
    return last >= today


def is_current(view: str) -> bool:
    return view in PERIODS and PERIODS[view][1] == 0


def stamp_for(view: str, now: time.struct_time) -> str:
    if is_view(view) and not is_current(view):
        return window(view, now)[0]
    return iso(now)


def horizon_at(now: time.struct_time, span: Window | None = None) -> Horizon:
    today = iso(now)
    first, last = span or (today, window(NEXT_WEEK, now)[1])
    return Horizon(today, first, last)


def days_ago(date: str, now: time.struct_time) -> int:
    return ordinal(now.tm_year, now.tm_mon, now.tm_mday) - ordinal(*map(int, date.split("-")))


def age(date: str, now: time.struct_time) -> str:
    days = days_ago(date, now)
    if days < 0:
        return date
    if days == 0:
        return TODAY
    if days < 7:
        return f"{days}d"
    if days < 30:
        return f"{days // 7}w"
    if days < 365:
        return f"{days // 30}mo"
    return f"{days // 365}y"


def freshness(date: str, horizon: Horizon) -> tuple[int, int]:
    today, floor, last = horizon
    if not today:
        return 0, 0
    if not date:
        return 3, 0
    number = int(date.replace("-", ""))
    if date == today:
        return 0, 0
    if today < date <= last:
        return 1, number
    if floor <= date < today:
        return 2, -number
    if date > last:
        return 4, number
    return 5, -number
