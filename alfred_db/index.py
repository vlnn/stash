from __future__ import annotations

import marshal
import os
import zlib
from contextlib import suppress
from typing import NamedTuple, Optional

from .matching import haystack_of
from .store import ENCODING, read_bytes, write_atomically

LINE_SEPARATOR = "\n"


class Index(NamedTuple):
    lines: list[str]
    haystacks: list[str]

    @property
    def has_entries(self) -> bool:
        return any(self.haystacks)


def load_index(db_path: str, cache_dir: str) -> Index:
    content = read_bytes(db_path)
    lines = content.decode(ENCODING).split(LINE_SEPARATOR)
    cache_path = cache_path_for(cache_dir, db_path)
    fingerprint = zlib.crc32(content)
    haystacks = cached_haystacks(cache_path, fingerprint, len(lines))
    if haystacks is None:
        haystacks = [haystack_of(line) for line in lines]
        save_haystacks(cache_path, fingerprint, haystacks)
    return Index(lines, haystacks)


def cache_path_for(cache_dir: str, db_path: str) -> str:
    return os.path.join(cache_dir, f"index-{zlib.crc32(db_path.encode()):08x}.marshal")


def cached_haystacks(cache_path: str, fingerprint: int, line_count: int) -> Optional[list[str]]:
    try:
        with open(cache_path, "rb") as file:
            cached_fingerprint, joined = marshal.loads(file.read())
        haystacks = joined.split(LINE_SEPARATOR)
    except (OSError, EOFError, ValueError, TypeError, AttributeError):
        return None
    is_fresh = cached_fingerprint == fingerprint and len(haystacks) == line_count
    return haystacks if is_fresh else None


def save_haystacks(cache_path: str, fingerprint: int, haystacks: list[str]) -> None:
    with suppress(OSError):
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        write_atomically(cache_path, marshal.dumps((fingerprint, LINE_SEPARATOR.join(haystacks))))
