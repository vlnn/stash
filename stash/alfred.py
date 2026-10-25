from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping, Sequence
from typing import Any

from .entries import Entry, has_separator, in_scope, parse_line
from .snippets import CLIPBOARD, PLACEHOLDER, Clipboard, Values, fill, has_placeholders, mentions, pending, placeholders

Item = dict[str, Any]
Flows = Mapping[str, str]
NO_FLOWS: Flows = {}
NO_VALUES: Values = {}

FORMAT_HINT = "words | payload"
SCOPE_ICON = {"path": "scope.png"}
OPENABLE_SCHEMES = ("http://", "https://", "file://", "alfred://")
TRAILING_FLOW = re.compile(r"^(?:(?P<text>.*\S)\s+)?@(?P<name>\S+)$")
LEADING_FLOW = re.compile(r"^@(?P<name>\S+)(?:\s+(?P<text>\S.*))?$")
LABELS = {"copy": "Copy", "open": "Open", "alfred": "Alfred", "paste": "Paste", "fill": "Fill", "resolve": "Copy"}
INVALID = {"valid": False}


def flow_of(payload: str, flows: Flows) -> tuple[str, str] | None:
    found = TRAILING_FLOW.match(payload) or LEADING_FLOW.match(payload)
    if found is None:
        return None
    name = found.group("name")
    return flows.get(name, name), found.group("text") or ""


def flow_subtitle(payload: str) -> str:
    name, text = flow_of(payload, NO_FLOWS)
    return f"→ {name} · {text}" if text else f"→ {name}"


def is_payload(query: str) -> bool:
    return PLACEHOLDER.search(query) is not None or action_of(query) != "copy"


def action_of(payload: str) -> str:
    if flow_of(payload, NO_FLOWS):
        return "alfred"
    if payload.startswith(OPENABLE_SCHEMES) or is_existing_path(payload):
        return "open"
    return "copy"


def is_existing_path(payload: str) -> bool:
    path = os.path.expanduser(payload)
    return os.path.isabs(path) and os.path.exists(path)


def arg_of(payload: str, action: str, flows: Flows) -> str:
    if action == "alfred":
        keyword, text = flow_of(payload, flows)
        return f"{keyword} {text}".rstrip()
    if action == "open":
        return os.path.expanduser(payload)
    return payload


def names_of(payload: str) -> str:
    return ", ".join(placeholder.name for placeholder in placeholders(payload))


def action_for(payload: str) -> str:
    if has_placeholders(payload):
        return "fill"
    if mentions(payload, CLIPBOARD):
        return "resolve"
    return action_of(payload)


def is_deferred(action: str) -> bool:
    return action in ("fill", "resolve")


def fill_variables(template: str, values: Values, finish: str) -> dict[str, str]:
    return {"action": "fill", "template": template, "filled": json.dumps(values), "finish": finish}


def resolve_variables(template: str, finish: str) -> dict[str, str]:
    return {"action": "resolve", "template": template, "finish": finish}


def deferred_variables(action: str, template: str) -> dict[str, str]:
    return fill_variables(template, {}, "") if action == "fill" else resolve_variables(template, "")


def paste_mod(payload: str) -> Item:
    return {"arg": payload, "variables": {"action": "paste"}, "subtitle": "Paste into the frontmost app"}


def fill_then_paste_mod(template: str, values: Values) -> Item:
    return {"arg": "", "variables": fill_variables(template, values, "paste"), "subtitle": "Fill, then paste"}


def resolve_then_paste_mod(template: str) -> Item:
    return {"arg": "", "variables": resolve_variables(template, "paste"), "subtitle": "Paste into the frontmost app"}


def paste_mod_for(action: str, payload: str) -> Item:
    if action == "fill":
        return fill_then_paste_mod(payload, {})
    if action == "resolve":
        return resolve_then_paste_mod(payload)
    return paste_mod(payload)


def where(scope: str) -> str:
    return f"{scope}/" if scope else "the stash"


def with_origin(origin: str, subtitle: str) -> str:
    return f"{origin} · {subtitle}" if origin else subtitle


def open_editor(scope: str = "") -> Item:
    return {"arg": in_scope(scope, "1"), "subtitle": f"Open {where(scope)} in your editor"}


def entry_item(entry: Entry, flows: Flows = NO_FLOWS, within: str = "", reserved: Values = NO_VALUES) -> Item:
    payload = fill(entry.payload, reserved)
    action = action_for(payload)
    arg = "" if is_deferred(action) else arg_of(payload, action, flows)
    origin = entry.scope if entry.scope != within else ""
    line = str(entry.line_number)
    return {
        "uid": in_scope(entry.scope, f"{entry.label}|{entry.payload}"),
        "title": entry.label,
        "subtitle": with_origin(origin, subtitle_of(entry.label, payload, action, arg)),
        "arg": arg,
        "autocomplete": in_scope(entry.scope, entry.label),
        "variables": deferred_variables(action, payload) if is_deferred(action) else {"action": action},
        "text": {"copy": entry.payload, "largetype": payload},
        "mods": {
            "cmd": {"arg": in_scope(entry.scope, line), "subtitle": f"Edit line {line} of {where(entry.scope)}"},
            "alt": {"arg": in_scope(entry.scope, entry.raw), "subtitle": f"Delete: {entry.raw}"},
            "shift": paste_mod_for(action, payload),
            "ctrl": {**INVALID, "subtitle": f"Line {line} of {where(entry.scope)} · {action_detail(action, arg)}"},
        },
    }


def action_detail(action: str, arg: str) -> str:
    return f"{action}: {arg}" if action == "alfred" else action


def run_item(query: str, flows: Flows, reserved: Values, scope: str = "") -> Item:
    payload = fill(query, reserved)
    action = action_for(payload)
    arg = "" if is_deferred(action) else arg_of(payload, action, flows)
    return {
        "title": f"Run: {query}",
        "subtitle": subtitle_of(query, payload, action, arg),
        "arg": arg,
        "variables": deferred_variables(action, payload) if is_deferred(action) else {"action": action},
        "text": {"copy": payload, "largetype": payload},
        "mods": {
            "cmd": open_editor(scope),
            "alt": INVALID,
            "shift": paste_mod_for(action, payload),
            "ctrl": {**INVALID, "subtitle": f"Not stored · {action_detail(action, arg)}"},
        },
    }


def subtitle_of(label: str, payload: str, action: str, arg: str) -> str:
    if action == "alfred":
        return flow_subtitle(payload)
    if action == "fill":
        return f"{LABELS[action]} {names_of(payload)} · {payload}"
    if payload == label:
        return LABELS[action]
    return payload if action in ("copy", "resolve") else f"{LABELS[action]} · {payload}"


def scope_item(scope: str, count: int) -> Item:
    noun = "entry" if count == 1 else "entries"
    return {
        "title": f"{scope}/",
        "subtitle": f"{count} {noun} · ↩ to browse",
        "autocomplete": f"{scope}/ ",
        "icon": SCOPE_ICON,
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
    flows: Flows = NO_FLOWS,
) -> list[Item]:
    addition = add_item(query, scope, new_scope, reserved)
    if addition is None:
        return list(matches) or [hint]
    if has_separator(query):
        return [addition, *matches]
    run = [run_item(query, flows, reserved, scope)] if matches and is_payload(query) else []
    return [*matches, *run, addition]


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
    return {
        "title": result,
        "subtitle": flow_subtitle(result) if action == "alfred" else f"{LABELS[action]} · {result}",
        "text": {"copy": result, "largetype": result},
        "mods": {"shift": paste_mod(result)},
        **routed(result, action, flows),
    }


def routed(payload: str, action: str, flows: Flows) -> dict[str, Any]:
    return {"arg": arg_of(payload, action, flows), "variables": {"action": action}}


def render(items: Sequence[Item]) -> str:
    return json.dumps({"items": list(items)})
