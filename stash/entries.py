from __future__ import annotations

from typing import NamedTuple, Optional

FIELD_SEPARATOR = "|"
COMMENT_PREFIX = "#"

Keywords = tuple[str, ...]


class Entry(NamedTuple):
    keywords: Keywords
    title: str
    payload: str
    haystack: str
    line_number: int = 0
    raw: str = ""


def parse_line(line: str, line_number: int = 0) -> Optional[Entry]:
    text = line.strip()
    if not text or text.startswith(COMMENT_PREFIX):
        return None
    keywords_field, *rest = split_fields(text)
    keywords = split_words(keywords_field)
    if not keywords:
        return None
    title, payload = title_and_payload(rest, fallback=" ".join(keywords))
    return Entry(keywords, title, payload, haystack_of(keywords, title), line_number, text)


def split_fields(text: str) -> list[str]:
    return [field.strip() for field in text.split(FIELD_SEPARATOR, 2)]


def title_and_payload(rest: list[str], fallback: str) -> tuple[str, str]:
    title, payload = [""] * (2 - len(rest)) + rest
    return title or fallback, payload or fallback


def haystack_of(keywords: Keywords, title: str) -> str:
    words = dict.fromkeys(" ".join(keywords + split_words(title)).lower().split())
    return f" {' '.join(words)} "


def split_words(text: str) -> Keywords:
    return tuple(text.replace(",", " ").split())
