import os
import stat

import pytest

from stash.store import (
    append_line,
    delete_line,
    ensure_file,
    load_entries,
    load_stash,
    load_stashes,
    read_text,
    stash_names,
    stash_path,
)


@pytest.fixture
def db_file(tmp_path):
    return tmp_path / "entries.txt"


DAY = "2026-10-25"


def write(path, text):
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_read_text_returns_nothing_for_missing_file(db_file):
    assert read_text(str(db_file)) == "", "read_text should treat a missing file as an empty database"


def test_read_text_reads_unicode(db_file):
    path = write(db_file, "кава café | Кава ☕ | flat white\n")

    assert read_text(path) == "кава café | Кава ☕ | flat white\n", "read_text should read the file as UTF-8"


def test_load_entries_skips_comments_and_keeps_line_numbers(db_file):
    path = write(db_file, "# my db\n\nssh prod | ssh p\nwifi | pw\n")

    entries = load_entries(path)

    assert [entry.label for entry in entries] == ["ssh prod", "wifi"], "load_entries should skip comments and blanks"
    assert [entry.line_number for entry in entries] == [3, 4], "load_entries should number lines as in the editor"


def test_load_entries_of_missing_file_is_empty(db_file):
    assert load_entries(str(db_file)) == [], "load_entries should treat a missing database as empty"


def test_append_line_creates_missing_directories(tmp_path):
    path = str(tmp_path / "nested" / "dir" / "entries.txt")

    append_line(path, "a | b | c")

    assert open(path, encoding="utf-8").read() == "a | b | c\n", "append_line should create the file and its parents"


@pytest.mark.parametrize(
    "existing, expected",
    [
        ("", "new\n"),
        ("old\n", "old\nnew\n"),
        ("old", "old\nnew\n"),
    ],
)
def test_append_line_keeps_one_entry_per_line(db_file, existing, expected):
    path = write(db_file, existing)

    append_line(path, "new")

    assert db_file.read_text(encoding="utf-8") == expected, "append_line should never glue entries together"


@pytest.mark.parametrize(
    "target",
    ["b | B | 2", "  b | B | 2  "],
)
def test_delete_line_comments_out_first_matching_line(db_file, target):
    path = write(db_file, "# keep\na | A | 1\n  b | B | 2\nc | C | 3\nb | B | 2\n")

    assert delete_line(path, target, DAY) is True, "delete_line should report a successful deletion"
    assert db_file.read_text(encoding="utf-8") == (
        "# keep\na | A | 1\n# deleted 2026-10-25:   b | B | 2\nc | C | 3\nb | B | 2\n"
    ), "delete_line should comment out only the first matching line, verbatim, and keep everything else"


def test_a_deleted_line_is_not_loaded_and_not_deleted_again(db_file):
    path = write(db_file, "a | A | 1\nb | B | 2\n")

    delete_line(path, "a | A | 1", DAY)

    assert [entry.label for entry in load_entries(path)] == ["b"], "a commented-out line is gone from search"
    assert delete_line(path, "a | A | 1", DAY) is False, "the comment is not the entry, so there is nothing to delete"
    assert db_file.read_text(encoding="utf-8").count("deleted") == 1, "delete_line should not stack comments"


def test_delete_line_leaves_file_untouched_when_missing_target(db_file):
    path = write(db_file, "a | A | 1\n")

    assert delete_line(path, "zzz", DAY) is False, "delete_line should report that nothing matched"
    assert db_file.read_text(encoding="utf-8") == "a | A | 1\n", "delete_line should not change the file"


def test_delete_line_on_missing_file_reports_nothing_deleted(db_file):
    assert delete_line(str(db_file), "a", DAY) is False, "delete_line should handle a missing database"


def test_delete_line_preserves_symlinked_database(tmp_path):
    real = tmp_path / "synced" / "entries.txt"
    real.parent.mkdir()
    write(real, "a | A | 1\nb | B | 2\n")
    link = tmp_path / "entries.txt"
    link.symlink_to(real)

    delete_line(str(link), "a | A | 1", DAY)

    assert link.is_symlink(), "delete_line should keep the symlink instead of replacing it with a file"
    assert real.read_text(encoding="utf-8") == "# deleted 2026-10-25: a | A | 1\nb | B | 2\n", (
        "delete_line should edit the symlink target"
    )


def test_delete_line_keeps_file_mode(db_file):
    path = write(db_file, "a | A | 1\nb | B | 2\n")
    os.chmod(path, 0o600)

    delete_line(path, "a | A | 1", DAY)

    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600, "delete_line should keep the permissions of a private stash"


def test_delete_line_keeps_windows_line_endings(db_file):
    db_file.write_bytes(b"a | A | 1\r\nb | B | 2\r\n")

    delete_line(str(db_file), "a | A | 1", DAY)

    assert db_file.read_bytes() == b"# deleted 2026-10-25: a | A | 1\r\nb | B | 2\r\n", (
        "delete_line should not translate line endings"
    )


def test_ensure_file_creates_empty_database(tmp_path):
    path = str(tmp_path / "new" / "entries.txt")

    ensure_file(path)

    assert os.path.isfile(path), "ensure_file should create the database so an editor can open it"


def test_ensure_file_keeps_existing_content(db_file):
    path = write(db_file, "a | A | 1\n")

    ensure_file(path)

    assert db_file.read_text(encoding="utf-8") == "a | A | 1\n", "ensure_file should never truncate the database"


MIXED_ENCODING = b"good | 1\n" + b"caf\xe9 latin1 | 2\n" + b"last | 3\n"


def test_load_entries_tolerates_undecodable_bytes(db_file):
    db_file.write_bytes(MIXED_ENCODING)

    assert [entry.payload for entry in load_entries(str(db_file))] == ["1", "2", "3"], (
        "load_entries should read every line despite a stray non-UTF-8 byte"
    )


def test_delete_line_preserves_undecodable_bytes(db_file):
    db_file.write_bytes(MIXED_ENCODING)

    assert delete_line(str(db_file), "last | 3", DAY) is True, "delete_line should work in a file with stray bytes"
    assert db_file.read_bytes() == b"good | 1\ncaf\xe9 latin1 | 2\n# deleted 2026-10-25: last | 3\n", (
        "delete_line should write undecodable bytes back exactly as they were"
    )


def test_append_line_after_undecodable_bytes(db_file):
    db_file.write_bytes(b"caf\xe9 | x")

    append_line(str(db_file), "new | 1")

    assert db_file.read_bytes() == b"caf\xe9 | x\nnew | 1\n", "append_line should not choke on stray bytes"


@pytest.mark.parametrize("stash, name", [("", "default.txt"), ("grocery", "grocery.txt")])
def test_stash_path_names_the_file_after_the_stash(tmp_path, stash, name):
    assert stash_path(str(tmp_path), stash) == str(tmp_path / name), "the root is default.txt, a stash its own file"


def test_stash_names_lists_text_files_that_can_be_typed(tmp_path):
    for name in ("default.txt", "zsh.txt", "grocery.txt", "my notes.txt", ".hidden.txt", "notes.md", "grocery.txt.tmp"):
        (tmp_path / name).write_text("x | y\n", encoding="utf-8")

    assert stash_names(str(tmp_path)) == ["grocery", "zsh"], (
        "stashes are the .txt files next to default.txt whose names fit name/, sorted"
    )


def test_stash_names_of_missing_directory_is_empty(tmp_path):
    assert stash_names(str(tmp_path / "none")) == [], "a stash that does not exist yet has no stashes"


def test_load_stash_tags_entries_and_load_stashs_collects_them(tmp_path):
    (tmp_path / "default.txt").write_text("ssh | s\n", encoding="utf-8")
    (tmp_path / "grocery.txt").write_text("# list\nmilk | 2L\neggs | 12\n", encoding="utf-8")

    root = load_stash(str(tmp_path))
    stashes = load_stashes(str(tmp_path))

    assert [(entry.label, entry.stash) for entry in root] == [("ssh", "")], "default.txt loads with an empty stash name"
    assert {name: [entry.label for entry in entries] for name, entries in stashes.items()} == {
        "grocery": ["milk", "eggs"]
    }, "load_stashes should map every stash to its entries"
    assert [(entry.stash, entry.line_number) for entry in stashes["grocery"]] == [("grocery", 2), ("grocery", 3)], (
        "stashed entries should know their stash and their line in its file"
    )
