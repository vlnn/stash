from __future__ import annotations

import os

from .entries import Entry, parse_line

TEXT = {"encoding": "utf-8", "errors": "surrogateescape", "newline": ""}


def read_text(path: str) -> str:
    try:
        with open(path, **TEXT) as file:
            return file.read()
    except FileNotFoundError:
        return ""


def load_entries(path: str) -> list[Entry]:
    parsed = (parse_line(line, number) for number, line in enumerate(read_text(path).split("\n"), start=1))
    return [entry for entry in parsed if entry]


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
    os.replace(temporary, destination)
