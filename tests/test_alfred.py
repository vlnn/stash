import json
import os

import pytest

from stash.alfred import (
    SCOPE_ICON,
    action_of,
    add_item,
    entry_item,
    feedback,
    flow_of,
    is_payload,
    prompt_items,
    render,
    root_hint,
    run_item,
    scope_hint,
    scope_item,
)
from stash.entries import parse_line

ENTRY = parse_line("ssh prod web | ssh deploy@10.0.1.5", line_number=12)
OTHER = parse_line("wifi guest | hunter2", line_number=13)
PLAIN = parse_line("pihole update finished", line_number=14)
SCOPED = parse_line("bread | sourdough", line_number=2, scope="grocery")


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
        ("stash", "copy"),
        ("tests/test_alfred.py", "copy"),
        (".", "copy"),
        ("ftp://old.example.com", "copy"),
        ("delany @kb", "alfred"),
        ("@tally", "alfred"),
        ("@t 33333", "alfred"),
        ("@here deploying now", "alfred"),
        ("name.surname@example.com", "copy"),
        ("echo @", "copy"),
    ],
)
def test_action_of_payload_shape(monkeypatch, payload, action):
    monkeypatch.chdir(os.path.join(os.path.dirname(__file__), os.pardir))

    assert action_of(payload) == action, "URLs and absolute paths that exist open, everything else is copied"


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
        ("@t 33333", ("t", "33333")),
        ("@tally new   task", ("t", "new   task")),
        ("@t new task @kb", ("kb", "@t new task")),
        ("name.surname@example.com", None),
        ("mail me@example.com now", None),
        ("plain text", None),
    ],
)
def test_flow_of_resolves_trailing_at_word_through_aliases(payload, flow):
    assert flow_of(payload, FLOWS) == flow, "a trailing @word names an Alfred keyword, aliases first"


def test_entry_item_for_flow_hands_the_query_to_alfred():
    item = entry_item(parse_line("delany | delany @kobold"), FLOWS)

    assert item["variables"] == {"action": "alfred"}, "a flow payload should route to the alfred action"
    assert item["arg"] == "kb delany", "the arg should be the keyword and text Alfred will run"
    assert item["subtitle"] == "→ kobold · delany", "the subtitle names the workflow the way the entry wrote it"
    assert item["mods"]["ctrl"]["subtitle"] == "Line 0 of the stash · alfred: kb delany", (
        "ctrl shows the resolved call, keyword included"
    )
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
    assert ctrl["subtitle"] == "Line 12 of the stash · copy", (
        "ctrl modifier should show where the entry lives and what enter does"
    )


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


ADD = "Add: prod"


@pytest.mark.parametrize(
    "matches, query, expected",
    [
        (["ssh prod web"], "prod", ["ssh prod web", ADD]),
        (["ssh prod web", "wifi guest"], "", ["ssh prod web", "wifi guest"]),
        ([], "prod", [ADD]),
        (["ssh prod web"], "prod | p", [ADD, "ssh prod web"]),
        (["ssh prod web"], "prod \\ p", [ADD, "ssh prod web"]),
        ([], "", ["hint"]),
        ([], "|", ["hint"]),
    ],
)
def test_feedback_lists_matches_and_offers_to_add(matches, query, expected):
    items = [{"title": title} for title in matches]

    assert titles(feedback(items, query, {"title": "hint"})) == expected, (
        "feedback should list matches, offer to add the query, put Add first once a separator is typed, "
        "and fall back to the hint when there is nothing to show"
    )


def test_feedback_inside_a_scope_adds_there():
    [addition] = feedback([], "pasta | 500g", {"title": "hint"}, "recipes", new_scope=True)

    assert addition["arg"] == "recipes/ pasta | 500g", "the add action should receive the scope with the line"
    assert addition["subtitle"] == "500g · new scope recipes/", "adding to a scope that does not exist yet says so"
    assert addition["mods"]["cmd"]["arg"] == "recipes/ 1", "cmd on the add row opens the scope's file"


@pytest.mark.parametrize(
    "stash_empty, query, title",
    [(True, "", "The stash is empty"), (False, "|", "No match for '|'")],
)
def test_root_hint(stash_empty, query, title):
    hint = root_hint(stash_empty, query)

    assert hint["title"] == title, "the root hint should say whether the stash is empty or the query matched nothing"
    assert hint["valid"] is False, "hint items should not copy anything on enter"
    assert hint["mods"]["cmd"]["arg"] == "1", "cmd on a hint should still open the editor"


@pytest.mark.parametrize(
    "exists, title, editor_arg",
    [(False, "New scope recipes/", "recipes/ 1"), (True, "recipes/ is empty", "recipes/ 1")],
)
def test_scope_hint(exists, title, editor_arg):
    hint = scope_hint("recipes", exists)

    assert hint["title"] == title, "the scope hint should tell a new scope from an empty one"
    assert hint["valid"] is False, "hint items should not copy anything on enter"
    assert hint["mods"]["cmd"] == {"arg": editor_arg, "subtitle": "Open recipes/ in your editor", "valid": True}, (
        "cmd on a scope hint should open that scope's file"
    )


def test_scope_item_browses_on_enter_and_looks_like_a_folder():
    item = scope_item("grocery", 12)

    assert item["title"] == "grocery/", "a scope row shows its name as it is typed"
    assert item["subtitle"] == "12 entries · ↩ to browse", "a scope row says how much is inside"
    assert item["valid"] is False and item["autocomplete"] == "grocery/ ", (
        "enter on an invalid row autocompletes, which drops the user into the scope"
    )
    assert item["icon"] == SCOPE_ICON == {"path": "scope.png"}, "a scope row should carry its own icon from the bundle"
    assert item["mods"]["cmd"] == {"arg": "grocery/ 1", "subtitle": "Open grocery/ in your editor", "valid": True}, (
        "cmd on a scope row opens its file"
    )
    assert [item["mods"][key]["valid"] for key in ("alt", "shift")] == [False, False], (
        "a whole scope is not deleted or pasted from a keystroke"
    )


def test_scope_item_counts_one_entry_in_the_singular():
    assert scope_item("grocery", 1)["subtitle"] == "1 entry · ↩ to browse", "grammar"


@pytest.mark.parametrize(
    "key, expected",
    [
        ("uid", "grocery/ bread|sourdough"),
        ("title", "bread"),
        ("subtitle", "grocery · sourdough"),
        ("autocomplete", "grocery/ bread"),
    ],
)
def test_entry_item_of_scoped_entry_seen_from_the_root(key, expected):
    assert entry_item(SCOPED)[key] == expected, f"a scoped entry at the root should carry its scope in {key}"


def test_entry_item_of_scoped_entry_seen_inside_its_scope_drops_the_origin():
    assert entry_item(SCOPED, within="grocery")["subtitle"] == "sourdough", "inside a scope the origin is implied"


@pytest.mark.parametrize(
    "modifier, arg, subtitle",
    [
        ("cmd", "grocery/ 2", "Edit line 2 of grocery/"),
        ("alt", "grocery/ bread | sourdough", "Delete: bread | sourdough"),
        ("ctrl", None, "Line 2 of grocery/ · copy"),
    ],
)
def test_entry_item_of_scoped_entry_routes_modifiers_to_its_file(modifier, arg, subtitle):
    mod = entry_item(SCOPED)["mods"][modifier]

    assert mod.get("arg") == arg, f"{modifier} on a scoped entry should name the scope so the action finds the file"
    assert mod["subtitle"] == subtitle, f"{modifier} subtitle should name the scope"


def test_render_wraps_items_as_ascii_safe_json():
    output = render([{"title": "Кава ☕"}])

    assert output.isascii(), "render should escape non-ASCII so any locale can print it"
    assert json.loads(output) == {"items": [{"title": "Кава ☕"}]}, "render should produce Alfred script filter JSON"


def test_entry_item_shift_pastes_the_payload_through_the_router():
    assert entry_item(ENTRY)["mods"]["shift"] == {
        "arg": "ssh deploy@10.0.1.5",
        "variables": {"action": "paste"},
        "subtitle": "Paste into the frontmost app",
    }, "shift-enter should route to paste with the payload as written"


TEMPLATE = parse_line("ssh box | ssh {{user=root}}@{{host}} since {{date}}", line_number=3)


def test_entry_item_with_placeholders_routes_to_the_prompt():
    item = entry_item(TEMPLATE, reserved={"date": "2026-10-25"})

    assert item["variables"] == {
        "action": "fill",
        "template": "ssh {{user=root}}@{{host}} since 2026-10-25",
        "filled": "{}",
        "finish": "",
    }, "reserved names are resolved before the prompt, the rest travels as the template"
    assert item["arg"] == "", "nothing is passed as argument so the prompt opens with an empty field"
    assert item["subtitle"] == "Fill user, host · ssh {{user=root}}@{{host}} since 2026-10-25", "preview and names"
    assert item["text"] == {
        "copy": "ssh {{user=root}}@{{host}} since {{date}}",
        "largetype": "ssh {{user=root}}@{{host}} since 2026-10-25",
    }, "cmd-c copies the line as written, large type shows the preview"
    assert item["mods"]["shift"]["variables"]["finish"] == "paste", "shift-enter asks to paste once filled"
    assert item["mods"]["ctrl"]["subtitle"] == "Line 3 of the stash · fill", "ctrl says the entry prompts"


def test_add_item_previews_reserved_names_but_stores_the_placeholder():
    item = add_item("stamp | {{date}} {{host}}", reserved={"date": "2026-10-25"})

    assert item["subtitle"] == "2026-10-25 {{host}}", "the add row previews what date becomes"
    assert item["arg"] == "stamp | {{date}} {{host}}", "the stored line keeps every placeholder"


def test_prompt_items_offer_empty_default_but_not_empty_clipboard():
    [row] = prompt_items("x {{sep=}} y", {}, "", "", {}, lambda: "")

    assert row["title"] == "sep (1/1): (empty)   (default)", "an explicit empty default is a real choice"
    assert row["arg"] == "x  y", "the empty default fills in as nothing"


@pytest.mark.parametrize(
    "query, expected",
    [
        ("delany @kobold", True),
        ("@wisp", True),
        ("@t 33333", True),
        ("https://example.com/x", True),
        ("release {{date}}", True),
        ("ssh {{host}}", True),
        ("delany books", False),
        ("name.surname@example.com", False),
        ("rm {} ${HOME}", False),
    ],
)
def test_is_payload_spots_hand_offs_links_and_blanks(query, expected):
    assert is_payload(query) is expected, "a query acts on its own when it is a hand-off, a URL or path, or has blanks"


def test_run_item_hands_off_what_was_typed_without_storing_it():
    item = run_item("delany @kobold", FLOWS, {})

    assert item["title"] == "Run: delany @kobold", "the run row shows the query as typed"
    assert item["subtitle"] == "→ kobold · delany", "and says who gets it"
    assert item["variables"] == {"action": "alfred"} and item["arg"] == "kb delany", "enter hands off"
    assert item["mods"]["alt"] == {"valid": False}, "there is nothing to delete"
    assert item["mods"]["ctrl"]["subtitle"] == "Not stored · alfred: kb delany", "ctrl makes the ephemeral nature plain"


def test_run_item_resolves_reserved_names_and_prompts_for_the_rest():
    copied = run_item("release {{date}}", {}, {"date": "2026-10-25"})
    prompted = run_item("ssh {{host}} {{date}}", {}, {"date": "2026-10-25"})

    assert copied["variables"] == {"action": "copy"} and copied["arg"] == "release 2026-10-25", (
        "a query with only reserved names is copied with them resolved"
    )
    assert copied["subtitle"] == "release 2026-10-25", "the subtitle previews the result"
    assert (
        prompted["variables"]["action"] == "fill" and prompted["variables"]["template"] == "ssh {{host}} 2026-10-25"
    ), "other blanks go through the prompt"


@pytest.mark.parametrize(
    "matches, query, expected",
    [
        (["ssh prod web"], "delany @kobold", ["ssh prod web", "Run: delany @kobold", "Add: delany @kobold"]),
        (["ssh prod web"], "release {{date}}", ["ssh prod web", "Run: release {{date}}", "Add: release {{date}}"]),
        (["ssh prod web"], "delany books", ["ssh prod web", "Add: delany books"]),
        (["ssh prod web"], "books | delany @kobold", ["Add: books", "ssh prod web"]),
        ([], "delany @kobold", ["Add: delany @kobold"]),
        ([], "https://example.com/x", ["Add: https://example.com/x"]),
        ([], "books | delany @kobold", ["Add: books"]),
    ],
)
def test_feedback_offers_run_only_beside_a_match(matches, query, expected):
    items = [{"title": title} for title in matches]

    assert titles(feedback(items, query, {"title": "hint"}, flows=FLOWS)) == expected, (
        "a found entry comes first and may be run; a typed payload is run only as the alternative beside it; "
        "new text is only ever added, and a typed separator means Add, as before"
    )
