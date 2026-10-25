import json
import os

import pytest

from stash.cli import (
    ALFRED_SEARCH,
    DEFAULT_DB_DIR,
    DEFAULT_EDITOR,
    DEFAULT_MAX_RESULTS,
    config_from,
    editor_argv,
    flows_from,
    main,
)

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


def run(capsys, env, *argv):
    main(list(argv), env)
    return capsys.readouterr().out.strip()


def item_titles(output):
    return [item["title"] for item in json.loads(output)["items"]]


DEFAULTS = (os.path.expanduser(DEFAULT_DB_DIR), DEFAULT_EDITOR, DEFAULT_MAX_RESULTS, {})


@pytest.mark.parametrize(
    "env, expected",
    [
        ({}, DEFAULTS),
        ({"db_dir": "", "editor": "", "max_results": "", "flows": ""}, DEFAULTS),
        (
            {"db_dir": "~/db", "editor": "code -g {file}:{line}", "max_results": "9", "flows": "tally=t"},
            (os.path.expanduser("~/db"), "code -g {file}:{line}", 9, {"tally": "t"}),
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
        (["search", "prod | ssh prod"], ["Add: prod", "ssh prod web"]),
        (["search", "prod \\ ssh prod"], ["Add: prod", "ssh prod web"]),
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

    assert item_titles(output) == ["The stash is empty"], "search should guide the user on an empty stash"


def test_search_survives_undecodable_bytes(capsys, env, db_file):
    db_file.write_bytes(DATABASE.encode() + b"caf\xe9 | x\n")

    assert len(item_titles(run(capsys, env, "search", ""))) == 3, (
        "search should still list entries when the file has a non-UTF-8 byte"
    )


def test_add_appends_entry_and_confirms(capsys, env, db_file):
    output = run(capsys, env, "add", "  k8s ctx | kubectl ctx  ")

    assert output == "Added: k8s ctx", "add should confirm with the entry label"
    assert db_file.read_text(encoding="utf-8").endswith("\nk8s ctx | kubectl ctx\n"), (
        "add should append the stripped line to the database"
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
        ("gone | x", "Not deleted: entry not found, the stash may have changed", ["ssh prod web", "wifi guest"]),
    ],
)
def test_delete(capsys, env, raw, expected_output, expected_titles):
    assert run(capsys, env, "delete", raw) == expected_output, "delete should report what happened"
    assert item_titles(run(capsys, env, "search", "")) == expected_titles, "delete should remove only that entry"


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
        ("recipes/", ["New scope recipes/"]),
        ("recipes/ pasta", ["Add: pasta"]),
    ],
)
def test_search_tiers_scopes_root_and_scoped_entries(capsys, env, grocery, query, expected):
    assert item_titles(run(capsys, env, "search", query)) == expected, (
        "scope rows come first, then root entries, then scoped entries; name/ narrows to one scope"
    )


def test_search_marks_scoped_entries_at_the_root_but_not_inside_their_scope(capsys, env, grocery):
    [at_root, _] = json.loads(run(capsys, env, "search", "bread"))["items"]
    [inside, _] = json.loads(run(capsys, env, "search", "grocery/ bread"))["items"]

    assert at_root["subtitle"] == "grocery · sourdough", "a scoped hit at the root should say where it lives"
    assert inside["subtitle"] == "sourdough", "inside its scope an entry looks like any other"


def test_search_counts_scope_rows_against_max_results(capsys, env, grocery):
    assert item_titles(run(capsys, {**env, "max_results": "2"}, "search", "")) == ["grocery/", "ssh prod web"], (
        "max_results should cap the whole list, scope rows included"
    )


def test_search_with_only_scopes_lists_them(capsys, tmp_path):
    (tmp_path / "grocery.txt").write_text(GROCERY, encoding="utf-8")

    assert item_titles(run(capsys, {"db_dir": str(tmp_path)}, "search", "")) == ["grocery/", "milk eggs", "bread"], (
        "a stash with scopes and no default.txt is not empty"
    )


def test_add_into_scope_creates_its_file(capsys, env, db_dir):
    output = run(capsys, env, "add", "recipes/ pasta | 500g, 10 min")

    assert output == "Added to recipes/: pasta", "add should say which scope received the entry"
    assert (db_dir / "recipes.txt").read_text(encoding="utf-8") == "pasta | 500g, 10 min\n", (
        "the first entry of a scope should create its file without the scope prefix"
    )
    assert (db_dir / "default.txt").read_text(encoding="utf-8") == DATABASE, "the root should be untouched"


def test_delete_from_scope(capsys, env, grocery):
    assert run(capsys, env, "delete", "grocery/ bread | sourdough") == "Deleted: bread | sourdough", (
        "delete should remove the line from the scope's file"
    )
    assert grocery.read_text(encoding="utf-8") == "milk eggs | 2L and a dozen\n", "only that line should go"


def test_delete_from_scope_reports_unknown_entry(capsys, env, grocery):
    assert run(capsys, env, "delete", "grocery/ ssh prod web | ssh deploy@10.0.1.5").startswith("Not deleted"), (
        "a root entry is not found in a scope's file"
    )


def test_edit_opens_the_scope_file_at_the_line(mocker, capsys, env, db_dir):
    execvp = mocker.patch("stash.cli.os.execvp")

    run(capsys, {**env, "editor": "code -g {file}:{line}"}, "edit", "recipes/ 4")

    assert execvp.call_args_list == [mocker.call("code", ["code", "-g", f"{db_dir / 'recipes.txt'}:4"])], (
        "edit should open the scope's file"
    )
    assert (db_dir / "recipes.txt").is_file(), "edit should create the scope's file so the editor can open it"


def test_search_in_an_empty_scope_says_so(capsys, env, db_dir):
    (db_dir / "grocery.txt").write_text("# nothing yet\n", encoding="utf-8")

    assert item_titles(run(capsys, env, "search", "grocery/")) == ["grocery/ is empty"], (
        "a scope file without entries should be told apart from a scope that does not exist"
    )
