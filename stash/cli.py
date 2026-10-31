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

from . import alfred, snippets, store, views
from .entries import SEPARATOR, Entry, parse_text, split_stash, stamped
from .matching import by_freshness, search, search_stashes
from .snippets import Values

DEFAULT_DB_DIR = "~/.config/stash"
DEFAULT_EDITOR = "open -t {file}"
DEFAULT_MAX_RESULTS = 50
DEFAULT_SHOW_STASHES = False
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
    show_stashes: bool = DEFAULT_SHOW_STASHES
    prompt: Prompt = Prompt()


def config_from(env: Mapping[str, str]) -> Config:
    return Config(
        db_dir=os.path.expanduser(env.get("db_dir") or DEFAULT_DB_DIR),
        editor=env.get("editor") or DEFAULT_EDITOR,
        max_results=int(env.get("max_results") or DEFAULT_MAX_RESULTS),
        flows=flows_from(env.get("flows") or ""),
        show_stashes=is_true(env.get("show_stashes") or ""),
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
    stash, rest = split_stash(query)
    words, *_ = SEPARATOR.split(rest, 1)
    query = rest.strip()
    if views.is_view(stash):
        items = view_search(stash, words, query, config)
    elif stash:
        items = stash_search(stash, words, query, config)
    else:
        items = root_search(words, query, config)
    return alfred.render(items)


def now() -> time.struct_time:
    return time.localtime()


def item_of(entry: Entry, within: str, reserved: Values, config: Config, today: time.struct_time) -> alfred.Item:
    age = views.age(entry.date, today) if entry.date else ""
    return alfred.entry_item(entry, config.flows, within, reserved, age)


def stash_search(stash: str, words: str, query: str, config: Config) -> list[alfred.Item]:
    today = now()
    path = store.stash_path(config.db_dir, stash)
    entries = store.load_entries(path, stash)
    hits = search(words, entries, config.max_results, views.horizon_at(today))
    reserved = clock_values()
    matches = [item_of(entry, stash, reserved, config, today) for entry in hits]
    exists = os.path.exists(path)
    hint = alfred.stash_hint(stash, exists)
    return alfred.feedback(matches, query, hint, stash, not exists, reserved, config.flows)


def root_search(words: str, query: str, config: Config) -> list[alfred.Item]:
    today = now()
    horizon = views.horizon_at(today)
    root = store.load_stash(config.db_dir)
    stashes = store.load_stashes(config.db_dir)
    stashed = [entry for entries in stashes.values() for entry in entries]
    rows = stash_rows(words, stashes) if words.strip() or config.show_stashes else []
    rows += view_rows(words, [*root, *stashed], today) if words.strip() else []
    hits = [*search(words, root, config.max_results, horizon), *search(words, stashed, config.max_results, horizon)]
    hits = hits[: max(config.max_results - len(rows), 0)]
    reserved = clock_values()
    matches = [*rows, *(item_of(entry, "", reserved, config, today) for entry in hits)]
    hint = alfred.root_hint(not (root or stashed), query)
    return alfred.feedback(matches, query, hint, reserved=reserved, flows=config.flows)


def view_search(view: str, words: str, query: str, config: Config) -> list[alfred.Item]:
    today = now()
    window = views.window(view, today)
    horizon = views.horizon_at(today, window)
    everything = [*store.load_stash(config.db_dir), *stashed_entries(config.db_dir)]
    admitted = by_freshness([entry for entry in everything if views.admits(window, entry.date)], horizon)
    hits = search(words, admitted, config.max_results, horizon)
    reserved = clock_values()
    matches = [item_of(entry, view, reserved, config, today) for entry in hits]
    hint = alfred.view_hint(view, window)
    items = alfred.feedback(matches, query, hint, view, False, reserved, config.flows)
    shadowed = os.path.exists(store.stash_path(config.db_dir, view))
    return [alfred.shadow_hint(view), *items] if shadowed else items


def stashed_entries(db_dir: str) -> list[Entry]:
    return [entry for entries in store.load_stashes(db_dir).values() for entry in entries]


def stash_rows(words: str, stashes: Mapping[str, list[Entry]]) -> list[alfred.Item]:
    names = [name for name in stashes if not views.is_view(name)]
    return [alfred.stash_item(name, len(stashes[name])) for name in search_stashes(words, names)]


def view_rows(words: str, entries: Sequence[Entry], today: time.struct_time) -> list[alfred.Item]:
    return [view_row(view, entries, today) for view in views.named(words.strip().lower())]


def view_row(view: str, entries: Sequence[Entry], today: time.struct_time) -> alfred.Item:
    window = views.window(view, today)
    count = sum(views.admits(window, entry.date) for entry in entries)
    return alfred.stash_item(view, count, alfred.span_of(window))


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
    stash, line = split_stash(raw)
    entry = parse_text(line)
    if entry is None:
        return f"Nothing added, expected: {alfred.FORMAT_HINT}"
    date = views.stamp_for(stash, now())
    stash = alfred.home(stash)
    store.append_line(store.stash_path(config.db_dir, stash), stamped(date, entry.raw))
    return f"Added to {stash}/: {entry.label}" if stash else f"Added: {entry.label}"


def delete_command(raw: str, config: Config) -> str:
    stash, line = split_stash(raw)
    if store.delete_line(store.stash_path(config.db_dir, alfred.home(stash)), line, views.iso(now())):
        return f"Deleted: {line.strip()}"
    return "Not deleted: entry not found, the file may have changed"


def edit_command(target: str, config: Config) -> str | None:
    stash, line_number = split_stash(target)
    path = store.stash_path(config.db_dir, alfred.home(stash))
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
