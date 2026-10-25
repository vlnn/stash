from __future__ import annotations

import os

from .entries import Entry, is_scope_name, parse_line

TEXT = {"encoding": "utf-8", "errors": "surrogateescape", "newline": ""}
ROOT = "default"
EXTENSION = ".txt"


def scope_path(db_dir: str, scope: str = "") -> str:
    return os.path.join(db_dir, f"{scope or ROOT}{EXTENSION}")


def scope_names(db_dir: str) -> list[str]:
    try:
        names = os.listdir(db_dir)
    except FileNotFoundError:
        return []
    stems = (name[: -len(EXTENSION)] for name in names if name.endswith(EXTENSION))
    return sorted(stem for stem in stems if stem != ROOT and is_scope_name(stem))


def read_text(path: str) -> str:
    try:
        with open(path, **TEXT) as file:
            return file.read()
    except FileNotFoundError:
        return ""


def load_entries(path: str, scope: str = "") -> list[Entry]:
    lines = enumerate(read_text(path).split("\n"), start=1)
    parsed = (parse_line(line, number, scope) for number, line in lines)
    return [entry for entry in parsed if entry]


def load_scope(db_dir: str, scope: str = "") -> list[Entry]:
    return load_entries(scope_path(db_dir, scope), scope)


def load_scopes(db_dir: str) -> dict[str, list[Entry]]:
    return {scope: load_scope(db_dir, scope) for scope in scope_names(db_dir)}


def ensure_parent(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)


def ensure_file(path: str) -> None:
    ensure_parent(path)
    open(path, "a", **TEXT).close()


def append_line(path: str, line: str) -> None:
    existing = read_text(path)
    separator = "\n" if existing and not existing.endswith("\n") else ""
    ensure_parent(path)
    with open(path, "a", **TEXT) as file:
        file.write(f"{separator}{line}\n")


def delete_line(path: str, target: str) -> bool:
    lines = read_text(path).splitlines(keepends=True)
    index = find_line(lines, target)
    if index is None:
        return False
    write_atomically(path, "".join(lines[:index] + lines[index + 1 :]))
    return True


def find_line(lines: list[str], target: str) -> int | None:
    wanted = target.strip()
    return next((index for index, line in enumerate(lines) if line.strip() == wanted), None)


def write_atomically(path: str, text: str) -> None:
    destination = os.path.realpath(path)
    temporary = f"{destination}.tmp"
    with open(temporary, "w", **TEXT) as file:
        file.write(text)
    os.chmod(temporary, os.stat(destination).st_mode)
    os.replace(temporary, destination)
