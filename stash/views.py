from __future__ import annotations

import re
import time

from .entries import DATE

VIEWS = ("today", "yesterday", "week", "month", "quarter", "year", "decade")
TODAY, YESTERDAY, WEEK, MONTH, QUARTER, YEAR, DECADE = VIEWS
DATE_NAME = re.compile(rf"^{DATE}$")
DATE_FORMAT = "%Y-%m-%d"
EPOCH_SHIFT = 719468


def is_view(name: str) -> bool:
    return name in VIEWS or DATE_NAME.match(name) is not None


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


def window(view: str, now: time.struct_time) -> tuple[str, str]:
    year, month, mday, weekday = now.tm_year, now.tm_mon, now.tm_mday, now.tm_wday
    if view == TODAY:
        return iso(now), iso(now)
    if view == YESTERDAY:
        return day(year, month, mday - 1), day(year, month, mday - 1)
    if view == WEEK:
        return day(year, month, mday - weekday), day(year, month, mday - weekday + 6)
    if view == MONTH:
        return day(year, month, 1), day(year, month + 1, 0)
    if view == QUARTER:
        first = (month - 1) // 3 * 3 + 1
        return day(year, first, 1), day(year, first + 3, 0)
    if view == YEAR:
        return day(year, 1, 1), day(year, 12, 31)
    if view == DECADE:
        first = year - year % 10
        return day(first, 1, 1), day(first + 9, 12, 31)
    return view, view


def admits(span: tuple[str, str], date: str) -> bool:
    first, last = span
    return not date or first <= date <= last


def stamp_for(view: str, now: time.struct_time) -> str:
    if view == YESTERDAY or DATE_NAME.match(view):
        return window(view, now)[0]
    return iso(now)


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


def freshness(date: str, floor: str) -> tuple[int, int]:
    if not date:
        return 1, 0
    return (0 if date >= floor else 2), -int(date.replace("-", ""))
