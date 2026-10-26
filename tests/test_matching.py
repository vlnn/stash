import pytest

from stash.entries import parse_line
from stash.matching import (
    EXACT,
    NO_MATCH,
    PAYLOAD,
    PREFIX,
    SUBSEQUENCE,
    SUBSTRING,
    by_freshness,
    score,
    search,
    search_stashes,
    tier,
    token,
    token_pattern,
)

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


def found_labels(query, lines=LINES, limit=10, today=""):
    return [entry.label for entry in search(query, entries_from(lines), limit, today)]


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
        ("hunter2", ["wifi guest password"]),
        ("deploy", ["ssh prod web", "ssh staging web"]),
        ("use-context", ["k8s ctx staging kube"]),
        ("k8 config", ["k8s ctx staging kube"]),
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


@pytest.mark.parametrize(
    "query, lines, expected",
    [
        ("prod", ["proud | x", "k | ssh prod"], ["proud", "k"]),
        ("prd", ["k | ssh prd", "prod | x"], ["prod", "k"]),
        ("log", ["git log | git log", "k8s | kubectl logs", "pods | kubectl get pods"], ["git log", "k8s"]),
        ("{{date}}", ["stamp | note {{date}}", "plain | nothing"], ["stamp"]),
        ("DEPLOY", ["ssh | ssh deploy@h"], ["ssh"]),
    ],
)
def test_search_ranks_any_label_hit_above_a_payload_hit(query, lines, expected):
    assert found_labels(query, lines) == expected, (
        "a word found only in the payload counts, but below the weakest label match"
    )


@pytest.mark.parametrize(
    "query, line, expected",
    [
        ("ssh", "ssh prod | ssh deploy@h", EXACT),
        ("deploy", "ssh prod | ssh deploy@h", PAYLOAD),
        ("eploy@", "ssh prod | ssh deploy@h", PAYLOAD),
        ("dply", "ssh prod | ssh deploy@h", NO_MATCH),
        ("prod deploy", "ssh prod | ssh deploy@h", EXACT + PAYLOAD),
        ("4000", "http://127.0.0.1:4000", SUBSTRING),
    ],
)
def test_score_falls_back_to_a_plain_substring_of_the_payload(query, line, expected):
    assert score([token(word) for word in query.split()], parse_line(line)) == expected, (
        "each word takes its label tier, or the payload tier when only the payload contains it as written"
    )


def test_search_keeps_file_order_for_equal_scores():
    assert found_labels("abc", ["abc one | a", "abc two | b"]) == ["abc one", "abc two"], (
        "search should keep file order when scores and tightness are equal"
    )


DATED = [
    "2026-10-20: zoo visit | last week's plan",
    "visit grandma | evergreen",
    "2026-10-26: visit dentist | today's plan",
    "2026-10-25: visit bank | yesterday's plan",
]


def test_search_breaks_equal_scores_by_today_then_undated_then_older_newest_first():
    assert found_labels("visit", DATED, today="2026-10-26") == [
        "visit dentist",
        "visit grandma",
        "visit bank",
        "zoo visit",
    ], "at an equal score, today's lines come first, evergreens next, then older lines newest first"


def test_search_lets_a_stronger_match_beat_a_fresher_one():
    lines = ["2026-10-26: visits | today", "visit | evergreen"]

    assert found_labels("visit", lines, today="2026-10-26") == ["visit", "visits"], (
        "age only breaks ties; a whole-word match on an old line still beats a prefix match on today's"
    )


def test_search_tightness_still_decides_among_lines_of_one_age():
    lines = ["2026-10-20: box crate container | a", "2026-10-20: box | b"]

    assert found_labels("box", lines, today="2026-10-26") == ["box", "box crate container"], (
        "same date, same score: the tighter label wins as before"
    )


def test_search_without_today_treats_every_stamp_as_fresh():
    assert found_labels("visit", DATED) == ["visit dentist", "visit bank", "zoo visit", "visit grandma"], (
        "with no reference day, dated lines rank newest first and undated ones last"
    )


def test_by_freshness_orders_entries_for_browsing_a_view():
    assert [entry.label for entry in by_freshness(entries_from(DATED), "2026-10-26")] == [
        "visit dentist",
        "visit grandma",
        "visit bank",
        "zoo visit",
    ], "browsing a view lists today's lines, evergreens, then older lines newest first, file order within a day"


def test_search_ranks_by_the_order_given_when_everything_else_is_equal():
    entries = list(reversed(entries_from(["abc one | a", "abc two | b"])))

    assert [entry.label for entry in search("abc", entries, 10)] == ["abc two", "abc one"], (
        "the last tiebreak is the order the entries were given in, which is file order for one file"
    )


@pytest.mark.parametrize("query", ["", "   ", ",,"])
def test_search_with_empty_query_lists_entries_in_file_order(query):
    entries = entries_from(LINES)

    assert search(query, entries, limit=2) == entries[:2], "an empty query should list the first entries in file order"


@pytest.mark.parametrize("limit", [1, 2])
def test_search_respects_limit(limit):
    assert len(found_labels("web", limit=limit)) == limit, "search should return at most limit entries"


STASHES = ["aws", "checklists", "zsh", "chk"]


@pytest.mark.parametrize(
    "query, expected",
    [
        ("", ["aws", "checklists", "zsh", "chk"]),
        ("chk", ["chk", "checklists"]),
        ("ck", ["checklists", "chk"]),
        ("zsh aws", []),
        ("nothing", []),
    ],
)
def test_search_stashs_ranks_names_like_words(query, expected):
    assert search_stashes(query, STASHES) == expected, "stash names should match and rank the way entry words do"
