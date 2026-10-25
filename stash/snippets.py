from __future__ import annotations

import re
import time
from collections.abc import Callable, Mapping
from typing import NamedTuple

PLACEHOLDER = re.compile(r"\{\{([A-Za-z_][\w-]*)(?:=([^{}]*))?\}\}")
DATE, TIME, CLIPBOARD = "date", "time", "clipboard"
RESERVED = (DATE, TIME, CLIPBOARD)
DATE_FORMAT, TIME_FORMAT = "%Y-%m-%d", "%H:%M"

Values = Mapping[str, str]
Clipboard = Callable[[], str]


class Placeholder(NamedTuple):
    name: str
    default: str | None = None


def placeholders(text: str) -> list[Placeholder]:
    found: dict[str, Placeholder] = {}
    for match in PLACEHOLDER.finditer(text):
        name = match.group(1)
        if name not in RESERVED:
            found.setdefault(name, Placeholder(name, match.group(2)))
    return list(found.values())


def has_placeholders(text: str) -> bool:
    return bool(placeholders(text))


def pending(text: str, values: Values) -> list[Placeholder]:
    return [placeholder for placeholder in placeholders(text) if placeholder.name not in values]


def fill(text: str, values: Values) -> str:
    return PLACEHOLDER.sub(lambda found: values.get(found.group(1), found.group(0)), text)


def reserved_values(now: time.struct_time, clipboard: Clipboard, texts: tuple[str, ...] = ()) -> dict[str, str]:
    values = {DATE: time.strftime(DATE_FORMAT, now), TIME: time.strftime(TIME_FORMAT, now)}
    if any(mentions(text, CLIPBOARD) for text in texts):
        values[CLIPBOARD] = clipboard()
    return values


def mentions(text: str, name: str) -> bool:
    return any(found == name for found, _ in PLACEHOLDER.findall(text))


def assignments(pairs: list[str]) -> dict[str, str]:
    return dict(pair.split("=", 1) for pair in pairs if "=" in pair)
