import os

import pytest

from alfred_db.store import append_line, delete_line, ensure_file, read_bytes


@pytest.fixture
def db_file(tmp_path):
    return tmp_path / "entries.txt"


def write(path, text):
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_read_bytes_returns_nothing_for_missing_file(db_file):
    assert read_bytes(str(db_file)) == b"", "read_bytes should treat a missing file as an empty database"


def test_read_bytes_returns_raw_content(db_file):
    path = write(db_file, "кава café | Кава ☕ | flat white\n")

    assert read_bytes(path).decode("utf-8") == "кава café | Кава ☕ | flat white\n", "read_bytes should keep UTF-8 intact"


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
def test_delete_line_removes_first_matching_line(db_file, target):
    path = write(db_file, "# keep\na | A | 1\n  b | B | 2\nc | C | 3\nb | B | 2\n")

    assert delete_line(path, target) is True, "delete_line should report a successful deletion"
    assert db_file.read_text(encoding="utf-8") == "# keep\na | A | 1\nc | C | 3\nb | B | 2\n", (
        "delete_line should remove only the first matching line and keep everything else"
    )


def test_delete_line_leaves_file_untouched_when_missing_target(db_file):
    path = write(db_file, "a | A | 1\n")

    assert delete_line(path, "zzz") is False, "delete_line should report that nothing matched"
    assert db_file.read_text(encoding="utf-8") == "a | A | 1\n", "delete_line should not change the file"


def test_delete_line_on_missing_file_reports_nothing_deleted(db_file):
    assert delete_line(str(db_file), "a") is False, "delete_line should handle a missing database"


def test_delete_line_preserves_symlinked_database(tmp_path):
    real = tmp_path / "synced" / "entries.txt"
    real.parent.mkdir()
    write(real, "a | A | 1\nb | B | 2\n")
    link = tmp_path / "entries.txt"
    link.symlink_to(real)

    delete_line(str(link), "a | A | 1")

    assert link.is_symlink(), "delete_line should keep the symlink instead of replacing it with a file"
    assert real.read_text(encoding="utf-8") == "b | B | 2\n", "delete_line should edit the symlink target"


def test_ensure_file_creates_empty_database(tmp_path):
    path = str(tmp_path / "new" / "entries.txt")

    ensure_file(path)

    assert os.path.isfile(path), "ensure_file should create the database so an editor can open it"


def test_ensure_file_keeps_existing_content(db_file):
    path = write(db_file, "a | A | 1\n")

    ensure_file(path)

    assert db_file.read_text(encoding="utf-8") == "a | A | 1\n", "ensure_file should never truncate the database"


MIXED_ENCODING = "good | Good | 1\n".encode() + b"caf\xe9 latin1 | Bad byte | 2\n" + "last | Last | 3\n".encode()


def test_delete_line_preserves_undecodable_bytes(db_file):
    db_file.write_bytes(MIXED_ENCODING)

    assert delete_line(str(db_file), "last | Last | 3") is True, "delete_line should work in a file with stray bytes"
    assert db_file.read_bytes() == b"good | Good | 1\ncaf\xe9 latin1 | Bad byte | 2\n", (
        "delete_line should write undecodable bytes back exactly as they were"
    )


def test_append_line_after_undecodable_bytes(db_file):
    db_file.write_bytes(b"caf\xe9 | x | y")

    append_line(str(db_file), "new | New | 1")

    assert db_file.read_bytes() == b"caf\xe9 | x | y\nnew | New | 1\n", "append_line should not choke on stray bytes"
