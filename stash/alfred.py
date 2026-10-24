from __future__ import annotations

import json
from typing import Any, Optional, Sequence

from .entries import FIELD_SEPARATOR, Entry, parse_line

Item = dict[str, Any]

FORMAT_HINT = "keywords | title | payload"
OPEN_EDITOR = {"arg": "1", "subtitle": "Open the stash in your editor"}


def entry_item(entry: Entry) -> Item:
    keywords = " ".join(entry.keywords)
    return {
        "uid": f"{keywords}|{entry.title}",
        "title": entry.title,
        "subtitle": entry.payload,
        "arg": entry.payload,
        "autocomplete": keywords,
        "text": {"copy": entry.payload, "largetype": entry.payload},
        "mods": {
            "cmd": {"arg": str(entry.line_number), "subtitle": f"Edit line {entry.line_number} of the stash"},
            "alt": {"arg": entry.raw, "subtitle": f"Delete: {entry.raw}"},
            "ctrl": {"valid": False, "subtitle": f"Keywords: {keywords}"},
        },
    }


def add_item(raw: str) -> Optional[Item]:
    entry = parse_line(raw)
    if entry is None:
        return None
    format_hint = "" if FIELD_SEPARATOR in raw else f"   ({FORMAT_HINT})"
    return {
        "title": f"Add: {entry.title}",
        "subtitle": f"{' '.join(entry.keywords)}  →  {entry.payload}{format_hint}",
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
    if FIELD_SEPARATOR in query:
        return [addition, *matches]
    return [*matches, addition]


def empty_hint(entries: Sequence[Entry], query: str) -> Item:
    if not entries:
        return hint_item("The stash is empty", f"Type {FORMAT_HINT} and press ↩ to add the first entry")
    return hint_item(f"No match for '{query}'", f"Type {FORMAT_HINT} to add an entry")


def render(items: Sequence[Item]) -> str:
    return json.dumps({"items": list(items)})
