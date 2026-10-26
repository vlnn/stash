from __future__ import annotations

import heapq
import re
from collections.abc import Sequence
from typing import NamedTuple

from .entries import Entry, haystack_of, split_words
from .views import NO_HORIZON, Horizon, freshness

EXACT, PREFIX, SUBSTRING, SUBSEQUENCE, NO_MATCH = 8, 6, 4, 2, 0
PAYLOAD = 1


class Token(NamedTuple):
    word: str
    pattern: re.Pattern[str]


def token_pattern(word: str) -> re.Pattern[str]:
    exact = re.escape(word)
    head, *tail = map(re.escape, word)
    # [^ c]* stops at the first c, so the subsequence stays inside one word and never backtracks
    subsequence = head + "".join(f"[^ {char}]*{char}" for char in tail)
    # alternatives from strongest to weakest, so the group that matched is the tier
    return re.compile(f"((?=.* {exact} ))|((?=.* {exact}))|((?=.*{exact}))|((?=.*{subsequence}))")


def token(word: str) -> Token:
    return Token(word, token_pattern(word))


def tier(pattern: re.Pattern[str], haystack: str) -> int:
    match = pattern.match(haystack)
    return EXACT - 2 * (match.lastindex - 1) if match else NO_MATCH


def word_score(word: Token, entry: Entry) -> int:
    return tier(word.pattern, entry.haystack) or (PAYLOAD if word.word in entry.needle else NO_MATCH)


def score(tokens: Sequence[Token], entry: Entry) -> int:
    total = 0
    for word in tokens:
        matched = word_score(word, entry)
        if not matched:
            return NO_MATCH
        total += matched
    return total


Hit = tuple[int, int, Entry]


def rank(hit: Hit, horizon: Horizon = NO_HORIZON) -> tuple[int, tuple[int, int], int, int]:
    total, position, entry = hit
    return -total, freshness(entry.date, horizon), len(entry.haystack), position


def by_freshness(entries: Sequence[Entry], horizon: Horizon) -> list[Entry]:
    return sorted(entries, key=lambda entry: freshness(entry.date, horizon))


def search(query: str, entries: Sequence[Entry], limit: int, horizon: Horizon = NO_HORIZON) -> list[Entry]:
    tokens = [token(word) for word in dict.fromkeys(split_words(query.lower()))]
    if not tokens:
        return list(entries[:limit])
    hits = [(score(tokens, entry), position, entry) for position, entry in enumerate(entries)]
    best = heapq.nsmallest(limit, [hit for hit in hits if hit[0]], key=lambda hit: rank(hit, horizon))
    return [entry for _, _, entry in best]


def stash_entry(name: str, position: int) -> Entry:
    return Entry(name, name, haystack_of((name,)), position)


def search_stashes(query: str, names: Sequence[str]) -> list[str]:
    candidates = [stash_entry(name, position) for position, name in enumerate(names)]
    return [entry.label for entry in search(query, candidates, len(candidates))]
