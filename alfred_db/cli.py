from __future__ import annotations

import os
import shlex
import sys
from typing import Callable, Mapping, NamedTuple, Optional, Sequence

from . import alfred, store
from .entries import parse_line
from .index import load_index
from .matching import search

DEFAULT_DB_FILE = "~/.config/alfred-db/entries.txt"
DEFAULT_EDITOR = "open -t {file}"
DEFAULT_MAX_RESULTS = 50
DEFAULT_CACHE_DIR = "~/.cache/alfred-db"


class Config(NamedTuple):
    db_file: str
    editor: str
    max_results: int
    cache_dir: str


def config_from(env: Mapping[str, str]) -> Config:
    return Config(
        db_file=os.path.expanduser(env.get("db_file") or DEFAULT_DB_FILE),
        editor=env.get("editor") or DEFAULT_EDITOR,
        max_results=int(env.get("max_results") or DEFAULT_MAX_RESULTS),
        cache_dir=os.path.expanduser(env.get("alfred_workflow_cache") or DEFAULT_CACHE_DIR),
    )


def search_command(query: str, config: Config) -> str:
    index = load_index(config.db_file, config.cache_dir)
    positions = search(query, index.haystacks, config.max_results)
    results = [parse_line(index.lines[position], position + 1) for position in positions]
    return alfred.render(alfred.search_feedback(results, index.has_entries, query.strip()))


def preview_command(raw: str, config: Config) -> str:
    return alfred.render([alfred.add_preview_item(raw)])


def add_command(raw: str, config: Config) -> str:
    entry = parse_line(raw)
    if entry is None:
        return f"Nothing added, expected: {alfred.FORMAT_HINT}"
    store.append_line(config.db_file, entry.raw)
    return f"Added: {entry.title}"


def delete_command(raw: str, config: Config) -> str:
    if store.delete_line(config.db_file, raw):
        return f"Deleted: {raw.strip()}"
    return "Not deleted: entry not found, the file may have changed"


def edit_command(line_number: str, config: Config) -> Optional[str]:
    store.ensure_file(config.db_file)
    argv = editor_argv(config.editor, config.db_file, line_number or "1")
    try:
        os.execvp(argv[0], argv)
    except FileNotFoundError:
        return f"Editor not found: {argv[0]} (use a full path in the editor variable)"
    return None


def editor_argv(template: str, file: str, line: str) -> list[str]:
    return [part.format(file=file, line=line) for part in shlex.split(template)]


Command = Callable[[str, Config], Optional[str]]

COMMANDS: dict[str, Command] = {
    "search": search_command,
    "preview": preview_command,
    "add": add_command,
    "delete": delete_command,
    "edit": edit_command,
}

USAGE = f"usage: run.py {{{','.join(COMMANDS)}}} [argument]"


def main(argv: Sequence[str], env: Mapping[str, str]) -> None:
    if not argv or argv[0] not in COMMANDS:
        sys.exit(USAGE)
    command, *arguments = argv
    output = COMMANDS[command](" ".join(arguments), config_from(env))
    if output is not None:
        print(output)
