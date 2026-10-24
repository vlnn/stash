from __future__ import annotations

import os
import shlex
import sys
from typing import Callable, Mapping, NamedTuple, Optional, Sequence

from . import alfred, store
from .entries import SEPARATOR, parse_line
from .matching import search

DEFAULT_DB_FILE = "~/.config/stash/stash.txt"
DEFAULT_EDITOR = "open -t {file}"
DEFAULT_MAX_RESULTS = 50


class Config(NamedTuple):
    db_file: str
    editor: str
    max_results: int


def config_from(env: Mapping[str, str]) -> Config:
    return Config(
        db_file=os.path.expanduser(env.get("db_file") or DEFAULT_DB_FILE),
        editor=env.get("editor") or DEFAULT_EDITOR,
        max_results=int(env.get("max_results") or DEFAULT_MAX_RESULTS),
    )


def search_command(query: str, config: Config) -> str:
    entries = store.load_entries(config.db_file)
    words, *_ = SEPARATOR.split(query, 1)
    results = search(words, entries, config.max_results)
    return alfred.render(alfred.search_feedback(results, entries, query.strip()))


def add_command(raw: str, config: Config) -> str:
    entry = parse_line(raw)
    if entry is None:
        return f"Nothing added, expected: {alfred.FORMAT_HINT}"
    store.append_line(config.db_file, entry.raw)
    return f"Added: {entry.label}"


def delete_command(raw: str, config: Config) -> str:
    if store.delete_line(config.db_file, raw):
        return f"Deleted: {raw.strip()}"
    return "Not deleted: entry not found, the stash may have changed"


def edit_command(line_number: str, config: Config) -> Optional[str]:
    store.ensure_file(config.db_file)
    argv = editor_argv(config.editor, config.db_file, line_number or "1")
    try:
        os.execvp(argv[0], argv)
    except FileNotFoundError:
        return f"Editor not found: {argv[0]} (use a full path in the editor variable)"
    return None


def open_command(target: str, config: Config) -> None:
    os.execvp("open", ["open", target])


def editor_argv(template: str, file: str, line: str) -> list[str]:
    return [part.replace("{file}", file).replace("{line}", line) for part in shlex.split(template)]


Command = Callable[[str, Config], Optional[str]]

COMMANDS: dict[str, Command] = {
    "search": search_command,
    "add": add_command,
    "delete": delete_command,
    "edit": edit_command,
    "open": open_command,
}

USAGE = f"usage: run.py {{{','.join(COMMANDS)}}} [argument]"


def main(argv: Sequence[str], env: Mapping[str, str]) -> None:
    if not argv or argv[0] not in COMMANDS:
        sys.exit(USAGE)
    command, *arguments = argv
    output = COMMANDS[command](" ".join(arguments), config_from(env))
    if output is not None:
        print(output)
