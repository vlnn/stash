from __future__ import annotations

import os
from typing import Optional

ENCODING = "utf-8"


def read_bytes(path: str) -> bytes:
    try:
        with open(path, "rb") as file:
            return file.read()
    except FileNotFoundError:
        return b""


def read_text(path: str) -> str:
    return read_bytes(path).decode(ENCODING)


def ensure_parent(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)


def ensure_file(path: str) -> None:
    ensure_parent(path)
    open(path, "a", encoding=ENCODING).close()


def append_line(path: str, line: str) -> None:
    existing = read_text(path)
    separator = "\n" if existing and not existing.endswith("\n") else ""
    ensure_parent(path)
    with open(path, "a", encoding=ENCODING) as file:
        file.write(f"{separator}{line}\n")


def delete_line(path: str, target: str) -> bool:
    lines = read_text(path).splitlines(keepends=True)
    index = find_line(lines, target)
    if index is None:
        return False
    write_atomically(path, "".join(lines[:index] + lines[index + 1:]).encode(ENCODING))
    return True


def find_line(lines: list[str], target: str) -> Optional[int]:
    wanted = target.strip()
    return next((index for index, line in enumerate(lines) if line.strip() == wanted), None)


def write_atomically(path: str, data: bytes) -> None:
    destination = os.path.realpath(path)
    temporary = f"{destination}.tmp"
    with open(temporary, "wb") as file:
        file.write(data)
    os.replace(temporary, destination)
