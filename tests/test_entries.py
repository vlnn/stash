import pytest

from stash.entries import (
    Entry,
    in_stash,
    is_stash_name,
    parse_line,
    parse_text,
    split_stamp,
    split_stash,
    split_words,
    stamped,
)


@pytest.mark.parametrize(
    "line, label, payload",
    [
        ("ssh prod web | ssh deploy@10.0.1.5", "ssh prod web", "ssh deploy@10.0.1.5"),
        ("ssh prod web \\ ssh deploy@10.0.1.5", "ssh prod web", "ssh deploy@10.0.1.5"),
        ("logs api | tail -f app.log | grep ERROR", "logs api", "tail -f app.log | grep ERROR"),
        ("find py | find . -name '*.py' -exec rm {} \\;", "find py", "find . -name '*.py' -exec rm {} \\;"),
        ("newline \\ printf 'a\\nb' | wc -l", "newline", "printf 'a\\nb' | wc -l"),
        ("wifi guest", "wifi guest", "wifi guest"),
        ("http://127.0.0.1:4000", "http://127.0.0.1:4000", "http://127.0.0.1:4000"),
        ("| echo a | wc", "echo a | wc", "echo a | wc"),
        ("  k8s   ctx  |  kubectl ctx  ", "k8s   ctx", "kubectl ctx"),
        ("k8s,ctx, staging | kubectl ctx staging", "k8s,ctx, staging", "kubectl ctx staging"),
        ("note |", "note", "note"),
        ("printf 'a\\nb'", "printf 'a\\nb'", "printf 'a\\nb'"),
        ("C:\\Users\\me\\Documents", "C:\\Users\\me\\Documents", "C:\\Users\\me\\Documents"),
        ("regex \\d+ digits", "regex \\d+ digits", "regex \\d+ digits"),
        ("latex \\ alpha", "latex", "alpha"),
        ("tab\t\\\tsep", "tab", "sep"),
        ("win path \\ C:\\Users\\me", "win path", "C:\\Users\\me"),
    ],
)
def test_parse_line_splits_at_the_first_separator_only(line, label, payload):
    entry = parse_line(line)

    assert entry.label == label, "the text before the first | or \\ is what Alfred shows and what is searched"
    assert entry.payload == payload, "everything after the first separator is the payload, verbatim"


@pytest.mark.parametrize(
    "line, keywords",
    [
        ("ssh prod web | x", ("ssh", "prod", "web")),
        ("k8s,ctx, staging | x", ("k8s", "ctx", "staging")),
        ("wifi guest", ("wifi", "guest")),
        ("| echo a | wc", ("echo", "a", "wc")),
    ],
)
def test_parse_line_keywords_come_from_the_label(line, keywords):
    assert tuple(parse_line(line).haystack.split()) == keywords, (
        "search words are the label split on spaces and commas, separators excluded"
    )


@pytest.mark.parametrize(
    "line",
    ["", "   ", "\n", "# a comment", "   # indented comment", "|", " | ", "\\", ", , |"],
)
def test_parse_line_skips_lines_without_entry(line):
    assert parse_line(line) is None, "parse_line should ignore blank lines, comments and lines with no words"


def test_parse_line_remembers_position_and_source():
    entry = parse_line("  wifi guest | hunter2\n", line_number=7)

    assert entry.line_number == 7, "parse_line should keep the line number for editing"
    assert entry.raw == "wifi guest | hunter2", "parse_line should keep the stripped source line for deletion"


@pytest.mark.parametrize(
    "line, haystack",
    [
        ("ssh prod web | ssh deploy@10.0.1.5", " ssh prod web "),
        ("Kube, CTX | kubectl", " kube ctx "),
        ("ssh prod ssh | x", " ssh prod "),
        ("wifi guest", " wifi guest "),
        ("http://127.0.0.1:4000", " http://127.0.0.1:4000 "),
        ("| echo a | wc", " echo a wc "),
    ],
)
def test_haystack_holds_lowercase_unique_words(line, haystack):
    assert parse_line(line).haystack == haystack, "haystack should hold the searchable words, space-delimited"


@pytest.mark.parametrize(
    "line, needle",
    [
        ("ssh prod | ssh Deploy@10.0.1.5", "ssh deploy@10.0.1.5"),
        ("wifi guest", "wifi guest"),
        ("stamp | note {{date}}", "note {{date}}"),
    ],
)
def test_parse_line_keeps_a_lowercase_payload_for_searching(line, needle):
    assert parse_line(line).needle == needle, "the payload as written, lowercased, is what a payload search looks in"


def test_entry_is_hashable_value():
    first = parse_line("a | b")
    second = parse_line("a | b")

    assert first == second, "entries parsed from the same line should be equal"
    assert isinstance(first, Entry), "parse_line should return an Entry"


@pytest.mark.parametrize(
    "text, words",
    [
        ("a b c", ("a", "b", "c")),
        ("a,b , c", ("a", "b", "c")),
        ("  spaced\tout  ", ("spaced", "out")),
        ("", ()),
    ],
)
def test_split_words(text, words):
    assert split_words(text) == words, "split_words should split on whitespace and commas"


@pytest.mark.parametrize(
    "text, stash, rest",
    [
        ("grocery/ milk eggs", "grocery", "milk eggs"),
        ("grocery/milk", "grocery", "milk"),
        ("grocery/", "grocery", ""),
        ("  grocery/   milk | 2L", "grocery", "milk | 2L"),
        ("my-notes_2/ x", "my-notes_2", "x"),
        ("кава/ order", "кава", "order"),
        ("milk eggs", "", "milk eggs"),
        ("http://127.0.0.1:4000", "", "http://127.0.0.1:4000"),
        ("a/b/c", "a", "b/c"),
        ("/grocery milk", "", "/grocery milk"),
        ("", "", ""),
    ],
)
def test_split_stash_takes_a_leading_name_slash(text, stash, rest):
    assert split_stash(text) == (stash, rest), "a leading name/ is the stash, the rest is the query or the line"


@pytest.mark.parametrize(
    "stash, text, expected", [("grocery", "milk | 2L", "grocery/ milk | 2L"), ("", "milk", "milk")]
)
def test_in_stash_prefixes_text_with_the_stash(stash, text, expected):
    assert in_stash(stash, text) == expected, "in_stash should write the stash the way split_stash reads it"


@pytest.mark.parametrize(
    "name, valid", [("grocery", True), ("my-notes_2", True), ("кава", True), ("my notes", False), ("", False)]
)
def test_is_stash_name_accepts_what_split_stash_can_read(name, valid):
    assert is_stash_name(name) is valid, "a stash name must be typeable as name/ in a query"


def test_parse_line_keeps_the_stash():
    assert parse_line("milk | 2L", 3, "grocery").stash == "grocery", "parse_line should tag the entry with its stash"


@pytest.mark.parametrize(
    "line, date, label, payload",
    [
        ("2026-10-26: ssh prod | ssh deploy@h", "2026-10-26", "ssh prod", "ssh deploy@h"),
        ("2026-10-26: pihole update finished", "2026-10-26", "pihole update finished", "pihole update finished"),
        ("2026-10-26: | #FF8800", "2026-10-26", "#FF8800", "#FF8800"),
        ("2026-10-26: find py \\ find . -name '*.pyc'", "2026-10-26", "find py", "find . -name '*.pyc'"),
        ("2026-10-26:no space | x", "2026-10-26", "no space", "x"),
        ("  2026-10-26:   padded | x", "2026-10-26", "padded", "x"),
        ("2026-10-26: 2025-05-20 great day", "2026-10-26", "2025-05-20 great day", "2025-05-20 great day"),
        ("2026-10-26: 2025-05-20: typed stamp | x", "2026-10-26", "2025-05-20: typed stamp", "x"),
        ("ssh prod | ssh deploy@h", "", "ssh prod", "ssh deploy@h"),
        ("2026-10-26 no colon | x", "", "2026-10-26 no colon", "x"),
        ("2026-13-26: bad month | x", "", "2026-13-26: bad month", "x"),
        ("26-10-26: short year | x", "", "26-10-26: short year", "x"),
        ("release 2026-10-26: | x", "", "release 2026-10-26:", "x"),
    ],
)
def test_parse_line_takes_a_leading_date_colon_as_the_stamp(line, date, label, payload):
    entry = parse_line(line)

    assert entry.date == date, "a line starting with YYYY-MM-DD: carries that date; anything else is undated"
    assert entry.label == label, "the stamp is stripped before the separator rule, so it is never a label word"
    assert entry.payload == payload, "the stamp is never part of the payload either"


@pytest.mark.parametrize(
    "line, keywords",
    [
        ("2026-10-26: ssh prod | x", ("ssh", "prod")),
        ("2026-10-26: 2025-05-20 great day", ("2025-05-20", "great", "day")),
    ],
)
def test_stamp_is_not_a_search_word_but_a_date_in_the_text_is(line, keywords):
    assert tuple(parse_line(line).haystack.split()) == keywords, (
        "the stamp is metadata; a date you typed is an ordinary word"
    )


def test_parse_line_keeps_the_stamp_in_the_raw_line():
    assert parse_line(" 2026-10-26: wifi | pw \n").raw == "2026-10-26: wifi | pw", (
        "deletion matches the stored line, stamp included"
    )


@pytest.mark.parametrize(
    "line", ["2026-10-26:", "2026-10-26: ", "2026-10-26: |", "# 2026-10-26: a comment", "2026-10-26: # still a comment"]
)
def test_parse_line_skips_a_bare_stamp_and_a_stamped_comment(line):
    assert parse_line(line) is None, "a stamp with no entry after it is not an entry; after the stamp # still comments"


@pytest.mark.parametrize(
    "text, label, date",
    [("2026-10-20: typed | x", "2026-10-20: typed", ""), ("plain | x", "plain", ""), ("# nope", None, None)],
)
def test_parse_text_reads_what_was_typed_without_looking_for_a_stamp(text, label, date):
    entry = parse_text(text)

    assert (entry and entry.label) == label, "parse_text is for typed text, where a date is just words"
    assert (entry and entry.date) == date, "typed text never carries a stamp"


@pytest.mark.parametrize(
    "text, date, rest",
    [
        ("2026-10-26: ssh | x", "2026-10-26", "ssh | x"),
        ("2026-10-26:ssh", "2026-10-26", "ssh"),
        ("ssh | x", "", "ssh | x"),
        ("", "", ""),
    ],
)
def test_split_stamp(text, date, rest):
    assert split_stamp(text) == (date, rest), "split_stamp should take a leading YYYY-MM-DD: and leave the rest"


def test_stamped_writes_the_stamp_the_way_split_stamp_reads_it():
    line = stamped("2026-10-26", "ssh prod | ssh deploy@h")

    assert line == "2026-10-26: ssh prod | ssh deploy@h", "stamped should prepend date, colon, one space"
    assert split_stamp(line) == ("2026-10-26", "ssh prod | ssh deploy@h"), "stamped and split_stamp are inverses"
