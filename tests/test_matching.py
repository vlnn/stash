import pytest

from stash.entries import parse_line
from stash.matching import EXACT, NO_MATCH, PREFIX, SUBSEQUENCE, SUBSTRING, search, tier, token_pattern

LINES = [
    "ssh prod web | ssh deploy@10.0.1.5",
    "ssh staging web | ssh deploy@10.0.2.5",
    "k8s ctx staging kube | kubectl config use-context staging",
    "wifi guest password | hunter2",
    "git log pretty | git log --oneline --graph",
    "http://127.0.0.1:4000",
]


def entries_from(lines):
    return [parse_line(line, number) for number, line in enumerate(lines, start=1)]


def found_labels(query, lines=LINES, limit=10):
    return [entry.label for entry in search(query, entries_from(lines), limit)]


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
        ("deploy", "ssh | ssh deploy@host", NO_MATCH),
        ("prod", "xprod prod", EXACT),
        ("4000", "http://127.0.0.1:4000", SUBSTRING),
    ],
)
def test_tier_is_the_strongest_way_a_word_matches(word, line, expected):
    assert tier(token_pattern(word), parse_line(line).haystack) == expected, (
        f"word {word!r} against {line!r} should score tier {expected}"
    )


@pytest.mark.parametrize(
    "query, expected",
    [
        ("prod", ["ssh prod web"]),
        ("web prod", ["ssh prod web"]),
        ("prod web", ["ssh prod web"]),
        ("PROD", ["ssh prod web"]),
        ("ssh,prod", ["ssh prod web"]),
        ("ssh", ["ssh prod web", "ssh staging web"]),
        ("ssh ssh", ["ssh prod web", "ssh staging web"]),
        ("stag", ["ssh staging web", "k8s ctx staging kube"]),
        ("stg", ["ssh staging web", "k8s ctx staging kube"]),
        ("ctx stg k8", ["k8s ctx staging kube"]),
        ("pass wifi", ["wifi guest password"]),
        ("127 4000", ["http://127.0.0.1:4000"]),
        ("ssh prod staging", []),
        ("hunter2", []),
        ("zzz", []),
    ],
)
def test_search_matches_any_order_subset_and_word_parts(query, expected):
    assert found_labels(query) == expected, f"search {query!r} should return {expected}"


@pytest.mark.parametrize(
    "query, lines, expected_first",
    [
        ("go", ["golang | a", "go | b"], "go"),
        ("rod", ["prod | a", "rodeo | b"], "rodeo"),
        ("web", ["wxexb | a", "cobweb | b"], "cobweb"),
        ("box", ["box crate container | a", "box | b"], "box"),
        ("dev prod", ["dev pdrxoxd | a", "dev prod extra words | b"], "dev prod extra words"),
    ],
)
def test_search_ranks_stronger_and_tighter_matches_first(query, lines, expected_first):
    assert found_labels(query, lines)[0] == expected_first, f"search {query!r} should rank {expected_first!r} first"


def test_search_keeps_file_order_for_equal_scores():
    assert found_labels("abc", ["abc one | a", "abc two | b"]) == ["abc one", "abc two"], (
        "search should keep file order when scores and tightness are equal"
    )


@pytest.mark.parametrize("query", ["", "   ", ",,"])
def test_search_with_empty_query_lists_entries_in_file_order(query):
    entries = entries_from(LINES)

    assert search(query, entries, limit=2) == entries[:2], "an empty query should list the first entries in file order"


@pytest.mark.parametrize("limit", [1, 2])
def test_search_respects_limit(limit):
    assert len(found_labels("web", limit=limit)) == limit, "search should return at most limit entries"
