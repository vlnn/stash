from __future__ import annotations

import heapq
import re
from collections.abc import Sequence

from .entries import Entry, haystack_of, split_words

EXACT, PREFIX, SUBSTRING, SUBSEQUENCE, NO_MATCH = 4, 3, 2, 1, 0


def token_pattern(word: str) -> re.Pattern[str]:
    exact = re.escape(word)
    head, *tail = map(re.escape, word)
    # [^ c]* stops at the first c, so the subsequence stays inside one word and never backtracks
    subsequence = head + "".join(f"[^ {char}]*{char}" for char in tail)
    # alternatives from strongest to weakest, so the group that matched is the tier
    return re.compile(f"((?=.* {exact} ))|((?=.* {exact}))|((?=.*{exact}))|((?=.*{subsequence}))")


def tier(pattern: re.Pattern[str], haystack: str) -> int:
    match = pattern.match(haystack)
    return EXACT + 1 - match.lastindex if match else NO_MATCH


def score(patterns: Sequence[re.Pattern[str]], entry: Entry) -> int:
    total = 0
    for pattern in patterns:
        matched = tier(pattern, entry.haystack)
        if not matched:
            return NO_MATCH
        total += matched
    return total


def rank(hit: tuple[int, Entry]) -> tuple[int, int, int]:
    total, entry = hit
    return -total, len(entry.haystack), entry.line_number


def search(query: str, entries: Sequence[Entry], limit: int) -> list[Entry]:
    patterns = [token_pattern(word) for word in dict.fromkeys(split_words(query.lower()))]
    if not patterns:
        return list(entries[:limit])
    hits = [(score(patterns, entry), entry) for entry in entries]
    return [entry for _, entry in heapq.nsmallest(limit, [hit for hit in hits if hit[0]], key=rank)]


def stash_entry(name: str, position: int) -> Entry:
    return Entry(name, name, haystack_of((name,)), position)


def search_stashes(query: str, names: Sequence[str]) -> list[str]:
    candidates = [stash_entry(name, position) for position, name in enumerate(names)]
    return [entry.label for entry in search(query, candidates, len(candidates))]
