import json
import os
import time

import pytest

from stash.cli import (
    ALFRED_SEARCH,
    DEFAULT_DB_DIR,
    DEFAULT_EDITOR,
    DEFAULT_MAX_RESULTS,
    Prompt,
    config_from,
    editor_argv,
    flows_from,
    main,
)
from stash.views import VIEWS

DATABASE = "ssh prod web | ssh deploy@10.0.1.5\nwifi guest | hunter2\n"


GROCERY = "milk eggs | 2L and a dozen\nbread | sourdough\n"


@pytest.fixture
def db_dir(tmp_path):
    (tmp_path / "default.txt").write_text(DATABASE, encoding="utf-8")
    return tmp_path


@pytest.fixture
def db_file(db_dir):
    return db_dir / "default.txt"


@pytest.fixture
def grocery(db_dir):
    path = db_dir / "grocery.txt"
    path.write_text(GROCERY, encoding="utf-8")
    return path


@pytest.fixture
def env(db_dir):
    return {"db_dir": str(db_dir)}


@pytest.fixture
def stashed_env(env):
    return {**env, "show_stashes": "1"}


def run(capsys, env, *argv):
    main(list(argv), env)
    return capsys.readouterr().out.strip()


def item_titles(output):
    return [item["title"] for item in json.loads(output)["items"]]


DEFAULTS = (os.path.expanduser(DEFAULT_DB_DIR), DEFAULT_EDITOR, DEFAULT_MAX_RESULTS, {}, False, Prompt())


@pytest.mark.parametrize(
    "env, expected",
    [
        ({}, DEFAULTS),
        ({"db_dir": "", "editor": "", "max_results": "", "flows": "", "show_stashes": ""}, DEFAULTS),
        ({"show_stashes": "0"}, DEFAULTS),
        (
            {
                "db_dir": "~/db",
                "editor": "code -g {file}:{line}",
                "max_results": "9",
                "flows": "tally=t",
                "show_stashes": "1",
            },
            (os.path.expanduser("~/db"), "code -g {file}:{line}", 9, {"tally": "t"}, True, Prompt()),
        ),
        (
            {"template": "ssh {{host}}", "filled": '{"port": "22"}', "finish": "paste"},
            (*DEFAULTS[:5], Prompt("ssh {{host}}", {"port": "22"}, "paste")),
        ),
    ],
)
def test_config_from_environment(env, expected):
    assert tuple(config_from(env)) == expected, "config_from should read Alfred workflow variables with defaults"


@pytest.mark.parametrize(
    "argv, expected",
    [
        (["search", "prod"], ["ssh prod web", "Add: prod"]),
        (["search", "web", "prod"], ["ssh prod web", "Add: web prod"]),
        (["search", ""], ["ssh prod web", "wifi guest"]),
        (["search"], ["ssh prod web", "wifi guest"]),
        (["search", "zzz"], ["Add: zzz"]),
        (["search", "hunter2"], ["wifi guest", "Add: hunter2"]),
        (["search", "deploy"], ["ssh prod web", "Add: deploy"]),
        (["search", "prod | ssh prod"], ["Add: prod", "ssh prod web"]),
        (["search", "prod \\ ssh prod"], ["Add: prod", "ssh prod web"]),
        (["search", "| echo a | wc"], ["Add: echo a | wc"]),
        (["search", "grocery/ | echo a"], ["Add: echo a"]),
        (["search", "today/ | echo a"], ["Add: echo a"]),
    ],
)
def test_search_prints_alfred_items(capsys, env, argv, expected):
    assert item_titles(run(capsys, env, *argv)) == expected, f"{argv} should print matching Alfred items"


def test_search_limits_results(capsys, env):
    assert len(item_titles(run(capsys, {**env, "max_results": "1"}, "search", ""))) == 1, (
        "search should honour max_results"
    )


def test_search_on_missing_database_offers_to_add(capsys, tmp_path):
    output = run(capsys, {"db_dir": str(tmp_path / "none")}, "search", "x")

    assert item_titles(output) == ["Add: x"], "search on an empty stash should offer to add the query"


def test_search_on_missing_database_with_empty_query_says_so(capsys, tmp_path):
    output = run(capsys, {"db_dir": str(tmp_path / "none")}, "search", "")

    assert item_titles(output) == ["Nothing stashed yet"], "search should guide the user when nothing is stashed"


def test_search_survives_undecodable_bytes(capsys, env, db_file):
    db_file.write_bytes(DATABASE.encode() + b"caf\xe9 | x\n")

    assert len(item_titles(run(capsys, env, "search", ""))) == 3, (
        "search should still list entries when the file has a non-UTF-8 byte"
    )


def test_add_appends_a_stamped_entry_and_confirms(capsys, env, db_file, frozen_clock):
    output = run(capsys, env, "add", "  k8s ctx | kubectl ctx  ")

    assert output == "Added: k8s ctx", "add should confirm with the entry label"
    assert db_file.read_text(encoding="utf-8").endswith("\n2026-10-25: k8s ctx | kubectl ctx\n"), (
        "add should append the stripped line with today's stamp in front"
    )


@pytest.mark.parametrize("raw", ["", "# nope", " | "])
def test_add_rejects_invalid_entry(capsys, env, db_file, raw):
    output = run(capsys, env, "add", raw)

    assert output.startswith("Nothing added"), "add should explain why nothing was added"
    assert db_file.read_text(encoding="utf-8") == DATABASE, "add should not touch the database on invalid input"


def test_added_entry_is_searchable(capsys, env):
    run(capsys, env, "add", "k8s ctx kube | kubectl ctx")

    assert item_titles(run(capsys, env, "search", "kub"))[0] == "k8s ctx kube", "a freshly added entry should be found"


@pytest.mark.parametrize(
    "raw, expected_output, expected_titles",
    [
        ("wifi guest | hunter2", "Deleted: wifi guest | hunter2", ["ssh prod web"]),
        ("gone | x", "Not deleted: entry not found, the file may have changed", ["ssh prod web", "wifi guest"]),
    ],
)
def test_delete(capsys, env, frozen_clock, raw, expected_output, expected_titles):
    assert run(capsys, env, "delete", raw) == expected_output, "delete should report what happened"
    assert item_titles(run(capsys, env, "search", "")) == expected_titles, "delete should remove only that entry"


def test_delete_keeps_the_line_as_a_dated_comment(capsys, env, db_file, frozen_clock):
    run(capsys, env, "delete", "wifi guest | hunter2")

    assert db_file.read_text(encoding="utf-8") == (
        "ssh prod web | ssh deploy@10.0.1.5\n# deleted 2026-10-25: wifi guest | hunter2\n"
    ), "a keystroke should never destroy data: the line stays in the file, commented out with the day"


@pytest.mark.parametrize(
    "template, file, line, argv",
    [
        ("open -t {file}", "/db/e.txt", "3", ["open", "-t", "/db/e.txt"]),
        ("code -g {file}:{line}", "/db/e.txt", "3", ["code", "-g", "/db/e.txt:3"]),
        ("/usr/local/bin/subl {file}:{line}", "/my db/e.txt", "3", ["/usr/local/bin/subl", "/my db/e.txt:3"]),
        ("'/Applications/My Editor' +{line} {file}", "/db/e.txt", "7", ["/Applications/My Editor", "+7", "/db/e.txt"]),
        ("vim '+{line}' {file}", "/db/{odd}.txt", "2", ["vim", "+2", "/db/{odd}.txt"]),
        ("ed {typo} {file}", "/db/e.txt", "2", ["ed", "{typo}", "/db/e.txt"]),
    ],
)
def test_editor_argv(template, file, line, argv):
    assert editor_argv(template, file, line) == argv, "editor_argv should fill placeholders without choking on braces"


@pytest.mark.parametrize("argv, line", [(["edit", "12"], "12"), (["edit"], "1"), (["edit", ""], "1")])
def test_edit_replaces_process_with_editor(mocker, capsys, env, db_file, argv, line):
    execvp = mocker.patch("stash.cli.os.execvp")

    run(capsys, {**env, "editor": "code -g {file}:{line}"}, *argv)

    assert execvp.call_args_list == [mocker.call("code", ["code", "-g", f"{db_file}:{line}"])], (
        "edit should hand the process over to the editor at the requested line"
    )


def test_edit_creates_missing_database(mocker, capsys, tmp_path):
    mocker.patch("stash.cli.os.execvp")
    path = tmp_path / "new"

    run(capsys, {"db_dir": str(path)}, "edit")

    assert (path / "default.txt").is_file(), "edit should create the database so the editor has something to open"


def test_edit_reports_missing_editor(mocker, capsys, env):
    mocker.patch("stash.cli.os.execvp", side_effect=FileNotFoundError)

    output = run(capsys, {**env, "editor": "nosuch {file}"}, "edit")

    assert output == "Editor not found: nosuch (use a full path in the editor variable)", (
        "edit should explain how to fix a missing editor"
    )


@pytest.mark.parametrize(
    "text, flows",
    [
        ("", {}),
        ("tally=t kobold=kb", {"tally": "t", "kobold": "kb"}),
        ("tally=t, kobold = kb ,wisp=l", {"tally": "t", "kobold": "kb", "wisp": "l"}),
        ("broken tally=t", {"tally": "t"}),
    ],
)
def test_flows_from_variable(text, flows):
    assert flows_from(text) == flows, "flows should be name=keyword pairs separated by spaces or commas"


def test_search_resolves_flow_aliases(capsys, env, db_file):
    db_file.write_text("books | delany @kobold\n", encoding="utf-8")

    [item, _] = json.loads(run(capsys, {**env, "flows": "kobold=kb"}, "search", "books"))["items"]

    assert item["arg"] == "kb delany", "search should resolve @kobold through the flows variable"


def test_alfred_asks_alfred_to_search(mocker, capsys, env):
    run_process = mocker.patch("stash.cli.subprocess.run", return_value=mocker.Mock(returncode=0, stderr=""))

    output = run(capsys, env, "alfred", "kb delany")

    assert run_process.call_args.args == (["osascript", *ALFRED_SEARCH, "kb delany"],), (
        "alfred should pass the query as an argument rather than splice it into the script"
    )
    assert output == "", "a successful hand-off should stay silent"


def test_alfred_explains_how_to_grant_automation_permission(mocker, capsys, env):
    refused = mocker.Mock(
        returncode=1, stderr="execution error: Not authorized to send Apple events to Alfred. (-1743)"
    )
    mocker.patch("stash.cli.subprocess.run", return_value=refused)

    output = run(capsys, env, "alfred", "kb delany")

    assert output.startswith("macOS has not let Stash drive Alfred yet."), "a refused hand-off should say what happened"
    assert 'osascript -e \'tell application id "com.runningwithcrayons.Alfred" to search "kb delany"\'' in output, (
        "the notification should carry the exact Terminal line that triggers the permission dialog"
    )


@pytest.mark.parametrize("payload", ["https://example.com/x", "/tmp/some file.pdf"])
def test_open_replaces_process_with_open(mocker, capsys, env, payload):
    execvp = mocker.patch("stash.cli.os.execvp")

    run(capsys, env, "open", payload)

    assert execvp.call_args_list == [mocker.call("open", ["open", payload])], (
        "open should hand the process over to macOS open with the payload as given"
    )


@pytest.mark.parametrize("argv", [[], ["unknown"]])
def test_main_rejects_unknown_command(env, argv):
    with pytest.raises(SystemExit) as exit_info:
        main(argv, env)

    assert "usage" in str(exit_info.value), "main should print usage for unknown commands"


@pytest.mark.parametrize(
    "query, expected",
    [
        ("", ["grocery/", "ssh prod web", "wifi guest", "milk eggs", "bread"]),
        ("gro", ["grocery/", "Add: gro"]),
        ("eggs", ["milk eggs", "Add: eggs"]),
        ("e", ["grocery/", "wifi guest", "ssh prod web", "milk eggs", "bread", "Add: e"]),
        ("grocery/", ["milk eggs", "bread"]),
        ("grocery/ milk", ["milk eggs", "Add: milk"]),
        ("grocery/bread", ["bread", "Add: bread"]),
        ("grocery/ prod", ["Add: prod"]),
        ("grocery/ pasta | 500g", ["Add: pasta"]),
        ("recipes/", ["New stash recipes/"]),
        ("recipes/ pasta", ["Add: pasta"]),
    ],
)
def test_search_tiers_stashes_root_and_stashed_entries(capsys, stashed_env, grocery, query, expected):
    assert item_titles(run(capsys, stashed_env, "search", query)) == expected, (
        "stash rows come first, then root entries, then stashed entries; name/ narrows to one stash"
    )


def test_search_marks_stashed_entries_at_the_root_but_not_inside_their_stash(capsys, env, grocery):
    [at_root, _] = json.loads(run(capsys, env, "search", "bread"))["items"]
    [inside, _] = json.loads(run(capsys, env, "search", "grocery/ bread"))["items"]

    assert at_root["subtitle"] == "grocery · sourdough", "a stashed hit at the root should say where it lives"
    assert inside["subtitle"] == "sourdough", "inside its stash an entry looks like any other"


@pytest.mark.parametrize(
    "query, expected",
    [
        ("", ["ssh prod web", "wifi guest", "milk eggs", "bread"]),
        ("gro", ["grocery/", "Add: gro"]),
        ("e", ["grocery/", "wifi guest", "ssh prod web", "milk eggs", "bread", "Add: e"]),
        ("grocery/", ["milk eggs", "bread"]),
        ("grocery/ milk", ["milk eggs", "Add: milk"]),
    ],
)
def test_search_lists_a_stash_row_only_when_its_name_is_typed(capsys, env, grocery, query, expected):
    assert item_titles(run(capsys, env, "search", query)) == expected, (
        "a bare st hides stash rows unless show_stashes is on; words that match a stash name always list its row"
    )


def test_stash_row_expands_on_tab(capsys, env, grocery):
    [row, _] = json.loads(run(capsys, env, "search", "gro"))["items"]

    assert row["autocomplete"] == "grocery/ " and row["valid"] is False, "tab or enter on the row enters the stash"


def test_search_counts_stash_rows_against_max_results(capsys, stashed_env, grocery):
    titles = item_titles(run(capsys, {**stashed_env, "max_results": "2"}, "search", ""))

    assert titles == ["grocery/", "ssh prod web"], "max_results should cap the whole list, stash rows included"


def test_search_with_only_stashs_lists_them(capsys, tmp_path):
    (tmp_path / "grocery.txt").write_text(GROCERY, encoding="utf-8")

    assert item_titles(run(capsys, {"db_dir": str(tmp_path), "show_stashes": "1"}, "search", "")) == [
        "grocery/",
        "milk eggs",
        "bread",
    ], "a stash with stashes and no default.txt is not empty"


def test_add_into_stash_creates_its_file(capsys, env, db_dir, frozen_clock):
    output = run(capsys, env, "add", "recipes/ pasta | 500g, 10 min")

    assert output == "Added to recipes/: pasta", "add should say which stash received the entry"
    assert (db_dir / "recipes.txt").read_text(encoding="utf-8") == "2026-10-25: pasta | 500g, 10 min\n", (
        "the first entry of a stash should create its file, stamped, without the stash prefix"
    )
    assert (db_dir / "default.txt").read_text(encoding="utf-8") == DATABASE, "the root should be untouched"


def test_delete_from_stash(capsys, env, grocery, frozen_clock):
    assert run(capsys, env, "delete", "grocery/ bread | sourdough") == "Deleted: bread | sourdough", (
        "delete should remove the line from the stash's file"
    )
    assert grocery.read_text(encoding="utf-8") == (
        "milk eggs | 2L and a dozen\n# deleted 2026-10-25: bread | sourdough\n"
    ), "only that line should go, and it should stay in the file as a comment"


def test_delete_from_stash_reports_unknown_entry(capsys, env, grocery, frozen_clock):
    assert run(capsys, env, "delete", "grocery/ ssh prod web | ssh deploy@10.0.1.5").startswith("Not deleted"), (
        "a root entry is not found in a stash's file"
    )


def test_edit_opens_the_stash_file_at_the_line(mocker, capsys, env, db_dir):
    execvp = mocker.patch("stash.cli.os.execvp")

    run(capsys, {**env, "editor": "code -g {file}:{line}"}, "edit", "recipes/ 4")

    assert execvp.call_args_list == [mocker.call("code", ["code", "-g", f"{db_dir / 'recipes.txt'}:4"])], (
        "edit should open the stash's file"
    )
    assert (db_dir / "recipes.txt").is_file(), "edit should create the stash's file so the editor can open it"


def test_search_in_an_empty_stash_says_so(capsys, env, db_dir):
    (db_dir / "grocery.txt").write_text("# nothing yet\n", encoding="utf-8")

    assert item_titles(run(capsys, env, "search", "grocery/")) == ["grocery/ is empty"], (
        "a stash file without entries should be told apart from a stash that does not exist"
    )


NOON = time.strptime("2026-10-25 12:05", "%Y-%m-%d %H:%M")
TEMPLATES = "ssh {{host}} -p {{port=22}} | ssh root@{{host}} -p {{port=22}}\nstamp | note of {{date}} {{time}}\n"


@pytest.fixture
def frozen_clock(mocker):
    mocker.patch("stash.cli.time.localtime", return_value=NOON)
    return mocker.patch("stash.cli.read_clipboard", return_value="from clipboard")


@pytest.fixture
def templates(db_file):
    db_file.write_text(TEMPLATES, encoding="utf-8")


def test_search_resolves_reserved_names_and_leaves_the_rest_for_the_prompt(capsys, env, templates, frozen_clock):
    [stamp, ssh, _] = json.loads(run(capsys, env, "search", "s"))["items"]

    assert stamp["variables"] == {"action": "copy"} and stamp["arg"] == "note of 2026-10-25 12:05", (
        "date and time fill themselves, so the entry copies as usual"
    )
    assert (
        ssh["variables"]["action"] == "fill" and ssh["variables"]["template"] == "ssh root@{{host}} -p {{port=22}}"
    ), "an entry with placeholders routes to the prompt with its template"
    assert ssh["subtitle"] == "Fill host, port · ssh root@{{host}} -p {{port=22}}", "the subtitle previews the template"
    assert frozen_clock.call_count == 0, "the clipboard is not read unless an entry mentions it"


def test_search_never_reads_the_clipboard(capsys, env, db_file, frozen_clock):
    db_file.write_text("wrap | echo '{{clipboard}}'\n", encoding="utf-8")

    output = run(capsys, env, "search", "wrap")
    [item, _] = json.loads(output)["items"]

    assert frozen_clock.call_count == 0, "the clipboard is read on enter, not on every keystroke"
    assert "from clipboard" not in output, "the clipboard must never appear in the results list"
    assert item["variables"] == {"action": "resolve", "template": "echo '{{clipboard}}'", "finish": ""}, (
        "an entry mentioning the clipboard routes to resolve, which fills it on enter"
    )
    assert item["subtitle"] == "echo '{{clipboard}}'", "the preview shows the placeholder, not the clipboard"
    assert item["mods"]["shift"]["variables"]["finish"] == "paste", "shift-enter asks to paste once resolved"


@pytest.mark.parametrize(
    "template, finish, expected",
    [
        ("echo '{{clipboard}}'", "", {"arg": "echo 'from clipboard'", "variables": {"action": "copy"}}),
        ("echo '{{clipboard}}'", "paste", {"arg": "echo 'from clipboard'", "variables": {"action": "paste"}}),
        ("https://x.test/{{clipboard}}", "", {"arg": "https://x.test/from clipboard", "variables": {"action": "open"}}),
        ("{{clipboard}} @kobold", "", {"arg": "kb from clipboard", "variables": {"action": "alfred"}}),
    ],
)
def test_resolve_fills_the_clipboard_and_hands_the_result_to_the_router(
    capsys, env, frozen_clock, template, finish, expected
):
    state = {**env, "flows": "kobold=kb", "template": template, "finish": finish}

    output = json.loads(run(capsys, state, "resolve"))

    assert output == {"alfredworkflow": expected}, "resolve should fill the clipboard and route like an entry would"
    assert frozen_clock.call_count == 1, "resolve reads the clipboard exactly once"


def test_prompt_fills_the_clipboard_placeholder_before_asking_for_the_rest(capsys, env, frozen_clock):
    [typed, *_] = prompt(capsys, env, "h", "ssh {{host}} < {{clipboard}}")

    assert typed["arg"] == "ssh h < from clipboard", "the prompt runs after enter, so it may resolve the clipboard"


def test_add_row_previews_reserved_names(capsys, env, frozen_clock):
    [*_, addition] = json.loads(run(capsys, env, "search", "note | today is {{date}}"))["items"]

    assert addition["subtitle"] == "today is 2026-10-25", "typing {{date}} should show what it will become"
    assert addition["arg"] == "note | today is {{date}}", "the stored line keeps the placeholder"


def prompt(capsys, env, query, template, filled="{}", finish=""):
    state = {"template": template, "filled": filled, "finish": finish}
    return json.loads(run(capsys, {**env, **state}, "prompt", query))["items"]


def test_prompt_first_step_offers_default_and_clipboard(capsys, env, frozen_clock):
    [default, clipboard] = prompt(capsys, env, "", "ssh {{host=10.0.0.1}} -p {{port}}")

    assert default["title"] == "host (1/2): 10.0.0.1   (default)", "the default comes first when nothing is typed"
    assert clipboard["title"] == "host (1/2): from clipboard   (clipboard)", "the clipboard is always one row away"
    assert default["subtitle"] == "ssh 10.0.0.1 -p {{port}}", "each row previews the payload with that value"
    assert default["variables"] == {
        "action": "fill",
        "template": "ssh {{host=10.0.0.1}} -p {{port}}",
        "filled": '{"host": "10.0.0.1"}',
        "finish": "",
    }, "a non-final step routes back to the prompt with the value recorded"
    assert default["arg"] == "", "a non-final step passes no argument, so the next prompt opens empty"


def test_prompt_typed_value_comes_first(capsys, env, frozen_clock):
    [typed, *_] = prompt(capsys, env, "db.example.com", "ssh {{host=10.0.0.1}}")

    assert typed["title"] == "host (1/1): db.example.com", "what you type is the first row"


def test_prompt_last_step_performs_the_entry_action(capsys, env, frozen_clock):
    [typed, _] = prompt(capsys, env, "2222", "ssh {{host}} -p {{port}}", '{"host": "h"}')

    assert typed["title"] == "port (2/2): 2222", "the counter shows which step this is"
    assert typed["variables"] == {"action": "copy"} and typed["arg"] == "ssh h -p 2222", (
        "the last step carries the filled payload to the usual action"
    )
    assert typed["subtitle"] == "Copy · ssh h -p 2222", "the last step says what enter will do"
    assert typed["mods"]["shift"] == {
        "arg": "ssh h -p 2222",
        "variables": {"action": "paste"},
        "subtitle": "Paste into the frontmost app",
    }, "shift-enter on the last step pastes the result"


def test_prompt_last_step_opens_urls_and_hands_off_flows(capsys, env, frozen_clock):
    [url, _] = prompt(capsys, env, "OPS-12", "https://jira.example.com/browse/{{ticket}}")
    [flow, _] = prompt(capsys, {**env, "flows": "kobold=kb"}, "delany", "{{title}} @kobold")

    assert url["variables"] == {"action": "open"} and url["arg"] == "https://jira.example.com/browse/OPS-12", (
        "a filled URL opens"
    )
    assert flow["variables"] == {"action": "alfred"} and flow["arg"] == "kb delany", "a filled hand-off hands off"


def test_prompt_remembers_paste_requested_before_filling(capsys, env, frozen_clock):
    [typed, _] = prompt(capsys, env, "h", "ssh {{host}}", finish="paste")

    assert typed["variables"] == {"action": "paste"}, "shift-enter on the entry means paste once everything is filled"


def test_prompt_without_candidates_asks_for_a_value(capsys, env, mocker):
    mocker.patch("stash.cli.read_clipboard", return_value="")

    [hint] = prompt(capsys, env, "", "ssh {{host}}")

    assert hint["title"] == "host (1/1)" and hint["valid"] is False, "with nothing to offer the prompt just waits"


def test_prompt_with_everything_filled_finishes(capsys, env, frozen_clock):
    [done] = prompt(capsys, env, "", "ssh {{host}}", '{"host": "h"}')

    assert done["arg"] == "ssh h" and done["variables"] == {"action": "copy"}, "nothing pending means act"


@pytest.mark.parametrize(
    "argv, expected",
    [
        (["ssh {{host}} -p {{port}}", "host=10.0.0.1", "port=22"], "ssh 10.0.0.1 -p 22"),
        (["{{date}} {{time}} {{clipboard}}"], "2026-10-25 12:05 from clipboard"),
        (["ssh {{host=h}} -p {{port}}", "port=1"], "ssh {{host=h}} -p 1"),
        (["plain"], "plain"),
        ([], ""),
    ],
)
def test_fill_prints_the_filled_payload(capsys, env, frozen_clock, argv, expected):
    assert run(capsys, env, "fill", *argv) == expected, "fill should take name=value pairs and resolve reserved names"


def test_search_offers_to_run_a_typed_hand_off_beside_a_match(capsys, env, db_file, frozen_clock):
    db_file.write_text("delany @kobold\n", encoding="utf-8")

    [found, run, addition] = json.loads(run_search(capsys, {**env, "flows": "kobold=kb"}, "delany @kobold"))["items"]

    assert found["title"] == "delany @kobold", "the entry added earlier is the first row, so enter acts on it"
    assert run["title"] == "Run: delany @kobold" and run["arg"] == "kb delany", "running what was typed is next"
    assert addition["title"] == "Add: delany @kobold", "storing it is last"


def test_search_only_adds_a_typed_hand_off_that_matches_nothing(capsys, env, frozen_clock):
    assert item_titles(run_search(capsys, {**env, "flows": "kobold=kb"}, "delany @kobold")) == [
        "Add: delany @kobold"
    ], "new text is added, not run"


def run_search(capsys, env, query):
    return run(capsys, env, "search", query)


DATED = (
    "2026-10-25: zoo visit | plan for the day\n"
    "2026-10-24: visit bank | the bank\n"
    "2026-10-20: visit dentist | last monday\n"
    "visit grandma | evergreen\n"
    "2026-09-30: visit museum | september\n"
    "2025-12-31: visit paris | last year\n"
    "2027-01-10: visit rome | far ahead\n"
    "2026-10-30: visit tax | next friday\n"
    "2026-11-15: visit opera | next month\n"
    "2026-10-26: visit vet | the vet\n"
)


@pytest.fixture
def dated(db_file, grocery, frozen_clock):
    db_file.write_text(DATED, encoding="utf-8")
    grocery.write_text(GROCERY + "2026-10-24: cheese | brie\n", encoding="utf-8")


@pytest.mark.parametrize(
    "query, expected",
    [
        ("today/", ["zoo visit", "visit grandma", "milk eggs", "bread"]),
        ("today/ visit", ["zoo visit", "visit grandma", "Add: visit"]),
        ("today/ zoo", ["zoo visit", "Add: zoo"]),
        ("yesterday/", ["visit bank", "cheese", "visit grandma", "milk eggs", "bread"]),
        ("yesterday/ visit", ["visit bank", "visit grandma", "Add: visit"]),
        ("week/ visit", ["zoo visit", "visit bank", "visit dentist", "visit grandma", "Add: visit"]),
        (
            "month/ visit",
            ["zoo visit", "visit vet", "visit tax", "visit bank", "visit dentist", "visit grandma", "Add: visit"],
        ),
        (
            "quarter/ visit",
            [
                "zoo visit",
                "visit vet",
                "visit tax",
                "visit opera",
                "visit bank",
                "visit dentist",
                "visit grandma",
                "Add: visit",
            ],
        ),
        (
            "year/ visit",
            [
                "zoo visit",
                "visit vet",
                "visit tax",
                "visit opera",
                "visit bank",
                "visit dentist",
                "visit museum",
                "visit grandma",
                "Add: visit",
            ],
        ),
        (
            "decade/ visit",
            [
                "zoo visit",
                "visit vet",
                "visit tax",
                "visit opera",
                "visit rome",
                "visit bank",
                "visit dentist",
                "visit museum",
                "visit paris",
                "visit grandma",
                "Add: visit",
            ],
        ),
        ("tomorrow/ visit", ["visit vet", "visit grandma", "Add: visit"]),
        ("tomorrow/", ["visit vet", "visit grandma", "milk eggs", "bread"]),
        ("next-week/ visit", ["visit vet", "visit tax", "visit grandma", "Add: visit"]),
        ("next-month/ visit", ["visit opera", "visit grandma", "Add: visit"]),
        ("next-quarter/ visit", ["visit rome", "visit grandma", "Add: visit"]),
        ("next-year/ visit", ["visit rome", "visit grandma", "Add: visit"]),
        ("last-week/ visit", ["visit grandma", "Add: visit"]),
        ("last-month/ visit", ["visit museum", "visit grandma", "Add: visit"]),
        ("last-quarter/ visit", ["visit museum", "visit grandma", "Add: visit"]),
        ("last-year/ visit", ["visit paris", "visit grandma", "Add: visit"]),
        ("2026-10-20/", ["visit dentist", "visit grandma", "milk eggs", "bread"]),
        ("2026-10-20/ dentist", ["visit dentist", "Add: dentist"]),
        ("2026-10-21/", ["visit grandma", "milk eggs", "bread"]),
        ("today/ zzz", ["Add: zzz"]),
        ("today/ pasta | 500g", ["Add: pasta"]),
    ],
)
def test_view_search_filters_by_stamp_and_lists_newest_first_then_undated(capsys, env, dated, query, expected):
    assert item_titles(run(capsys, env, "search", query)) == expected, (
        "a view holds the lines stamped inside its calendar window, newest first, then every undated line"
    )


def test_root_search_breaks_ties_by_freshness_and_shows_an_age_word(capsys, env, dated):
    items = json.loads(run(capsys, env, "search", "visit"))["items"]

    assert [item["title"] for item in items] == [
        "zoo visit",
        "visit vet",
        "visit tax",
        "visit grandma",
        "visit opera",
        "visit rome",
        "visit bank",
        "visit dentist",
        "visit museum",
        "visit paris",
        "Add: visit",
    ], "at the root, equal matches rank today, up to next Sunday, undated, later, then the past newest first"
    assert [item["subtitle"] for item in items[:-1]] == [
        "today · plan for the day",
        "2026-10-26 · the vet",
        "2026-10-30 · next friday",
        "evergreen",
        "2026-11-15 · next month",
        "2027-01-10 · far ahead",
        "1d · the bank",
        "5d · last monday",
        "3w · september",
        "9mo · last year",
    ], "a past stamp shows as an age, a future one as its date, an undated line shows neither"


@pytest.mark.parametrize(
    "query, subtitle",
    [
        ("cheese", "grocery · 1d · brie"),
        ("yesterday/ cheese", "grocery · 1d · brie"),
        ("grocery/ cheese", "1d · brie"),
        ("week/ bread", "grocery · sourdough"),
    ],
)
def test_subtitle_shows_stash_then_age_then_payload(capsys, env, dated, query, subtitle):
    [item, _] = json.loads(run(capsys, env, "search", query))["items"]

    assert item["subtitle"] == subtitle, "stash (when not inside it), age (when stamped), payload"


@pytest.mark.parametrize(
    "raw, output, stored",
    [
        ("today/ zoo visit", "Added: zoo visit", "2026-10-25: zoo visit"),
        ("yesterday/ call dentist", "Added: call dentist", "2026-10-24: call dentist"),
        ("2026-10-20/ backdated | x", "Added: backdated", "2026-10-20: backdated | x"),
        ("week/ x", "Added: x", "2026-10-25: x"),
        ("decade/ x", "Added: x", "2026-10-25: x"),
        ("tomorrow/ x", "Added: x", "2026-10-26: x"),
        ("next-week/ x", "Added: x", "2026-10-26: x"),
        ("last-week/ x", "Added: x", "2026-10-12: x"),
        ("next-month/ x", "Added: x", "2026-11-01: x"),
        ("last-month/ x", "Added: x", "2026-09-01: x"),
        ("next-quarter/ x", "Added: x", "2027-01-01: x"),
        ("last-year/ x", "Added: x", "2025-01-01: x"),
        ("2026-10-20: typed | x", "Added: 2026-10-20: typed", "2026-10-25: 2026-10-20: typed | x"),
        ("2026-10-20 great day", "Added: 2026-10-20 great day", "2026-10-25: 2026-10-20 great day"),
    ],
)
def test_add_under_a_view_writes_to_default_with_the_view_date(capsys, env, db_file, frozen_clock, raw, output, stored):
    assert run(capsys, env, "add", raw) == output, "a view is not a stash, so add does not name it"
    assert db_file.read_text(encoding="utf-8").endswith(f"\n{stored}\n"), (
        "the current period stamps today; the shifted views and a date stamp their first day; typed dates are text"
    )


def test_add_under_a_view_never_creates_a_file_named_after_it(capsys, env, db_dir, frozen_clock):
    run(capsys, env, "add", "today/ x")

    assert not (db_dir / "today.txt").exists(), "views are not files"


def test_add_row_under_a_view_carries_the_view_so_add_can_date_it(capsys, env, dated):
    [addition] = json.loads(run(capsys, env, "search", "yesterday/ zzz"))["items"]

    assert addition["arg"] == "yesterday/ zzz", "the add command reads the view prefix and stamps yesterday"
    assert addition["mods"]["cmd"] == {"arg": "1", "subtitle": "Open default/ in your editor"}, (
        "cmd-enter on the add row opens the file the line will land in"
    )


def test_add_row_shows_a_typed_date_as_text(capsys, env, frozen_clock):
    [*_, addition] = json.loads(run(capsys, env, "search", "2026-10-20: typed | x"))["items"]

    assert addition["title"] == "Add: 2026-10-20: typed", "what you type is the label, stamp-shaped or not"


def test_edit_under_a_view_opens_default(mocker, capsys, env, db_file):
    execvp = mocker.patch("stash.cli.os.execvp")

    run(capsys, {**env, "editor": "code -g {file}:{line}"}, "edit", "today/ 3")

    assert execvp.call_args_list == [mocker.call("code", ["code", "-g", f"{db_file}:3"])], (
        "a view has no file of its own; its lines live in default.txt"
    )


@pytest.mark.parametrize(
    "query, expected, subtitle",
    [
        ("tod", ["today/", "Add: tod"], "4 entries · 2026-10-25 · ↩ to browse"),
        ("tom", ["tomorrow/", "Add: tom"], "4 entries · 2026-10-26 · ↩ to browse"),
        ("wee", ["week/", "Add: wee"], "7 entries · 2026-10-19 – 2026-10-25 · ↩ to browse"),
        ("yes", ["yesterday/", "Add: yes"], "5 entries · 2026-10-24 · ↩ to browse"),
        ("next-w", ["next-week/", "Add: next-w"], "5 entries · 2026-10-26 – 2026-11-01 · ↩ to browse"),
    ],
)
def test_a_view_row_appears_when_its_name_is_typed(capsys, env, dated, query, expected, subtitle):
    items = json.loads(run(capsys, env, "search", query))["items"]

    assert [item["title"] for item in items] == expected, "typing part of a view name lists its row like a stash"
    assert items[0]["subtitle"] == subtitle, "the row says how many lines the view holds and which days it spans"
    assert items[0]["autocomplete"] == f"{expected[0]} ", "tab on the row enters the view"


@pytest.mark.parametrize("query", ["", "e", "day", "o"])
def test_view_rows_need_the_start_of_their_name(capsys, stashed_env, dated, query):
    titles = item_titles(run(capsys, stashed_env, "search", query))

    assert not any(title == f"{view}/" for view in VIEWS for title in titles), (
        "seven fixed names would match almost any letter, so a view row needs a prefix, not a fuzzy hit"
    )


@pytest.mark.parametrize("query", ["t", "y", "l", "n", "w"])
def test_view_rows_wait_for_a_second_letter(capsys, env, dated, query):
    titles = item_titles(run(capsys, env, "search", query))

    assert not any(title == f"{view}/" for view in VIEWS for title in titles), (
        "one letter is the start of a search, not of a view name, so entries keep the top of the list"
    )


def test_view_rows_for_every_view_that_starts_with_what_was_typed(capsys, env, dated):
    rows = [title for title in item_titles(run(capsys, env, "search", "ye")) if title.endswith("/")]
    nexts = [title for title in item_titles(run(capsys, env, "search", "next")) if title.endswith("/")]
    narrowed = [title for title in item_titles(run(capsys, env, "search", "next-q")) if title.endswith("/")]

    assert rows == ["yesterday/", "year/"], "every view starting with the letters, in their natural order"
    assert nexts == ["next-week/", "next-month/"], "a family of four shows its first two; one more letter narrows it"
    assert narrowed == ["next-quarter/"], "the dash and a letter reach the rest of the family"


def test_a_file_named_after_a_view_is_shadowed_but_its_lines_are_not_lost(capsys, env, db_dir, dated):
    (db_dir / "today.txt").write_text("shadow | x\n", encoding="utf-8")

    inside = item_titles(run(capsys, env, "search", "today/"))
    typed = item_titles(run(capsys, env, "search", "tod"))

    assert inside[0] == "today.txt is hidden behind the today/ view", "the view says a file is in its way"
    assert "shadow" in inside, "an undated line belongs to every view, so the shadowed line still shows"
    assert item_titles(run(capsys, env, "search", "shadow")) == ["shadow", "Add: shadow"], "a bare st finds it"
    assert typed.count("today/") == 1, "only the view row is offered, not a stash row for the file too"


def test_an_empty_view_says_so(capsys, tmp_path, frozen_clock):
    assert item_titles(run(capsys, {"db_dir": str(tmp_path / "none")}, "search", "today/")) == ["Nothing in today/"], (
        "a view with nothing in it is told apart from a miss"
    )


def test_delete_under_a_view_removes_from_default(capsys, env, db_file, dated):
    assert run(capsys, env, "delete", "today/ 2026-10-25: zoo visit | plan for the day") == (
        "Deleted: 2026-10-25: zoo visit | plan for the day"
    ), "delete matches the stored line, stamp included, in default.txt"
    assert "zoo visit" not in item_titles(run(capsys, env, "search", "today/")), "the line is gone from the view"
