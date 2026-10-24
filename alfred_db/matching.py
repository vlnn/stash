from __future__ import annotations

import heapq
import re
from itertools import islice
from typing import Iterator, NamedTuple, Sequence

from .entries import entry_fields, split_words

EXACT, PREFIX, SUBSTRING, SUBSEQUENCE, NO_MATCH = 4, 3, 2, 1, 0


class Token(NamedTuple):
    text: str
    as_word: str
    as_word_start: str
    as_subsequence: re.Pattern[str]


def make_token(text: str) -> Token:
    return Token(text, f" {text} ", f" {text}", subsequence_pattern(text))


def subsequence_pattern(text: str) -> re.Pattern[str]:
    head, *tail = map(re.escape, text)
    # [^ c]* stops at the first c, so the match stays inside one word and never backtracks
    return re.compile(head + "".join(f"[^ {char}]*{char}" for char in tail))


def haystack_of(line: str) -> str:
    fields = entry_fields(line)
    if fields is None:
        return ""
    keywords, rest = fields
    title_words = split_words(rest[0]) if len(rest) == 2 else ()
    words = dict.fromkeys(" ".join(keywords + title_words).lower().split())
    return f" {' '.join(words)} "


def token_tier(token: Token, haystack: str) -> int:
    if not token.as_subsequence.search(haystack):
        return NO_MATCH
    return tiers(token, [haystack])[0]


def tiers(token: Token, haystacks: Sequence[str]) -> list[int]:
    text, word_start, word = token.text, token.as_word_start, token.as_word
    # every tier implies the weaker ones, so the tier is the number of checks that pass
    return [SUBSEQUENCE + (text in haystack) + (word_start in haystack) + (word in haystack) for haystack in haystacks]


def query_tokens(query: str) -> list[Token]:
    words = dict.fromkeys(split_words(query.lower()))
    return [make_token(word) for word in sorted(words, key=len, reverse=True)]


def search(query: str, haystacks: Sequence[str], limit: int) -> list[int]:
    tokens = query_tokens(query)
    if not tokens:
        return list(islice(entry_positions(haystacks), limit))
    return [position for *_, position in heapq.nsmallest(limit, ranked(tokens, haystacks))]


def entry_positions(haystacks: Sequence[str]) -> Iterator[int]:
    return (position for position, haystack in enumerate(haystacks) if haystack)


def matching_positions(tokens: Sequence[Token], haystacks: Sequence[str]) -> list[int]:
    positions: Sequence[int] = range(len(haystacks))
    for token in tokens:
        matches = token.as_subsequence.search
        positions = [position for position in positions if matches(haystacks[position])]
    return list(positions)


def total_scores(tokens: Sequence[Token], haystacks: Sequence[str]) -> list[int]:
    scores = [0] * len(haystacks)
    for token in tokens:
        scores = [score + tier for score, tier in zip(scores, tiers(token, haystacks))]
    return scores


def ranked(tokens: Sequence[Token], haystacks: Sequence[str]) -> list[tuple[int, int, int]]:
    positions = matching_positions(tokens, haystacks)
    found = [haystacks[position] for position in positions]
    scores = total_scores(tokens, found)
    return [(-score, len(haystack), position) for score, haystack, position in zip(scores, found, positions)]
