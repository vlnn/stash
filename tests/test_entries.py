import pytest

from stash.entries import Entry, in_scope, is_scope_name, parse_line, split_scope, split_words


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
    "text, scope, rest",
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
def test_split_scope_takes_a_leading_name_slash(text, scope, rest):
    assert split_scope(text) == (scope, rest), "a leading name/ is the scope, the rest is the query or the line"


@pytest.mark.parametrize(
    "scope, text, expected", [("grocery", "milk | 2L", "grocery/ milk | 2L"), ("", "milk", "milk")]
)
def test_in_scope_prefixes_text_with_the_scope(scope, text, expected):
    assert in_scope(scope, text) == expected, "in_scope should write the scope the way split_scope reads it"


@pytest.mark.parametrize(
    "name, valid", [("grocery", True), ("my-notes_2", True), ("кава", True), ("my notes", False), ("", False)]
)
def test_is_scope_name_accepts_what_split_scope_can_read(name, valid):
    assert is_scope_name(name) is valid, "a scope name must be typeable as name/ in a query"


def test_parse_line_keeps_the_scope():
    assert parse_line("milk | 2L", 3, "grocery").scope == "grocery", "parse_line should tag the entry with its scope"
