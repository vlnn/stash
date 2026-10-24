"""Regenerates info.plist. Run after changing keywords, variables or wiring: uv run python make_plist.py"""

import plistlib
import uuid

from stash.cli import DEFAULT_DB_FILE, DEFAULT_EDITOR, DEFAULT_MAX_RESULTS

PYTHON = 'exec "${python:-/usr/bin/python3}" -S -X utf8 run.py'
CMD, ALT, SHIFT = 1 << 20, 1 << 19, 1 << 17
SEARCH_KEYWORDS = ("st", "sta", "stash")


def uid(name):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"com.vlnn.stash/{name}")).upper()


COPY, PASTE, EDIT, DELETE, ADD, OPEN, ALFRED, NOTIFY, ROUTE = map(
    uid, ("copy", "paste", "edit", "delete", "add", "open", "alfred", "notify", "route")
)
ROUTES = {"add": (ADD, uid("route-add")), "open": (OPEN, uid("route-open")), "alfred": (ALFRED, uid("route-alfred"))}

README = """Fuzzy keyword search over a plain-text stash you own.

st / sta / stash <words>   search; words match in any order, as whole words, prefixes,
                           substrings or in-word letters (stg → staging)
                           the last result adds what you typed; type | and it becomes the first
                           ↩ copy, or open a URL/path, or hand "text @keyword" to another
                           workflow, or add  ⇧↩ paste  ⌘↩ edit  ⌥↩ delete

Entries are lines of  words | payload ; without a | the whole line is both.
flows: aliases for @words, e.g. "tally=t kobold=kb wisp=l".

Variables: db_file (stash path), editor (command template with {file} and {line}),
max_results, python (interpreter, 3.9+).
"""


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
    link(PASTE, SHIFT, "Paste into the frontmost app"),
    link(EDIT, CMD, "Edit in your editor"),
    link(DELETE, ALT, "Delete this entry"),
]

WORKFLOW = {
    "bundleid": "com.vlnn.stash",
    "category": "Productivity",
    "createdby": "vlnn",
    "description": "Fuzzy keyword search over a plain-text stash",
    "disabled": False,
    "name": "Stash",
    "readme": README,
    "version": "2.2.1",
    "webaddress": "",
    "variables": {
        "db_file": DEFAULT_DB_FILE,
        "editor": DEFAULT_EDITOR,
        "max_results": str(DEFAULT_MAX_RESULTS),
        "python": "/usr/bin/python3",
        "flows": "",
    },
    "variablesdontexport": [],
    "objects": [
        *(search_filter(keyword) for keyword in SEARCH_KEYWORDS),
        ROUTER,
        clipboard(COPY, autopaste=False),
        clipboard(PASTE, autopaste=True),
        run_script(EDIT, "edit"),
        run_script(DELETE, "delete"),
        run_script(ADD, "add"),
        run_script(OPEN, "open"),
        run_script(ALFRED, "alfred"),
        NOTIFICATION,
    ],
    "connections": {
        **{uid(f"search-{keyword}"): SEARCH_LINKS for keyword in SEARCH_KEYWORDS},
        ROUTE: [*(link(target, output_uid=output_uid) for target, output_uid in ROUTES.values()), link(COPY)],
        EDIT: [link(NOTIFY)],
        DELETE: [link(NOTIFY)],
        ADD: [link(NOTIFY)],
        ALFRED: [link(NOTIFY)],
    },
    "uidata": {
        **{uid(f"search-{keyword}"): {"xpos": 40, "ypos": 40 + 130 * index} for index, keyword in enumerate(SEARCH_KEYWORDS)},
        ROUTE: {"xpos": 330, "ypos": 60},
        COPY: {"xpos": 600, "ypos": 40},
        ADD: {"xpos": 600, "ypos": 170},
        OPEN: {"xpos": 600, "ypos": 300},
        ALFRED: {"xpos": 600, "ypos": 430},
        PASTE: {"xpos": 330, "ypos": 300},
        EDIT: {"xpos": 330, "ypos": 430},
        DELETE: {"xpos": 330, "ypos": 560},
        NOTIFY: {"xpos": 870, "ypos": 300},
    },
}

if __name__ == "__main__":
    with open("info.plist", "wb") as file:
        plistlib.dump(WORKFLOW, file, sort_keys=True)
