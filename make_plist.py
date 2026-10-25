"""Regenerates info.plist. Run after changing keywords, variables or wiring: uv run python make_plist.py"""

import plistlib
import uuid

from stash.cli import DEFAULT_DB_DIR, DEFAULT_EDITOR, DEFAULT_MAX_RESULTS, DEFAULT_SHOW_SCOPES

PYTHON = 'exec "${python:-/usr/bin/python3}" -S -X utf8 run.py'
CMD, ALT, CTRL, SHIFT = 1 << 20, 1 << 19, 1 << 18, 1 << 17
HYPER = CMD | ALT | CTRL | SHIFT
KEY_L = 37
SEARCH_KEYWORDS = ("st", "sta", "stash")
HOTKEY_KEYWORD = "stash"


def uid(name):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"com.vlnn.stash/{name}")).upper()


COPY, PASTE, EDIT, DELETE, ADD, OPEN, ALFRED, PROMPT, RESOLVE, NOTIFY, ROUTE, HOTKEY = map(
    uid, ("copy", "paste", "edit", "delete", "add", "open", "alfred", "prompt", "resolve", "notify", "route", "hotkey")
)
ROUTES = {
    "add": (ADD, uid("route-add")),
    "open": (OPEN, uid("route-open")),
    "alfred": (ALFRED, uid("route-alfred")),
    "fill": (PROMPT, uid("route-fill")),
    "resolve": (RESOLVE, uid("route-resolve")),
    "paste": (PASTE, uid("route-paste")),
}

README = """Fuzzy keyword search over a plain-text stash you own.

st / sta / stash <words>   search (or press ⌘⌥⌃⇧L); words match in any order, as whole words, prefixes,
                           substrings or in-word letters (stg → staging)
                           the last result adds what you typed; type | and it becomes the first
                           ↩ copy, or open a URL/path, or hand "text @keyword" to another
                           workflow, or add  ⇧↩ paste  ⌘↩ edit  ⌥↩ delete

Entries are lines of  words | payload ; without a | the whole line is both.
The stash is a folder: default.txt holds the root, every other name.txt is a scope.
st name/ <words>   searches inside a scope; typing part of a name shows its row, ⇥ enters it.
{{name}} in a payload asks for a value on ↩, one prompt per name ({{name=default}}
offers a default, the clipboard is always offered); {{date}}, {{time}} and
{{clipboard}} fill themselves; the clipboard is read on ↩, never while you type.
flows: aliases for @words, e.g. "tally=t kobold=kb wisp=l".

Configure Workflow… sets the stash folder, the editor, the interpreter,
hand-off aliases and the number of results.
"""


def setting(variable, label, default, description, placeholder=""):
    return {
        "type": "textfield",
        "variable": variable,
        "label": label,
        "description": description,
        "config": {"default": default, "placeholder": placeholder or default, "required": False, "trim": True},
    }


SETTINGS = [
    setting(
        "db_dir",
        "Stash folder",
        DEFAULT_DB_DIR,
        "default.txt holds the root entries; every other name.txt in the folder is a scope. ~ is expanded.",
    ),
    setting(
        "editor",
        "Editor",
        DEFAULT_EDITOR,
        "Command run by ⌘↩, with {file} and {line} filled in. Use full paths: Alfred runs with a minimal PATH.",
        "code -g {file}:{line}",
    ),
    setting(
        "python",
        "Python",
        "/usr/bin/python3",
        "Interpreter, 3.9 or newer, as an absolute path (no ~). /usr/bin/python3 comes with the Xcode tools.",
    ),
    setting(
        "flows",
        "Hand-off aliases",
        "",
        "Workflow names for @word hand-offs, as name=keyword pairs: tally=t kobold=kb wisp=l",
        "tally=t kobold=kb",
    ),
    setting(
        "max_results",
        "Max results",
        str(DEFAULT_MAX_RESULTS),
        "How many rows Alfred receives per keystroke, scope rows and Add included.",
    ),
    {
        "type": "checkbox",
        "variable": "show_scopes",
        "label": "List scopes",
        "description": "List every scope on a bare st. Typing part of a scope name shows its row either way.",
        "config": {"default": DEFAULT_SHOW_SCOPES, "required": False},
    },
]


def search_filter(keyword):
    return {
        "type": "alfred.workflow.input.scriptfilter",
        "uid": uid(f"search-{keyword}"),
        "version": 3,
        "config": {
            "alfredfiltersresults": False,
            "alfredfiltersresultsmatchmode": 0,
            "argumenttreatemptyqueryasnil": True,
            "argumenttrimmode": 0,
            "argumenttype": 1,
            "escaping": 102,
            "keyword": keyword,
            "queuedelaycustom": 3,
            "queuedelayimmediatelyinitially": True,
            "queuedelaymode": 0,
            "queuemode": 2,
            "runningsubtext": "Searching…",
            "script": f'{PYTHON} search "$1"',
            "scriptargtype": 1,
            "scriptfile": "",
            "subtext": "Fuzzy search; the last result adds what you typed",
            "title": "Search the stash",
            "type": 0,
            "withspace": True,
        },
    }


HOTKEY_TRIGGER = {
    "type": "alfred.workflow.trigger.hotkey",
    "uid": HOTKEY,
    "version": 2,
    "config": {
        "action": 0,
        "argument": 0,
        "focusedappvariable": False,
        "focusedappvariablename": "",
        "hotkey": KEY_L,
        "hotmod": HYPER,
        "hotstring": "L",
        "leftcursor": False,
        "modsmode": 0,
        "relatedAppsMode": 0,
    },
}


def prompt_filter():
    return {
        "type": "alfred.workflow.input.scriptfilter",
        "uid": PROMPT,
        "version": 3,
        "config": {
            **search_filter("")["config"],
            "script": f'{PYTHON} prompt "$1"',
            "subtext": "Type a value; ↩ takes the selected row",
            "title": "Fill in the blanks",
            "withspace": False,
        },
    }


def run_script(object_uid, command):
    return {
        "type": "alfred.workflow.action.script",
        "uid": object_uid,
        "version": 2,
        "config": {
            "concurrently": False,
            "escaping": 102,
            "script": f'{PYTHON} {command} "$1"',
            "scriptargtype": 1,
            "scriptfile": "",
            "type": 0,
        },
    }


def clipboard(object_uid, autopaste):
    return {
        "type": "alfred.workflow.output.clipboard",
        "uid": object_uid,
        "version": 3,
        "config": {
            "autopaste": autopaste,
            "clipboardtext": "{query}",
            "ignoredynamicplaceholders": True,
            "transient": False,
        },
    }


ROUTER = {
    "type": "alfred.workflow.utility.conditional",
    "uid": ROUTE,
    "version": 1,
    "config": {
        "conditions": [
            {
                "inputstring": "{var:action}",
                "matchcasesensitive": False,
                "matchmode": 0,
                "matchstring": action,
                "outputlabel": action,
                "uid": output_uid,
            }
            for action, (_, output_uid) in ROUTES.items()
        ],
        "elselabel": "copy",
        "hideelse": False,
    },
}

NOTIFICATION = {
    "type": "alfred.workflow.output.notification",
    "uid": NOTIFY,
    "version": 1,
    "config": {
        "lastpathcomponent": False,
        "onlyshowifquerypopulated": True,
        "removeextension": False,
        "text": "{query}",
        "title": "Stash",
    },
}


def link(destination, modifiers=0, subtext="", output_uid=None):
    connection = {"destinationuid": destination, "modifiers": modifiers, "modifiersubtext": subtext, "vitoclose": False}
    if output_uid:
        connection["sourceoutputuid"] = output_uid
    return connection


SEARCH_LINKS = [
    link(ROUTE),
    link(ROUTE, SHIFT, "Paste into the frontmost app"),
    link(EDIT, CMD, "Edit in your editor"),
    link(DELETE, ALT, "Delete this entry"),
]
PROMPT_LINKS = [link(ROUTE), link(ROUTE, SHIFT, "Paste once filled")]

WORKFLOW = {
    "bundleid": "com.vlnn.stash",
    "category": "Productivity",
    "createdby": "vlnn",
    "description": "Fuzzy keyword search over a plain-text stash",
    "disabled": False,
    "name": "Stash",
    "readme": README,
    "version": "3.0.0",
    "webaddress": "",
    "userconfigurationconfig": SETTINGS,
    "variables": {},
    "variablesdontexport": [],
    "objects": [
        HOTKEY_TRIGGER,
        *(search_filter(keyword) for keyword in SEARCH_KEYWORDS),
        prompt_filter(),
        ROUTER,
        clipboard(COPY, autopaste=False),
        clipboard(PASTE, autopaste=True),
        run_script(EDIT, "edit"),
        run_script(DELETE, "delete"),
        run_script(ADD, "add"),
        run_script(OPEN, "open"),
        run_script(ALFRED, "alfred"),
        run_script(RESOLVE, "resolve"),
        NOTIFICATION,
    ],
    "connections": {
        HOTKEY: [link(uid(f"search-{HOTKEY_KEYWORD}"))],
        **{uid(f"search-{keyword}"): SEARCH_LINKS for keyword in SEARCH_KEYWORDS},
        PROMPT: PROMPT_LINKS,
        ROUTE: [*(link(target, output_uid=output_uid) for target, output_uid in ROUTES.values()), link(COPY)],
        EDIT: [link(NOTIFY)],
        DELETE: [link(NOTIFY)],
        ADD: [link(NOTIFY)],
        ALFRED: [link(NOTIFY)],
        RESOLVE: [link(ROUTE)],
    },
    "uidata": {
        HOTKEY: {"xpos": -220, "ypos": 40 + 130 * SEARCH_KEYWORDS.index(HOTKEY_KEYWORD)},
        **{
            uid(f"search-{keyword}"): {"xpos": 40, "ypos": 40 + 130 * index}
            for index, keyword in enumerate(SEARCH_KEYWORDS)
        },
        ROUTE: {"xpos": 330, "ypos": 60},
        COPY: {"xpos": 600, "ypos": 40},
        PASTE: {"xpos": 600, "ypos": 170},
        ADD: {"xpos": 600, "ypos": 300},
        OPEN: {"xpos": 600, "ypos": 430},
        ALFRED: {"xpos": 600, "ypos": 560},
        PROMPT: {"xpos": 600, "ypos": 690},
        RESOLVE: {"xpos": 600, "ypos": 820},
        EDIT: {"xpos": 330, "ypos": 430},
        DELETE: {"xpos": 330, "ypos": 560},
        NOTIFY: {"xpos": 870, "ypos": 430},
    },
}

if __name__ == "__main__":
    with open("info.plist", "wb") as file:
        plistlib.dump(WORKFLOW, file, sort_keys=True)
