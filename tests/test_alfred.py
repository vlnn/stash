import json

import pytest

from stash.alfred import add_item, entry_item, render, search_feedback
from stash.entries import parse_line

ENTRY = parse_line("ssh prod web | Prod web box | ssh deploy@10.0.1.5", line_number=12)
OTHER = parse_line("wifi guest | Guest wifi | hunter2", line_number=13)


def titles(items):
    return [item["title"] for item in items]


@pytest.mark.parametrize(
    "key, expected",
    [
        ("title", "Prod web box"),
        ("subtitle", "ssh deploy@10.0.1.5"),
        ("arg", "ssh deploy@10.0.1.5"),
        ("autocomplete", "ssh prod web"),
        ("uid", "ssh prod web|Prod web box"),
        ("text", {"copy": "ssh deploy@10.0.1.5", "largetype": "ssh deploy@10.0.1.5"}),
    ],
)
def test_entry_item_fields(key, expected):
    assert entry_item(ENTRY)[key] == expected, f"entry_item should set {key} for Alfred"


def test_entry_item_has_no_routing_variable():
    assert "variables" not in entry_item(ENTRY), "a plain entry should take the default (copy) route"


@pytest.mark.parametrize(
    "modifier, arg",
    [
        ("cmd", "12"),
        ("alt", "ssh prod web | Prod web box | ssh deploy@10.0.1.5"),
    ],
)
def test_entry_item_modifiers_carry_action_arguments(modifier, arg):
    assert entry_item(ENTRY)["mods"][modifier]["arg"] == arg, (
        f"{modifier} modifier should pass what its action needs"
    )


def test_entry_item_ctrl_reveals_keywords_without_action():
    ctrl = entry_item(ENTRY)["mods"]["ctrl"]

    assert ctrl["valid"] is False, "ctrl modifier should only reveal keywords, not trigger an action"
    assert "ssh prod web" in ctrl["subtitle"], "ctrl modifier should show the entry keywords"


@pytest.mark.parametrize(
    "raw, title, subtitle",
    [
        ("ssh prod | Prod | ssh p", "Add: Prod", "ssh prod  →  ssh p"),
        ("wifi guest", "Add: wifi guest", "wifi guest  →  wifi guest   (keywords | title | payload)"),
    ],
)
def test_add_item_shows_parsed_entry(raw, title, subtitle):
    item = add_item(raw)

    assert item["title"] == title, "add_item should show the resulting title"
    assert item["subtitle"] == subtitle, "add_item should show keywords and payload, and the format until a | is typed"
    assert item["arg"] == raw.strip(), "add_item should pass the line on to the add action"
    assert item["variables"] == {"action": "add"}, "add_item should route to the add action"


def test_add_item_modifiers_open_editor_and_nothing_else():
    mods = add_item("ssh prod")["mods"]

    assert mods["cmd"]["arg"] == "1", "cmd on the add item should open the stash in the editor"
    assert [mods[key]["valid"] for key in ("alt", "shift")] == [False, False], (
        "delete and paste make no sense on an entry that does not exist yet"
    )


@pytest.mark.parametrize("raw", ["", "  ", "# comment", " | title | payload"])
def test_add_item_is_absent_for_text_that_is_not_an_entry(raw):
    assert add_item(raw) is None, "add_item should offer nothing for text that cannot be stored"


@pytest.mark.parametrize(
    "results, entries, query, expected",
    [
        ([ENTRY], [ENTRY, OTHER], "prod", ["Prod web box", "Add: prod"]),
        ([ENTRY, OTHER], [ENTRY, OTHER], "", ["Prod web box", "Guest wifi"]),
        ([], [ENTRY], "zzz", ["Add: zzz"]),
        ([ENTRY], [ENTRY], "prod | Prod | p", ["Add: Prod", "Prod web box"]),
        ([], [], "new | New | n", ["Add: New"]),
        ([], [], "", ["The stash is empty"]),
        ([], [ENTRY], "| x", ["No match for '| x'"]),
    ],
)
def test_search_feedback_lists_matches_and_offers_to_add(results, entries, query, expected):
    assert titles(search_feedback(results, entries, query)) == expected, (
        "search_feedback should list matches, offer to add the query, and put Add first once a | is typed"
    )


@pytest.mark.parametrize("entries, query", [([], ""), ([ENTRY], "| x")])
def test_search_feedback_hints_are_not_actionable_except_for_editing(entries, query):
    hint = search_feedback([], entries, query)[0]

    assert hint["valid"] is False, "hint items should not copy anything on enter"
    assert hint["mods"]["cmd"]["arg"] == "1", "cmd on a hint should still open the editor"


def test_render_wraps_items_as_ascii_safe_json():
    output = render([{"title": "Кава ☕"}])

    assert output.isascii(), "render should escape non-ASCII so any locale can print it"
    assert json.loads(output) == {"items": [{"title": "Кава ☕"}]}, "render should produce Alfred script filter JSON"
