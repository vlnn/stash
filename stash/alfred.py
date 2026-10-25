from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping, Sequence
from typing import Any

from .entries import Entry, has_separator, in_scope, parse_line

Item = dict[str, Any]
Flows = Mapping[str, str]
NO_FLOWS: Flows = {}

FORMAT_HINT = "words | payload"
FOLDER_ICON = {"type": "filetype", "path": "public.folder"}
OPENABLE_SCHEMES = ("http://", "https://", "file://", "alfred://")
FLOW = re.compile(r"^(?:(?P<text>.*\S)\s+)?@(?P<name>\S+)$")
LABELS = {"copy": "Copy", "open": "Open", "alfred": "Alfred"}
INVALID = {"valid": False}


def flow_of(payload: str, flows: Flows) -> tuple[str, str] | None:
    found = FLOW.match(payload)
    if found is None:
        return None
    name = found.group("name")
    return flows.get(name, name), found.group("text") or ""


def action_of(payload: str) -> str:
    if flow_of(payload, NO_FLOWS):
        return "alfred"
    if payload.startswith(OPENABLE_SCHEMES) or os.path.exists(os.path.expanduser(payload)):
        return "open"
    return "copy"


def arg_of(entry: Entry, action: str, flows: Flows) -> str:
    if action == "alfred":
        keyword, text = flow_of(entry.payload, flows)
        return f"{keyword} {text}".rstrip()
    if action == "open":
        return os.path.expanduser(entry.payload)
    return entry.payload


def where(scope: str) -> str:
    return f"{scope}/" if scope else "the stash"


def with_origin(origin: str, subtitle: str) -> str:
    return f"{origin} · {subtitle}" if origin else subtitle


def open_editor(scope: str = "") -> Item:
    return {"arg": in_scope(scope, "1"), "subtitle": f"Open {where(scope)} in your editor"}


def entry_item(entry: Entry, flows: Flows = NO_FLOWS, within: str = "") -> Item:
    action = action_of(entry.payload)
    arg = arg_of(entry, action, flows)
    origin = entry.scope if entry.scope != within else ""
    line = str(entry.line_number)
    return {
        "uid": in_scope(entry.scope, f"{entry.label}|{entry.payload}"),
        "title": entry.label,
        "subtitle": with_origin(origin, subtitle_of(entry, action, arg)),
        "arg": arg,
        "autocomplete": in_scope(entry.scope, entry.label),
        "variables": {"action": action},
        "text": {"copy": entry.payload, "largetype": entry.payload},
        "mods": {
            "cmd": {"arg": in_scope(entry.scope, line), "subtitle": f"Edit line {line} of {where(entry.scope)}"},
            "alt": {"arg": in_scope(entry.scope, entry.raw), "subtitle": f"Delete: {entry.raw}"},
            "ctrl": {**INVALID, "subtitle": f"Line {line} of {where(entry.scope)} · {action}"},
        },
    }


def subtitle_of(entry: Entry, action: str, arg: str) -> str:
    if action == "alfred":
        return f"{LABELS[action]} · {arg}"
    if entry.payload == entry.label:
        return LABELS[action]
    return entry.payload if action == "copy" else f"{LABELS[action]} · {entry.payload}"


def scope_item(scope: str, count: int) -> Item:
    noun = "entry" if count == 1 else "entries"
    return {
        "title": f"{scope}/",
        "subtitle": f"{count} {noun} · ↩ to browse",
        "autocomplete": f"{scope}/ ",
        "icon": FOLDER_ICON,
        **INVALID,
        "mods": {"cmd": {**open_editor(scope), "valid": True}, "alt": INVALID, "shift": INVALID},
    }


def add_item(raw: str, scope: str = "", new_scope: bool = False) -> Item | None:
    entry = parse_line(raw)
    if entry is None:
        return None
    format_hint = "" if has_separator(raw) else f"   ({FORMAT_HINT})"
    creation = f" · new scope {scope}/" if new_scope else ""
    return {
        "title": f"Add: {entry.label}",
        "subtitle": f"{entry.payload}{format_hint}{creation}",
        "arg": in_scope(scope, entry.raw),
        "variables": {"action": "add"},
        "mods": {"cmd": open_editor(scope), "alt": INVALID, "shift": INVALID},
    }


def hint_item(title: str, subtitle: str, scope: str = "") -> Item:
    return {"title": title, "subtitle": subtitle, **INVALID, "mods": {"cmd": {**open_editor(scope), "valid": True}}}


def root_hint(stash_empty: bool, query: str) -> Item:
    if stash_empty:
        return hint_item("The stash is empty", f"Type {FORMAT_HINT} and press ↩ to add the first entry")
    return hint_item(f"No match for '{query}'", f"Type {FORMAT_HINT} to add an entry")


def scope_hint(scope: str, exists: bool) -> Item:
    if not exists:
        return hint_item(f"New scope {scope}/", f"Type {FORMAT_HINT} to add its first entry", scope)
    return hint_item(f"{scope}/ is empty", f"Type {FORMAT_HINT} to add an entry", scope)


def feedback(matches: Sequence[Item], query: str, hint: Item, scope: str = "", new_scope: bool = False) -> list[Item]:
    addition = add_item(query, scope, new_scope)
    if addition is None:
        return list(matches) or [hint]
    if has_separator(query):
        return [addition, *matches]
    return [*matches, addition]


def render(items: Sequence[Item]) -> str:
    return json.dumps({"items": list(items)})
