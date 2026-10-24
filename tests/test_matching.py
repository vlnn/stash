import pytest

from alfred_db.entries import parse_line
from alfred_db.matching import (
    EXACT,
    NO_MATCH,
    PREFIX,
    SUBSEQUENCE,
    SUBSTRING,
    haystack_of,
    make_token,
    search,
    token_tier,
)

LINES = [
    "ssh prod web | Prod web box | ssh deploy@10.0.1.5",
    "ssh staging web | Staging web box | ssh deploy@10.0.2.5",
    "k8s ctx staging | Switch kube context | kubectl config use-context staging",
    "wifi guest | Guest wifi password | hunter2",
    "git log pretty | Pretty git log | git log --oneline --graph",
]


def found_titles(query, lines=LINES, limit=10):
    haystacks = [haystack_of(line) for line in lines]
    return [parse_line(lines[index]).title for index in search(query, haystacks, limit)]


@pytest.mark.parametrize(
    "line, haystack",
    [
        ("ssh prod web | Prod web box | ssh deploy@10.0.1.5", " ssh prod web box "),
        ("Kube, CTX | Switch | kubectl", " kube ctx switch "),
        ("kw only | payload is not searchable", " kw only "),
        ("logs || tail -f app.log | grep ERROR", " logs "),
        ("wifi guest", " wifi guest "),
        ("# comment | title | payload", ""),
        ("   ", ""),
        (" | title without keywords | payload", ""),
    ],
)
def test_haystack_of_holds_keywords_and_title_words(line, haystack):
    assert haystack_of(line) == haystack, "haystack_of should hold lowercase unique keywords and title words"


@pytest.mark.parametrize(
    "token, line, tier",
    [
        ("prod", "ssh prod web", EXACT),
        ("pro", "ssh prod web", PREFIX),
        ("rod", "ssh prod web", SUBSTRING),
        ("prd", "ssh prod web", SUBSEQUENCE),
        ("stgng", "staging", SUBSEQUENCE),
        ("pdr", "ssh prod web", NO_MATCH),
        ("sw", "ssh web", NO_MATCH),
        ("s.h", "s.h", EXACT),
        ("s.h", "ssh", NO_MATCH),
        ("a]c", "a]bc", SUBSEQUENCE),
        ("box", "ssh | Prod web box | payload", EXACT),
        ("deploy", "ssh | Prod | ssh deploy@host", NO_MATCH),
    ],
)
def test_token_tier(token, line, tier):
    assert token_tier(make_token(token), haystack_of(line)) == tier, (
        f"token {token!r} against {line!r} should score tier {tier}"
    )


@pytest.mark.parametrize(
    "query, expected",
    [
        ("prod", ["Prod web box"]),
        ("web prod", ["Prod web box"]),
        ("prod web", ["Prod web box"]),
        ("PROD", ["Prod web box"]),
        ("ssh,prod", ["Prod web box"]),
        ("ssh", ["Prod web box", "Staging web box"]),
        ("ssh ssh", ["Prod web box", "Staging web box"]),
        ("stag", ["Staging web box", "Switch kube context"]),
        ("stg", ["Staging web box", "Switch kube context"]),
        ("ctx stg k8", ["Switch kube context"]),
        ("pass wifi", ["Guest wifi password"]),
        ("ssh prod staging", []),
        ("hunter2", []),
        ("zzz", []),
    ],
)
def test_search_matches_any_order_subset_and_word_parts(query, expected):
    assert found_titles(query) == expected, f"search {query!r} should return {expected}"


@pytest.mark.parametrize(
    "query, lines, expected_first",
    [
        ("go", ["golang | Golang | a", "go | Go docs | b"], "Go docs"),
        ("rod", ["prod | Prod | a", "rodeo | Rodeo | b"], "Rodeo"),
        ("web", ["wxexb | Scattered | a", "cobweb | Cobweb | b"], "Cobweb"),
        ("box", ["box crate container | Big | a", "box | Small | b"], "Small"),
        ("dev prod", ["dev pdrxoxd | Weak | a", "dev prod | Strong despite a longer title | b"], "Strong despite a longer title"),
    ],
)
def test_search_ranks_stronger_and_tighter_matches_first(query, lines, expected_first):
    assert found_titles(query, lines)[0] == expected_first, f"search {query!r} should rank {expected_first!r} first"


def test_search_keeps_file_order_for_equal_scores():
    assert found_titles("abc", ["abc one | First | a", "abc two | Second | b"]) == ["First", "Second"], (
        "search should keep file order when scores and tightness are equal"
    )


@pytest.mark.parametrize("query", ["", "   ", ",,"])
def test_search_with_empty_query_lists_entries_in_file_order(query):
    haystacks = [haystack_of(line) for line in ["# header", "a | A | 1", "", "b | B | 2", "c | C | 3"]]

    assert search(query, haystacks, limit=2) == [1, 3], (
        "search with an empty query should list the first entries in file order, skipping non-entries"
    )


@pytest.mark.parametrize("limit", [1, 2])
def test_search_respects_limit(limit):
    assert len(found_titles("web", limit=limit)) == limit, "search should return at most limit entries"


def test_search_never_returns_lines_without_entries():
    assert found_titles("title", [" | title | payload", "# title | title | x"]) == [], (
        "search should ignore comments and lines without keywords"
    )
