from __future__ import annotations

import re
from typing import NamedTuple

SEPARATOR = re.compile(r"\||(?:(?<=\s)|^)\\(?=\s|$)")
STASH_NAME = re.compile(r"[\w-]+")
STASH_PREFIX = re.compile(rf"^({STASH_NAME.pattern})/\s*")
DATE = r"\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])"
STAMP = re.compile(rf"^({DATE}):\s*")
COMMENT_PREFIX = "#"

Keywords = tuple[str, ...]


class Entry(NamedTuple):
    label: str
    payload: str
    haystack: str
    line_number: int = 0
    raw: str = ""
    stash: str = ""
    needle: str = ""
    date: str = ""


def parse_line(line: str, line_number: int = 0, stash: str = "") -> Entry | None:
    text = line.strip()
    if not text or text.startswith(COMMENT_PREFIX):
        return None
    date, body = split_stamp(text)
    label, payload = split_record(body)
    keywords = split_words(SEPARATOR.sub(" ", label))
    if not keywords:
        return None
    return Entry(label, payload, haystack_of(keywords), line_number, text, stash, payload.lower(), date)


def split_stamp(text: str) -> tuple[str, str]:
    found = STAMP.match(text)
    if found is None:
        return "", text
    return found.group(1), text[found.end() :]


def stamped(date: str, text: str) -> str:
    return f"{date}: {text}"


def split_record(text: str) -> tuple[str, str]:
    head, *tail = SEPARATOR.split(text, 1)
    if not tail:
        return text, text
    label, payload = head.strip(), tail[0].strip()
    return label or payload, payload or label


def split_stash(text: str) -> tuple[str, str]:
    stripped = text.lstrip()
    found = STASH_PREFIX.match(stripped)
    if found is None:
        return "", stripped
    return found.group(1), stripped[found.end() :]


def in_stash(stash: str, text: str) -> str:
    return f"{stash}/ {text}" if stash else text


def is_stash_name(name: str) -> bool:
    return STASH_NAME.fullmatch(name) is not None


def has_separator(text: str) -> bool:
    return SEPARATOR.search(text) is not None


def haystack_of(keywords: Keywords) -> str:
    words = dict.fromkeys(" ".join(keywords).lower().split())
    return f" {' '.join(words)} "


def split_words(text: str) -> Keywords:
    return tuple(text.replace(",", " ").split())
