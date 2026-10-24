import json
import os

import pytest

from stash.alfred import action_of, add_item, entry_item, flow_of, render, search_feedback
from stash.entries import parse_line

ENTRY = parse_line("ssh prod web | ssh deploy@10.0.1.5", line_number=12)
OTHER = parse_line("wifi guest | hunter2", line_number=13)
PLAIN = parse_line("pihole update finished", line_number=14)


def titles(items):
    return [item["title"] for item in items]


@pytest.mark.parametrize(
    "payload, action",
    [
        ("ssh deploy@10.0.1.5", "copy"),
        ("pihole update finished", "copy"),
        ("https://grafana.example.com/d/api", "open"),
        ("http://127.0.0.1:4000", "open"),
        ("file:///Users/me/notes.md", "open"),
        ("alfred://runtrigger/com.anokhin.tally/open/?argument=x", "open"),
        ("/usr/bin/env python3 -c 'print(1)'", "copy"),
        ("~/nowhere/that/exists", "copy"),
        ("ftp://old.example.com", "copy"),
        ("delany @kb", "alfred"),
        ("@tally", "alfred"),
        ("name.surname@example.com", "copy"),
        ("echo @", "copy"),
    ],
)
def test_action_of_payload_shape(payload, action):
    assert action_of(payload) == action, "URLs and existing paths open, everything else is copied"


@pytest.mark.parametrize("spelling", ["{tmp}", "{tmp}/notes.md", "~/{rel}"])
def test_action_of_existing_path_is_open(tmp_path, monkeypatch, spelling):
    (tmp_path / "notes.md").write_text("x")
    monkeypatch.setenv("HOME", str(tmp_path.parent))
    payload = spelling.format(tmp=tmp_path, rel=os.path.join(tmp_path.name, "notes.md"))

    assert action_of(payload) == "open", "a path that exists on disk should open, with ~ expanded"


FLOWS = {"tally": "t", "kobold": "kb"}


@pytest.mark.parametrize(
    "payload, flow",
    [
        ("delany @kb", ("kb", "delany")),
        ("parser lexer @tally", ("t", "parser lexer")),
        ("parser lexer   @tally", ("t", "parser lexer")),
        ("@tally", ("t", "")),
        ("@unknown", ("unknown", "")),
        ("name.surname@example.com", None),
        ("plain text", None),
    ],
)
def test_flow_of_resolves_trailing_at_word_through_aliases(payload, flow):
    assert flow_of(payload, FLOWS) == flow, "a trailing @word names an Alfred keyword, aliases first"


def test_entry_item_for_flow_hands_the_query_to_alfred():
    item = entry_item(parse_line("delany | delany @kobold"), FLOWS)

    assert item["variables"] == {"action": "alfred"}, "a flow payload should route to the alfred action"
    assert item["arg"] == "kb delany", "the arg should be the keyword and text Alfred will run"
    assert item["subtitle"] == "Alfred · kb delany", "the subtitle should show what Alfred will be asked"
    assert item["text"]["copy"] == "delany @kobold", "cmd-c should still copy the payload as written"


@pytest.mark.parametrize(
    "key, expected",
    [
        ("title", "ssh prod web"),
        ("subtitle", "ssh deploy@10.0.1.5"),
        ("arg", "ssh deploy@10.0.1.5"),
        ("autocomplete", "ssh prod web"),
        ("uid", "ssh prod web|ssh deploy@10.0.1.5"),
        ("text", {"copy": "ssh deploy@10.0.1.5", "largetype": "ssh deploy@10.0.1.5"}),
        ("variables", {"action": "copy"}),
    ],
)
def test_entry_item_fields(key, expected):
    assert entry_item(ENTRY)[key] == expected, f"entry_item should set {key} for Alfred"


def test_entry_item_without_separator_shows_the_action_instead_of_repeating_itself():
    item = entry_item(PLAIN)

    assert item["title"] == "pihole update finished", "a plain line is shown as itself"
    assert item["subtitle"] == "Copy", "the subtitle should not repeat the title"


def test_entry_item_for_url_opens_and_expands_tilde(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "notes.md").write_text("x")
    item = entry_item(parse_line("notes | ~/notes.md"))

    assert item["variables"] == {"action": "open"}, "an existing path should route to open"
    assert item["arg"] == str(tmp_path / "notes.md"), "the path handed to open should have ~ expanded"
    assert item["text"]["copy"] == "~/notes.md", "cmd-c should still copy the payload as written"
    assert item["subtitle"] == "Open · ~/notes.md", "the subtitle should say what enter does"


@pytest.mark.parametrize(
    "modifier, arg",
    [
        ("cmd", "12"),
        ("alt", "ssh prod web | ssh deploy@10.0.1.5"),
    ],
)
def test_entry_item_modifiers_carry_action_arguments(modifier, arg):
    assert entry_item(ENTRY)["mods"][modifier]["arg"] == arg, f"{modifier} modifier should pass what its action needs"


def test_entry_item_ctrl_shows_line_without_action():
    ctrl = entry_item(ENTRY)["mods"]["ctrl"]

    assert ctrl["valid"] is False, "ctrl modifier should only inform, not trigger an action"
    assert ctrl["subtitle"] == "Line 12 · copy", "ctrl modifier should show where the entry lives and what enter does"


@pytest.mark.parametrize(
    "raw, title, subtitle",
    [
        ("ssh prod | ssh p", "Add: ssh prod", "ssh p"),
        ("ssh prod \\ ssh p", "Add: ssh prod", "ssh p"),
        ("wifi guest", "Add: wifi guest", "wifi guest   (words | payload)"),
        ("http://127.0.0.1:4000", "Add: http://127.0.0.1:4000", "http://127.0.0.1:4000   (words | payload)"),
    ],
)
def test_add_item_shows_parsed_entry(raw, title, subtitle):
    item = add_item(raw)

    assert item["title"] == title, "add_item should show the label"
    assert item["subtitle"] == subtitle, "add_item should show the payload, and the format until a separator is typed"
    assert item["arg"] == raw.strip(), "add_item should pass the line on to the add action"
    assert item["variables"] == {"action": "add"}, "add_item should route to the add action"


def test_add_item_modifiers_open_editor_and_nothing_else():
    mods = add_item("ssh prod")["mods"]

    assert mods["cmd"]["arg"] == "1", "cmd on the add item should open the stash in the editor"
    assert [mods[key]["valid"] for key in ("alt", "shift")] == [False, False], (
        "delete and paste make no sense on an entry that does not exist yet"
    )


@pytest.mark.parametrize("raw", ["", "  ", "# comment", "|", " \\ "])
def test_add_item_is_absent_for_text_that_is_not_an_entry(raw):
    assert add_item(raw) is None, "add_item should offer nothing for text that cannot be stored"


@pytest.mark.parametrize(
    "results, entries, query, expected",
    [
        ([ENTRY], [ENTRY, OTHER], "prod", ["ssh prod web", "Add: prod"]),
        ([ENTRY, OTHER], [ENTRY, OTHER], "", ["ssh prod web", "wifi guest"]),
        ([], [ENTRY], "zzz", ["Add: zzz"]),
        ([ENTRY], [ENTRY], "prod | p", ["Add: prod", "ssh prod web"]),
        ([ENTRY], [ENTRY], "prod \\ p", ["Add: prod", "ssh prod web"]),
        ([], [], "new | n", ["Add: new"]),
        ([], [], "", ["The stash is empty"]),
        ([], [ENTRY], "|", ["No match for '|'"]),
    ],
)
def test_search_feedback_lists_matches_and_offers_to_add(results, entries, query, expected):
    assert titles(search_feedback(results, entries, query)) == expected, (
        "search_feedback should list matches, offer to add the query, and put Add first once a separator is typed"
    )


@pytest.mark.parametrize("entries, query", [([], ""), ([ENTRY], "|")])
def test_search_feedback_hints_are_not_actionable_except_for_editing(entries, query):
    hint = search_feedback([], entries, query)[0]

    assert hint["valid"] is False, "hint items should not copy anything on enter"
    assert hint["mods"]["cmd"]["arg"] == "1", "cmd on a hint should still open the editor"


def test_render_wraps_items_as_ascii_safe_json():
    output = render([{"title": "Кава ☕"}])

    assert output.isascii(), "render should escape non-ASCII so any locale can print it"
    assert json.loads(output) == {"items": [{"title": "Кава ☕"}]}, "render should produce Alfred script filter JSON"
