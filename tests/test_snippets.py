import time

import pytest

from stash.snippets import (
    Placeholder,
    assignments,
    fill,
    has_placeholders,
    mentions,
    pending,
    placeholders,
    reserved_values,
)

NOON = time.strptime("2026-10-25 12:05", "%Y-%m-%d %H:%M")


@pytest.mark.parametrize(
    "text, expected",
    [
        ("ssh {{host}} -p {{port}}", [Placeholder("host"), Placeholder("port")]),
        ("{{host}} and {{host}} again", [Placeholder("host")]),
        ("{{host=10.0.0.1}}", [Placeholder("host", "10.0.0.1")]),
        ("{{host=}}", [Placeholder("host", "")]),
        ("{{host=a}} {{host=b}}", [Placeholder("host", "a")]),
        ("{{greeting=Hi there, friend!}}", [Placeholder("greeting", "Hi there, friend!")]),
        ("{{my-var_2}}", [Placeholder("my-var_2")]),
        ("today {{date}} at {{time}} from {{clipboard}}", []),
        ("find . -exec rm {} \\;", []),
        ("${HOME} {{ spaced }} {{1st}} {{}}", []),
        ('{"a": 1}', []),
        ("{{outer {{inner}} }}", [Placeholder("inner")]),
        ("", []),
    ],
)
def test_placeholders_are_double_braced_identifiers(text, expected):
    assert placeholders(text) == expected, (
        "placeholders should be {{identifier}} with an optional =default, unique by name, reserved names excluded"
    )


@pytest.mark.parametrize("text, expected", [("ssh {{host}}", True), ("ssh host", False), ("{{date}}", False)])
def test_has_placeholders_ignores_reserved_names(text, expected):
    assert has_placeholders(text) is expected, "an entry prompts only for placeholders that need a value"


def test_pending_skips_names_that_have_a_value():
    assert pending("{{a}} {{b}} {{c}}", {"b": "2"}) == [Placeholder("a"), Placeholder("c")], (
        "pending should list placeholders still without a value, in order of first appearance"
    )


@pytest.mark.parametrize(
    "text, values, expected",
    [
        ("ssh {{host}} -p {{port}}", {"host": "10.0.0.1", "port": "22"}, "ssh 10.0.0.1 -p 22"),
        ("{{host}} {{host}}", {"host": "h"}, "h h"),
        ("{{host=default}}", {"host": "given"}, "given"),
        ("{{host}} -p {{port}}", {"host": "h"}, "h -p {{port}}"),
        ("{{host=x}} -p {{port}}", {}, "{{host=x}} -p {{port}}"),
        ("rm {} {{date}}", {"date": "2026-10-25"}, "rm {} 2026-10-25"),
        ("{{name}}", {"name": "{{name}}"}, "{{name}}"),
        ("plain", {"x": "y"}, "plain"),
    ],
)
def test_fill_replaces_known_placeholders_and_leaves_the_rest(text, values, expected):
    assert fill(text, values) == expected, "fill should replace every occurrence of a known name, verbatim"


def test_reserved_values_resolve_date_and_time_without_touching_the_clipboard():
    def clipboard():
        pytest.fail("the clipboard should not be read unless mentioned")

    assert reserved_values(NOON, clipboard) == {"date": "2026-10-25", "time": "12:05"}, (
        "date and time are ISO, the clipboard is read only when some text mentions it"
    )


def test_reserved_values_read_the_clipboard_when_some_text_mentions_it():
    values = reserved_values(NOON, lambda: "pasted", ("plain", "wrap {{clipboard}}"))

    assert values["clipboard"] == "pasted", "{{clipboard}} should be filled from the clipboard"


@pytest.mark.parametrize("text, expected", [("{{clipboard}}", True), ("{{clipboard=x}}", True), ("clipboard", False)])
def test_mentions_looks_for_a_placeholder_by_name(text, expected):
    assert mentions(text, "clipboard") is expected, "mentions should find a placeholder, not the bare word"


@pytest.mark.parametrize(
    "pairs, expected",
    [
        (["host=10.0.0.1", "port=22"], {"host": "10.0.0.1", "port": "22"}),
        (["url=https://x?a=b"], {"url": "https://x?a=b"}),
        (["stray", "name="], {"name": ""}),
        ([], {}),
    ],
)
def test_assignments_split_at_the_first_equals_sign(pairs, expected):
    assert assignments(pairs) == expected, "command line values are name=value, split once"
