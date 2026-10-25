from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping, Sequence
from typing import Any

from .entries import Entry, has_separator, in_scope, parse_line
from .snippets import Clipboard, Values, fill, has_placeholders, pending, placeholders

Item = dict[str, Any]
Flows = Mapping[str, str]
NO_FLOWS: Flows = {}
NO_VALUES: Values = {}

FORMAT_HINT = "words | payload"
FOLDER_ICON = {"type": "filetype", "path": "public.folder"}
OPENABLE_SCHEMES = ("http://", "https://", "file://", "alfred://")
FLOW = re.compile(r"^(?:(?P<text>.*\S)\s+)?@(?P<name>\S+)$")
LABELS = {"copy": "Copy", "open": "Open", "alfred": "Alfred", "paste": "Paste", "fill": "Fill"}
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


def arg_of(payload: str, action: str, flows: Flows) -> str:
    if action == "alfred":
        keyword, text = flow_of(payload, flows)
        return f"{keyword} {text}".rstrip()
    if action == "open":
        return os.path.expanduser(payload)
    return payload


def names_of(payload: str) -> str:
    return ", ".join(placeholder.name for placeholder in placeholders(payload))


def fill_variables(template: str, values: Values, finish: str) -> dict[str, str]:
    return {"action": "fill", "template": template, "filled": json.dumps(values), "finish": finish}


def paste_mod(payload: str) -> Item:
    return {"arg": payload, "variables": {"action": "paste"}, "subtitle": "Paste into the frontmost app"}


def fill_then_paste_mod(template: str, values: Values) -> Item:
    return {"arg": "", "variables": fill_variables(template, values, "paste"), "subtitle": "Fill, then paste"}


def where(scope: str) -> str:
    return f"{scope}/" if scope else "the stash"


def with_origin(origin: str, subtitle: str) -> str:
    return f"{origin} · {subtitle}" if origin else subtitle


def open_editor(scope: str = "") -> Item:
    return {"arg": in_scope(scope, "1"), "subtitle": f"Open {where(scope)} in your editor"}


def entry_item(entry: Entry, flows: Flows = NO_FLOWS, within: str = "", reserved: Values = NO_VALUES) -> Item:
    payload = fill(entry.payload, reserved)
    action = "fill" if has_placeholders(payload) else action_of(payload)
    arg = "" if action == "fill" else arg_of(payload, action, flows)
    origin = entry.scope if entry.scope != within else ""
    line = str(entry.line_number)
    return {
        "uid": in_scope(entry.scope, f"{entry.label}|{entry.payload}"),
        "title": entry.label,
        "subtitle": with_origin(origin, subtitle_of(entry.label, payload, action, arg)),
        "arg": arg,
        "autocomplete": in_scope(entry.scope, entry.label),
        "variables": fill_variables(payload, {}, "") if action == "fill" else {"action": action},
        "text": {"copy": entry.payload, "largetype": payload},
        "mods": {
            "cmd": {"arg": in_scope(entry.scope, line), "subtitle": f"Edit line {line} of {where(entry.scope)}"},
            "alt": {"arg": in_scope(entry.scope, entry.raw), "subtitle": f"Delete: {entry.raw}"},
            "shift": fill_then_paste_mod(payload, {}) if action == "fill" else paste_mod(payload),
            "ctrl": {**INVALID, "subtitle": f"Line {line} of {where(entry.scope)} · {action}"},
        },
    }


def subtitle_of(label: str, payload: str, action: str, arg: str) -> str:
    if action == "alfred":
        return f"{LABELS[action]} · {arg}"
    if action == "fill":
        return f"{LABELS[action]} {names_of(payload)} · {payload}"
    if payload == label:
        return LABELS[action]
    return payload if action == "copy" else f"{LABELS[action]} · {payload}"


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


def add_item(raw: str, scope: str = "", new_scope: bool = False, reserved: Values = NO_VALUES) -> Item | None:
    entry = parse_line(raw)
    if entry is None:
        return None
    format_hint = "" if has_separator(raw) else f"   ({FORMAT_HINT})"
    creation = f" · new scope {scope}/" if new_scope else ""
    return {
        "title": f"Add: {entry.label}",
        "subtitle": f"{fill(entry.payload, reserved)}{format_hint}{creation}",
        "arg": in_scope(scope, entry.raw),
        "variables": {"action": "add"},
        "mods": {"cmd": open_editor(scope), "alt": INVALID, "shift": INVALID},
    }


def hint_item(title: str, subtitle: str, scope: str = "", mods: bool = True) -> Item:
    editor = {"cmd": {**open_editor(scope), "valid": True}} if mods else {}
    return {"title": title, "subtitle": subtitle, **INVALID, "mods": editor}


def root_hint(stash_empty: bool, query: str) -> Item:
    if stash_empty:
        return hint_item("The stash is empty", f"Type {FORMAT_HINT} and press ↩ to add the first entry")
    return hint_item(f"No match for '{query}'", f"Type {FORMAT_HINT} to add an entry")


def scope_hint(scope: str, exists: bool) -> Item:
    if not exists:
        return hint_item(f"New scope {scope}/", f"Type {FORMAT_HINT} to add its first entry", scope)
    return hint_item(f"{scope}/ is empty", f"Type {FORMAT_HINT} to add an entry", scope)


def feedback(
    matches: Sequence[Item],
    query: str,
    hint: Item,
    scope: str = "",
    new_scope: bool = False,
    reserved: Values = NO_VALUES,
) -> list[Item]:
    addition = add_item(query, scope, new_scope, reserved)
    if addition is None:
        return list(matches) or [hint]
    if has_separator(query):
        return [addition, *matches]
    return [*matches, addition]


def prompt_items(
    template: str, values: Values, finish: str, query: str, flows: Flows, clipboard: Clipboard
) -> list[Item]:
    [current, *rest] = pending(template, values) or [None]
    if current is None:
        return [final_item(template, values, finish, flows)]
    step = f"{current.name} ({len(placeholders(template)) - len(rest)}/{len(placeholders(template))})"
    candidates = [(query, "typed"), (current.default, "default"), (clipboard(), "clipboard")]
    rows = [
        prompt_row(step, value, kind, template, {**values, current.name: value}, bool(rest), finish, flows)
        for value, kind in candidates
        if value or (kind == "default" and value is not None)
    ]
    return rows or [hint_item(step, "Type a value", mods=False)]


def prompt_row(
    step: str, value: str, kind: str, template: str, values: Values, more: bool, finish: str, flows: Flows
) -> Item:
    shown = value or "(empty)"
    title = f"{step}: {shown}" if kind == "typed" else f"{step}: {shown}   ({kind})"
    if more:
        return {
            "title": title,
            "subtitle": fill(template, values),
            "arg": "",
            "variables": fill_variables(template, values, finish),
            "mods": {"shift": fill_then_paste_mod(template, values)},
        }
    return {**final_item(template, values, finish, flows), "title": title}


def final_item(template: str, values: Values, finish: str, flows: Flows) -> Item:
    result = fill(template, values)
    action = finish or action_of(result)
    arg = arg_of(result, action, flows)
    return {
        "title": result,
        "subtitle": f"{LABELS[action]} · {arg if action == 'alfred' else result}",
        "arg": arg,
        "variables": {"action": action},
        "text": {"copy": result, "largetype": result},
        "mods": {"shift": paste_mod(result)},
    }


def render(items: Sequence[Item]) -> str:
    return json.dumps({"items": list(items)})
