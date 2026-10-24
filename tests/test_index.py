import marshal
import os

import pytest

from alfred_db import index as index_module
from alfred_db.index import load_index
from alfred_db.matching import haystack_of

DATABASE = "# my db\nssh prod | Prod | ssh p\n\nwifi | Wifi | pw\n"


@pytest.fixture
def db_file(tmp_path):
    path = tmp_path / "entries.txt"
    path.write_text(DATABASE, encoding="utf-8")
    return path


@pytest.fixture
def cache_dir(tmp_path):
    return str(tmp_path / "cache")


def test_load_index_aligns_haystacks_with_file_lines(db_file, cache_dir):
    loaded = load_index(str(db_file), cache_dir)

    assert loaded.lines == DATABASE.split("\n"), "load_index should keep every file line so indices map to line numbers"
    assert loaded.haystacks == [haystack_of(line) for line in loaded.lines], "load_index should index every line"


@pytest.mark.parametrize("content, has_entries", [(DATABASE, True), ("# only a comment\n", False), ("", False)])
def test_has_entries(db_file, cache_dir, content, has_entries):
    db_file.write_text(content, encoding="utf-8")

    assert load_index(str(db_file), cache_dir).has_entries is has_entries, "has_entries should ignore non-entry lines"


def test_load_index_of_missing_database_is_empty(tmp_path, cache_dir):
    assert load_index(str(tmp_path / "none.txt"), cache_dir).has_entries is False, (
        "load_index should treat a missing database as empty"
    )


def test_load_index_reuses_cache_for_unchanged_file(mocker, db_file, cache_dir):
    first = load_index(str(db_file), cache_dir)
    spy = mocker.spy(index_module, "haystack_of")

    second = load_index(str(db_file), cache_dir)

    assert spy.call_count == 0, "load_index should not rebuild haystacks when the file is unchanged"
    assert second == first, "a cached index should equal a freshly built one"


def test_load_index_rebuilds_after_file_changes(db_file, cache_dir):
    load_index(str(db_file), cache_dir)
    db_file.write_text("k8s | Kube | kubectl\n", encoding="utf-8")

    assert load_index(str(db_file), cache_dir).haystacks[0] == " k8s kube ", "load_index should notice edited content"


def test_load_index_keeps_separate_caches_per_database(tmp_path, cache_dir):
    first, second = tmp_path / "one.txt", tmp_path / "two.txt"
    first.write_text("one | One | 1\n", encoding="utf-8")
    second.write_text("two | Two | 2\n", encoding="utf-8")
    load_index(str(first), cache_dir)

    assert load_index(str(second), cache_dir).haystacks[0] == " two ", "each database should have its own cache"


@pytest.mark.parametrize(
    "garbage",
    [b"", b"not marshal", b"\xe9\x00\x00", marshal.dumps(42), marshal.dumps((1, 2)), marshal.dumps((1, 2, 3))],
)
def test_load_index_survives_corrupt_cache(db_file, cache_dir, garbage):
    load_index(str(db_file), cache_dir)
    for name in os.listdir(cache_dir):
        with open(os.path.join(cache_dir, name), "wb") as file:
            file.write(garbage)

    assert load_index(str(db_file), cache_dir).has_entries, "load_index should rebuild a corrupt cache"


def test_load_index_works_without_writable_cache(db_file, tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("a file where the cache directory should be", encoding="utf-8")

    assert load_index(str(db_file), str(blocker / "cache")).has_entries, (
        "load_index should still search when the cache cannot be written"
    )
