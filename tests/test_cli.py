import json
import os

import pytest

from alfred_db.cli import DEFAULT_DB_FILE, DEFAULT_EDITOR, DEFAULT_MAX_RESULTS, config_from, editor_argv, main

DATABASE = "ssh prod web | Prod web box | ssh deploy@10.0.1.5\nwifi guest | Guest wifi | hunter2\n"


@pytest.fixture
def db_file(tmp_path):
    path = tmp_path / "entries.txt"
    path.write_text(DATABASE, encoding="utf-8")
    return path


@pytest.fixture
def env(db_file):
    return {"db_file": str(db_file)}


def run(capsys, env, *argv):
    main(list(argv), env)
    return capsys.readouterr().out.strip()


def item_titles(output):
    return [item["title"] for item in json.loads(output)["items"]]


DEFAULTS = (os.path.expanduser(DEFAULT_DB_FILE), DEFAULT_EDITOR, DEFAULT_MAX_RESULTS)


@pytest.mark.parametrize(
    "env, expected",
    [
        ({}, DEFAULTS),
        ({"db_file": "", "editor": "", "max_results": ""}, DEFAULTS),
        (
            {"db_file": "~/db.txt", "editor": "code -g {file}:{line}", "max_results": "9"},
            (os.path.expanduser("~/db.txt"), "code -g {file}:{line}", 9),
        ),
    ],
)
def test_config_from_environment(env, expected):
    assert tuple(config_from(env)) == expected, "config_from should read Alfred workflow variables with defaults"


@pytest.mark.parametrize(
    "argv, expected",
    [
        (["search", "prod"], ["Prod web box"]),
        (["search", "web", "prod"], ["Prod web box"]),
        (["search", ""], ["Prod web box", "Guest wifi"]),
        (["search"], ["Prod web box", "Guest wifi"]),
        (["search", "zzz"], ["No match for 'zzz'"]),
    ],
)
def test_search_prints_alfred_items(capsys, env, argv, expected):
    assert item_titles(run(capsys, env, *argv)) == expected, f"{argv} should print matching Alfred items"


def test_search_limits_results(capsys, env):
    assert len(item_titles(run(capsys, {**env, "max_results": "1"}, "search", ""))) == 1, (
        "search should honour max_results"
    )


def test_search_on_missing_database_explains_how_to_add(capsys, tmp_path):
    output = run(capsys, {"db_file": str(tmp_path / "none.txt")}, "search", "x")

    assert item_titles(output) == ["The database is empty"], "search should guide the user on an empty database"


def test_search_survives_undecodable_bytes(capsys, env, db_file):
    db_file.write_bytes(DATABASE.encode() + b"caf\xe9 | Latin-1 line | x\n")

    assert item_titles(run(capsys, env, "search", "")) == ["Prod web box", "Guest wifi", "Latin-1 line"], (
        "search should still list entries when the file has a non-UTF-8 byte"
    )


def test_preview_prints_single_add_item(capsys, env):
    assert item_titles(run(capsys, env, "preview", "k8s | Kube | kubectl")) == ["Add: Kube"], (
        "preview should show what will be added"
    )


def test_add_appends_entry_and_confirms(capsys, env, db_file):
    output = run(capsys, env, "add", "  k8s ctx | Kube | kubectl ctx  ")

    assert output == "Added: Kube", "add should confirm with the entry title"
    assert db_file.read_text(encoding="utf-8").endswith("\nk8s ctx | Kube | kubectl ctx\n"), (
        "add should append the stripped line to the database"
    )


@pytest.mark.parametrize("raw", ["", "# nope", " | no keywords"])
def test_add_rejects_invalid_entry(capsys, env, db_file, raw):
    output = run(capsys, env, "add", raw)

    assert output.startswith("Nothing added"), "add should explain why nothing was added"
    assert db_file.read_text(encoding="utf-8") == DATABASE, "add should not touch the database on invalid input"


def test_added_entry_is_searchable(capsys, env):
    run(capsys, env, "add", "k8s ctx | Kube | kubectl ctx")

    assert item_titles(run(capsys, env, "search", "kub")) == ["Kube"], "a freshly added entry should be found"


@pytest.mark.parametrize(
    "raw, expected_output, expected_titles",
    [
        ("wifi guest | Guest wifi | hunter2", "Deleted: wifi guest | Guest wifi | hunter2", ["Prod web box"]),
        ("gone | Gone | x", "Not deleted: entry not found, the file may have changed", ["Prod web box", "Guest wifi"]),
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
    execvp = mocker.patch("alfred_db.cli.os.execvp")

    run(capsys, {**env, "editor": "code -g {file}:{line}"}, *argv)

    assert execvp.call_args_list == [mocker.call("code", ["code", "-g", f"{db_file}:{line}"])], (
        "edit should hand the process over to the editor at the requested line"
    )


def test_edit_creates_missing_database(mocker, capsys, tmp_path):
    mocker.patch("alfred_db.cli.os.execvp")
    path = tmp_path / "new" / "entries.txt"

    run(capsys, {"db_file": str(path)}, "edit")

    assert path.is_file(), "edit should create the database so the editor has something to open"


def test_edit_reports_missing_editor(mocker, capsys, env):
    mocker.patch("alfred_db.cli.os.execvp", side_effect=FileNotFoundError)

    output = run(capsys, {**env, "editor": "nosuch {file}"}, "edit")

    assert output == "Editor not found: nosuch (use a full path in the editor variable)", (
        "edit should explain how to fix a missing editor"
    )


@pytest.mark.parametrize("argv", [[], ["unknown"]])
def test_main_rejects_unknown_command(env, argv):
    with pytest.raises(SystemExit) as exit_info:
        main(argv, env)

    assert "usage" in str(exit_info.value), "main should print usage for unknown commands"
