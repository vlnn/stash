import json

import pytest

from alfred_db.alfred import add_preview_item, entry_item, render, search_feedback
from alfred_db.entries import parse_line

ENTRY = parse_line("ssh prod web | Prod web box | ssh deploy@10.0.1.5", line_number=12)


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
    "results, has_entries, expected_titles",
    [
        ([ENTRY], True, ["Prod web box"]),
        ([], True, ["No match for 'zzz'"]),
        ([], False, ["The database is empty"]),
    ],
)
def test_search_feedback(results, has_entries, expected_titles):
    titles = [item["title"] for item in search_feedback(results, has_entries, "zzz")]

    assert titles == expected_titles, "search_feedback should show results or explain why there are none"


@pytest.mark.parametrize("has_entries", [False, True])
def test_search_feedback_hints_are_not_actionable(has_entries):
    hint = search_feedback([], has_entries, "zzz")[0]

    assert hint["valid"] is False, "hint items should not trigger copy on enter"


@pytest.mark.parametrize(
    "raw, title, subtitle",
    [
        ("ssh prod | Prod | ssh p", "Add: Prod", "ssh prod  →  ssh p"),
        ("wifi guest", "Add: wifi guest", "wifi guest  →  wifi guest"),
    ],
)
def test_add_preview_item_shows_parsed_entry(raw, title, subtitle):
    item = add_preview_item(raw)

    assert item["title"] == title, "add_preview_item should show the resulting title"
    assert item["subtitle"] == subtitle, "add_preview_item should show keywords and payload"
    assert item["arg"] == raw, "add_preview_item should pass the line on to the add action"


@pytest.mark.parametrize("raw", ["", "  ", "# comment", " | title | payload"])
def test_add_preview_item_explains_format_for_invalid_input(raw):
    item = add_preview_item(raw)

    assert item["valid"] is False, "add_preview_item should block adding an invalid entry"
    assert "keywords | title | payload" in item["subtitle"], "add_preview_item should explain the expected format"


def test_render_wraps_items_as_ascii_safe_json():
    output = render([{"title": "Кава ☕"}])

    assert output.isascii(), "render should escape non-ASCII so any locale can print it"
    assert json.loads(output) == {"items": [{"title": "Кава ☕"}]}, "render should produce Alfred script filter JSON"
