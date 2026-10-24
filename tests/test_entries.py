import pytest

from stash.entries import Entry, parse_line, split_words


@pytest.mark.parametrize(
    "line, keywords, title, payload",
    [
        ("ssh prod web | Prod web box | ssh deploy@10.0.1.5", ("ssh", "prod", "web"), "Prod web box", "ssh deploy@10.0.1.5"),
        ("ssh prod | ssh deploy@10.0.1.5", ("ssh", "prod"), "ssh prod", "ssh deploy@10.0.1.5"),
        ("wifi guest", ("wifi", "guest"), "wifi guest", "wifi guest"),
        ("logs | Tail errors | tail -f app.log | grep ERROR", ("logs",), "Tail errors", "tail -f app.log | grep ERROR"),
        ("logs || tail -f app.log | grep ERROR", ("logs",), "logs", "tail -f app.log | grep ERROR"),
        ("  k8s   ctx  |  Kube context  |  kubectl ctx  ", ("k8s", "ctx"), "Kube context", "kubectl ctx"),
        ("k8s,ctx, staging | Staging | kubectl ctx staging", ("k8s", "ctx", "staging"), "Staging", "kubectl ctx staging"),
        ("email work | | me@example.com", ("email", "work"), "email work", "me@example.com"),
        ("note | Empty payload |", ("note",), "Empty payload", "note"),
    ],
)
def test_parse_line_reads_fields(line, keywords, title, payload):
    entry = parse_line(line)

    assert entry.keywords == keywords, "parse_line should split the first field into keywords"
    assert entry.title == title, "parse_line should use the title field or fall back to keywords"
    assert entry.payload == payload, "parse_line should keep the payload intact, pipes included"


@pytest.mark.parametrize(
    "line",
    ["", "   ", "\n", "# a comment", "   # indented comment", " | title | payload", ", , | title"],
)
def test_parse_line_skips_lines_without_entry(line):
    assert parse_line(line) is None, "parse_line should ignore blank lines, comments and entries without keywords"


def test_parse_line_remembers_position_and_source():
    entry = parse_line("  wifi guest | Guest | hunter2\n", line_number=7)

    assert entry.line_number == 7, "parse_line should keep the line number for editing"
    assert entry.raw == "wifi guest | Guest | hunter2", "parse_line should keep the stripped source line for deletion"


@pytest.mark.parametrize(
    "line, haystack",
    [
        ("ssh prod web | Prod web box | ssh deploy@10.0.1.5", " ssh prod web box "),
        ("Kube, CTX | Switch | kubectl", " kube ctx switch "),
        ("kw only | payload is not searchable", " kw only "),
        ("logs || tail -f app.log | grep ERROR", " logs "),
        ("wifi guest", " wifi guest "),
    ],
)
def test_haystack_holds_lowercase_unique_keywords_and_title_words(line, haystack):
    assert parse_line(line).haystack == haystack, "haystack should hold the searchable words, space-delimited"


def test_entry_is_hashable_value():
    first = parse_line("a | b | c")
    second = parse_line("a | b | c")

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
