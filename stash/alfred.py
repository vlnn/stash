from __future__ import annotations

import json
import os
from typing import Any, Optional, Sequence

from .entries import Entry, has_separator, parse_line

Item = dict[str, Any]

FORMAT_HINT = "words | payload"
OPEN_EDITOR = {"arg": "1", "subtitle": "Open the stash in your editor"}
OPENABLE_SCHEMES = ("http://", "https://", "file://", "alfred://")
LABELS = {"copy": "Copy", "open": "Open"}


def action_of(payload: str) -> str:
    if payload.startswith(OPENABLE_SCHEMES) or os.path.exists(os.path.expanduser(payload)):
        return "open"
    return "copy"


def entry_item(entry: Entry) -> Item:
    action = action_of(entry.payload)
    arg = os.path.expanduser(entry.payload) if action == "open" else entry.payload
    return {
        "uid": f"{entry.label}|{entry.payload}",
        "title": entry.label,
        "subtitle": subtitle_of(entry, action),
        "arg": arg,
        "autocomplete": entry.label,
        "variables": {"action": action},
        "text": {"copy": entry.payload, "largetype": entry.payload},
        "mods": {
            "cmd": {"arg": str(entry.line_number), "subtitle": f"Edit line {entry.line_number} of the stash"},
            "alt": {"arg": entry.raw, "subtitle": f"Delete: {entry.raw}"},
            "ctrl": {"valid": False, "subtitle": f"Line {entry.line_number} · {action}"},
        },
    }


def subtitle_of(entry: Entry, action: str) -> str:
    if entry.payload == entry.label:
        return LABELS[action]
    return entry.payload if action == "copy" else f"{LABELS[action]} · {entry.payload}"


def add_item(raw: str) -> Optional[Item]:
    entry = parse_line(raw)
    if entry is None:
        return None
    format_hint = "" if has_separator(raw) else f"   ({FORMAT_HINT})"
    return {
        "title": f"Add: {entry.label}",
        "subtitle": f"{entry.payload}{format_hint}",
        "arg": entry.raw,
        "variables": {"action": "add"},
        "mods": {"cmd": OPEN_EDITOR, "alt": {"valid": False}, "shift": {"valid": False}},
    }


def hint_item(title: str, subtitle: str) -> Item:
    return {"title": title, "subtitle": subtitle, "valid": False, "mods": {"cmd": {**OPEN_EDITOR, "valid": True}}}


def search_feedback(results: Sequence[Entry], entries: Sequence[Entry], query: str) -> list[Item]:
    addition = add_item(query)
    matches = [entry_item(entry) for entry in results]
    if addition is None:
        return matches or [empty_hint(entries, query)]
    if has_separator(query):
        return [addition, *matches]
    return [*matches, addition]


def empty_hint(entries: Sequence[Entry], query: str) -> Item:
    if not entries:
        return hint_item("The stash is empty", f"Type {FORMAT_HINT} and press ↩ to add the first entry")
    return hint_item(f"No match for '{query}'", f"Type {FORMAT_HINT} to add an entry")


def render(items: Sequence[Item]) -> str:
    return json.dumps({"items": list(items)})
