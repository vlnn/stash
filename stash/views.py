from __future__ import annotations

import re
import time

from .entries import DATE

VIEWS = ("today", "yesterday", "week", "month", "quarter", "year", "decade")
TODAY, YESTERDAY, WEEK, MONTH, QUARTER, YEAR, DECADE = VIEWS
DATE_NAME = re.compile(rf"^{DATE}$")
DATE_FORMAT = "%Y-%m-%d"
DAY = 86400
NOON = (12, 0, 0, 0, 0, -1)


def is_view(name: str) -> bool:
    return name in VIEWS or DATE_NAME.match(name) is not None


def iso(now: time.struct_time) -> str:
    return time.strftime(DATE_FORMAT, now)


def day(year: int, month: int, mday: int) -> str:
    # mktime normalises out-of-range fields, so month 13 is next January and mday 0 is the last day of the month before
    return iso(time.localtime(time.mktime((year, month, mday, *NOON))))


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


def admits(view: str, date: str, now: time.struct_time) -> bool:
    if not date:
        return True
    first, last = window(view, now)
    return first <= date <= last


def stamp_for(view: str, now: time.struct_time) -> str:
    if view == YESTERDAY or DATE_NAME.match(view):
        return window(view, now)[0]
    return iso(now)


def days_ago(date: str, now: time.struct_time) -> int:
    then = time.mktime((*map(int, date.split("-")), *NOON))
    return round((time.mktime((now.tm_year, now.tm_mon, now.tm_mday, *NOON)) - then) / DAY)


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


def freshness(date: str, today: str) -> tuple[int, int]:
    if not date:
        return 1, 0
    return (0 if date >= today else 2), -int(date.replace("-", ""))
