from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from .entries import Entry, parse_line

Item = dict[str, Any]

FORMAT_HINT = "keywords | title | payload"


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
            "cmd": {"arg": str(entry.line_number), "subtitle": f"Edit line {entry.line_number} of the database"},
            "alt": {"arg": entry.raw, "subtitle": f"Delete: {entry.raw}"},
            "ctrl": {"valid": False, "subtitle": f"Keywords: {keywords}"},
        },
    }


def hint_item(title: str, subtitle: str) -> Item:
    return {"title": title, "subtitle": subtitle, "valid": False}


def search_feedback(results: Sequence[Entry], has_entries: bool, query: str) -> list[Item]:
    if not has_entries:
        return [hint_item("The database is empty", f"Add an entry with: db+ {FORMAT_HINT}")]
    if not results:
        return [hint_item(f"No match for '{query}'", f"Add it with: db+ {query} | title | payload")]
    return [entry_item(entry) for entry in results]


def add_preview_item(raw: str) -> Item:
    entry = parse_line(raw)
    if entry is None:
        return hint_item("Add an entry", f"{FORMAT_HINT}   (title and payload are optional)")
    return {
        "title": f"Add: {entry.title}",
        "subtitle": f"{' '.join(entry.keywords)}  →  {entry.payload}",
        "arg": raw,
    }


def render(items: Sequence[Item], variables: Mapping[str, str]) -> str:
    return json.dumps({"variables": dict(variables), "items": list(items)})
