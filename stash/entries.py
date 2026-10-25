from __future__ import annotations

import re
from typing import NamedTuple

SEPARATOR = re.compile(r"[|\\]")
COMMENT_PREFIX = "#"

Keywords = tuple[str, ...]


class Entry(NamedTuple):
    label: str
    payload: str
    haystack: str
    line_number: int = 0
    raw: str = ""


def parse_line(line: str, line_number: int = 0) -> Entry | None:
    text = line.strip()
    if not text or text.startswith(COMMENT_PREFIX):
        return None
    label, payload = split_record(text)
    keywords = split_words(SEPARATOR.sub(" ", label))
    if not keywords:
        return None
    return Entry(label, payload, haystack_of(keywords), line_number, text)


def split_record(text: str) -> tuple[str, str]:
    head, *tail = SEPARATOR.split(text, 1)
    if not tail:
        return text, text
    label, payload = head.strip(), tail[0].strip()
    return label or payload, payload or label


def has_separator(text: str) -> bool:
    return SEPARATOR.search(text) is not None


def haystack_of(keywords: Keywords) -> str:
    words = dict.fromkeys(" ".join(keywords).lower().split())
    return f" {' '.join(words)} "


def split_words(text: str) -> Keywords:
    return tuple(text.replace(",", " ").split())
