from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from typing import Callable, NamedTuple, Optional

from . import alfred, snippets, store
from .entries import SEPARATOR, Entry, parse_line, split_scope
from .matching import search, search_scopes

DEFAULT_DB_DIR = "~/.config/stash"
DEFAULT_EDITOR = "open -t {file}"
DEFAULT_MAX_RESULTS = 50
DEFAULT_SHOW_SCOPES = False
TRUE = ("1", "true", "yes", "on")
ALFRED_SEARCH = (
    "-e",
    "on run argv",
    "-e",
    'tell application id "com.runningwithcrayons.Alfred" to search (item 1 of argv)',
    "-e",
    "end run",
)


class Prompt(NamedTuple):
    template: str = ""
    values: dict[str, str] = {}
    finish: str = ""


class Config(NamedTuple):
    db_dir: str
    editor: str
    max_results: int
    flows: dict[str, str]
    show_scopes: bool = DEFAULT_SHOW_SCOPES
    prompt: Prompt = Prompt()


def config_from(env: Mapping[str, str]) -> Config:
    return Config(
        db_dir=os.path.expanduser(env.get("db_dir") or DEFAULT_DB_DIR),
        editor=env.get("editor") or DEFAULT_EDITOR,
        max_results=int(env.get("max_results") or DEFAULT_MAX_RESULTS),
        flows=flows_from(env.get("flows") or ""),
        show_scopes=is_true(env.get("show_scopes") or ""),
        prompt=Prompt(env.get("template") or "", json.loads(env.get("filled") or "{}"), env.get("finish") or ""),
    )


def is_true(text: str) -> bool:
    return text.strip().lower() in TRUE


def read_clipboard() -> str:
    try:
        return subprocess.run(["pbpaste"], capture_output=True, text=True).stdout
    except OSError:
        return ""


def reserved_for(texts: Sequence[str]) -> dict[str, str]:
    return snippets.reserved_values(time.localtime(), read_clipboard, tuple(texts))


def clock_values() -> dict[str, str]:
    return snippets.reserved_values(time.localtime(), read_clipboard)


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
    hits = search(words, entries, config.max_results)
    reserved = clock_values()
    matches = [alfred.entry_item(entry, config.flows, scope, reserved) for entry in hits]
    exists = os.path.exists(path)
    hint = alfred.scope_hint(scope, exists)
    return alfred.feedback(matches, query, hint, scope, not exists, reserved, config.flows)


def root_search(words: str, query: str, config: Config) -> list[alfred.Item]:
    root = store.load_scope(config.db_dir)
    scopes = store.load_scopes(config.db_dir)
    scoped = [entry for entries in scopes.values() for entry in entries]
    rows = scope_rows(words, scopes) if config.show_scopes else []
    hits = [*search(words, root, config.max_results), *search(words, scoped, config.max_results)]
    hits = hits[: max(config.max_results - len(rows), 0)]
    reserved = clock_values()
    matches = [*rows, *(alfred.entry_item(entry, config.flows, "", reserved) for entry in hits)]
    hint = alfred.root_hint(not (root or scoped), query)
    return alfred.feedback(matches, query, hint, reserved=reserved, flows=config.flows)


def scope_rows(words: str, scopes: Mapping[str, list[Entry]]) -> list[alfred.Item]:
    return [alfred.scope_item(name, len(scopes[name])) for name in search_scopes(words, list(scopes))]


def prompt_command(query: str, config: Config) -> str:
    template, values, finish = config.prompt
    resolved = snippets.fill(template, reserved_for([template]))
    return alfred.render(alfred.prompt_items(resolved, values, finish, query.strip(), config.flows, read_clipboard))


def resolve_command(query: str, config: Config) -> str:
    template, _, finish = config.prompt
    payload = snippets.fill(template, reserved_for([template]))
    action = finish or alfred.action_of(payload)
    return json.dumps({"alfredworkflow": alfred.routed(payload, action, config.flows)})


def fill_command(arguments: Sequence[str], config: Config) -> str:
    template, *pairs = arguments or [""]
    values = {**reserved_for([template]), **snippets.assignments(pairs)}
    return snippets.fill(template, values)


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


Command = Callable[[Sequence[str], Config], Optional[str]]


def text_command(command: Callable[[str, Config], str | None]) -> Command:
    def run(arguments: Sequence[str], config: Config) -> str | None:
        return command(" ".join(arguments), config)

    return run


COMMANDS: dict[str, Command] = {
    "search": text_command(search_command),
    "add": text_command(add_command),
    "delete": text_command(delete_command),
    "edit": text_command(edit_command),
    "open": text_command(open_command),
    "alfred": text_command(alfred_command),
    "prompt": text_command(prompt_command),
    "resolve": text_command(resolve_command),
    "fill": fill_command,
}

USAGE = f"usage: run.py {{{','.join(COMMANDS)}}} [argument]"


def main(argv: Sequence[str], env: Mapping[str, str]) -> None:
    if not argv or argv[0] not in COMMANDS:
        sys.exit(USAGE)
    command, *arguments = argv
    output = COMMANDS[command](arguments, config_from(env))
    if output is not None:
        print(output)
