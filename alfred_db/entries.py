from __future__ import annotations

from typing import NamedTuple, Optional

FIELD_SEPARATOR = "|"
COMMENT_PREFIX = "#"

Keywords = tuple[str, ...]


class Entry(NamedTuple):
    keywords: Keywords
    title: str
    payload: str
    line_number: int = 0
    raw: str = ""


def parse_line(line: str, line_number: int = 0) -> Optional[Entry]:
    fields = entry_fields(line)
    if fields is None:
        return None
    keywords, rest = fields
    title, payload = title_and_payload(rest, fallback=" ".join(keywords))
    return Entry(keywords, title, payload, line_number, line.strip())


def entry_fields(line: str) -> Optional[tuple[Keywords, list[str]]]:
    text = line.strip()
    if is_skippable(text):
        return None
    keywords_field, *rest = split_fields(text)
    keywords = split_words(keywords_field)
    return (keywords, rest) if keywords else None


def is_skippable(text: str) -> bool:
    return not text or text.startswith(COMMENT_PREFIX)


def split_fields(text: str) -> list[str]:
    return [field.strip() for field in text.split(FIELD_SEPARATOR, 2)]


def title_and_payload(rest: list[str], fallback: str) -> tuple[str, str]:
    title, payload = [""] * (2 - len(rest)) + rest
    return title or fallback, payload or fallback


def split_words(text: str) -> Keywords:
    return tuple(text.replace(",", " ").split())
