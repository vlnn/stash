from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
from collections.abc import Mapping, Sequence
from typing import Callable, NamedTuple, Optional

from . import alfred, store
from .entries import SEPARATOR, parse_line, split_scope
from .matching import search, search_scopes

DEFAULT_DB_DIR = "~/.config/stash"
DEFAULT_EDITOR = "open -t {file}"
DEFAULT_MAX_RESULTS = 50
ALFRED_SEARCH = (
    "-e",
    "on run argv",
    "-e",
    'tell application id "com.runningwithcrayons.Alfred" to search (item 1 of argv)',
    "-e",
    "end run",
)


class Config(NamedTuple):
    db_dir: str
    editor: str
    max_results: int
    flows: dict[str, str]


def config_from(env: Mapping[str, str]) -> Config:
    return Config(
        db_dir=os.path.expanduser(env.get("db_dir") or DEFAULT_DB_DIR),
        editor=env.get("editor") or DEFAULT_EDITOR,
        max_results=int(env.get("max_results") or DEFAULT_MAX_RESULTS),
        flows=flows_from(env.get("flows") or ""),
    )


FLOW_PAIR = re.compile(r"([^\s=,]+)\s*=\s*([^\s=,]+)")


def flows_from(text: str) -> dict[str, str]:
    return dict(FLOW_PAIR.findall(text))


def search_command(query: str, config: Config) -> str:
    scope, rest = split_scope(query)
    words, *_ = SEPARATOR.split(rest, 1)
    items = scoped_search(scope, words, rest.strip(), config) if scope else root_search(words, rest.strip(), config)
    return alfred.render(items)


def scoped_search(scope: str, words: str, query: str, config: Config) -> list[alfred.Item]:
    path = store.scope_path(config.db_dir, scope)
    entries = store.load_entries(path, scope)
    matches = [alfred.entry_item(entry, config.flows, scope) for entry in search(words, entries, config.max_results)]
    exists = os.path.exists(path)
    return alfred.feedback(matches, query, alfred.scope_hint(scope, exists), scope, new_scope=not exists)


def root_search(words: str, query: str, config: Config) -> list[alfred.Item]:
    root = store.load_scope(config.db_dir)
    scopes = store.load_scopes(config.db_dir)
    scoped = [entry for entries in scopes.values() for entry in entries]
    rows = [alfred.scope_item(name, len(scopes[name])) for name in search_scopes(words, list(scopes))]
    hits = [*search(words, root, config.max_results), *search(words, scoped, config.max_results)]
    matches = [*rows, *(alfred.entry_item(entry, config.flows) for entry in hits)][: config.max_results]
    return alfred.feedback(matches, query, alfred.root_hint(not (root or scoped), query))


def add_command(raw: str, config: Config) -> str:
    scope, line = split_scope(raw)
    entry = parse_line(line)
    if entry is None:
        return f"Nothing added, expected: {alfred.FORMAT_HINT}"
    store.append_line(store.scope_path(config.db_dir, scope), entry.raw)
    return f"Added to {scope}/: {entry.label}" if scope else f"Added: {entry.label}"


def delete_command(raw: str, config: Config) -> str:
    scope, line = split_scope(raw)
    if store.delete_line(store.scope_path(config.db_dir, scope), line):
        return f"Deleted: {line.strip()}"
    return "Not deleted: entry not found, the stash may have changed"


def edit_command(target: str, config: Config) -> str | None:
    scope, line_number = split_scope(target)
    path = store.scope_path(config.db_dir, scope)
    store.ensure_file(path)
    argv = editor_argv(config.editor, path, line_number or "1")
    try:
        os.execvp(argv[0], argv)
    except FileNotFoundError:
        return f"Editor not found: {argv[0]} (use a full path in the editor variable)"
    return None


def open_command(target: str, config: Config) -> None:
    os.execvp("open", ["open", target])


def alfred_command(query: str, config: Config) -> str | None:
    result = subprocess.run(["osascript", *ALFRED_SEARCH, query], capture_output=True, text=True)
    if result.returncode == 0:
        return None
    quoted = query.replace("\\", "\\\\").replace('"', '\\"')
    return (
        "macOS has not let Stash drive Alfred yet. Run this once in Terminal and allow it: "
        f'osascript -e \'tell application id "com.runningwithcrayons.Alfred" to search "{quoted}"\''
    )


def editor_argv(template: str, file: str, line: str) -> list[str]:
    return [part.replace("{file}", file).replace("{line}", line) for part in shlex.split(template)]


Command = Callable[[str, Config], Optional[str]]

COMMANDS: dict[str, Command] = {
    "search": search_command,
    "add": add_command,
    "delete": delete_command,
    "edit": edit_command,
    "open": open_command,
    "alfred": alfred_command,
}

USAGE = f"usage: run.py {{{','.join(COMMANDS)}}} [argument]"


def main(argv: Sequence[str], env: Mapping[str, str]) -> None:
    if not argv or argv[0] not in COMMANDS:
        sys.exit(USAGE)
    command, *arguments = argv
    output = COMMANDS[command](" ".join(arguments), config_from(env))
    if output is not None:
        print(output)
