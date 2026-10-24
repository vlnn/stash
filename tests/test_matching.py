import pytest

from stash.entries import parse_line
from stash.matching import EXACT, NO_MATCH, PREFIX, SUBSEQUENCE, SUBSTRING, search, tier, token_pattern

LINES = [
    "ssh prod web | Prod web box | ssh deploy@10.0.1.5",
    "ssh staging web | Staging web box | ssh deploy@10.0.2.5",
    "k8s ctx staging | Switch kube context | kubectl config use-context staging",
    "wifi guest | Guest wifi password | hunter2",
    "git log pretty | Pretty git log | git log --oneline --graph",
]


def entries_from(lines):
    return [parse_line(line, number) for number, line in enumerate(lines, start=1)]


def found_titles(query, lines=LINES, limit=10):
    return [entry.title for entry in search(query, entries_from(lines), limit)]


@pytest.mark.parametrize(
    "word, line, expected",
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
        ("prod", "xprod prod", EXACT),
    ],
)
def test_tier_is_the_strongest_way_a_word_matches(word, line, expected):
    assert tier(token_pattern(word), parse_line(line).haystack) == expected, (
        f"word {word!r} against {line!r} should score tier {expected}"
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
    entries = entries_from(LINES)

    assert search(query, entries, limit=2) == entries[:2], "an empty query should list the first entries in file order"


@pytest.mark.parametrize("limit", [1, 2])
def test_search_respects_limit(limit):
    assert len(found_titles("web", limit=limit)) == limit, "search should return at most limit entries"
