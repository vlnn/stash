import os
import plistlib
import re

import pytest

from stash.cli import COMMANDS, DEFAULT_DB_DIR, DEFAULT_EDITOR, DEFAULT_MAX_RESULTS

CMD, ALT, CTRL, SHIFT = 1 << 20, 1 << 19, 1 << 18, 1 << 17
KEY_L = 37
PLIST_PATH = os.path.join(os.path.dirname(__file__), os.pardir, "info.plist")


@pytest.fixture(scope="module")
def workflow():
    with open(PLIST_PATH, "rb") as file:
        return plistlib.load(file)


@pytest.fixture(scope="module")
def objects(workflow):
    return {item["uid"]: item for item in workflow["objects"]}


@pytest.fixture(scope="module")
def script_filters(objects):
    return [item for item in objects.values() if item["type"] == "alfred.workflow.input.scriptfilter"]


@pytest.fixture(scope="module")
def search_filters(script_filters):
    return [item for item in script_filters if item["config"]["keyword"]]


@pytest.fixture(scope="module")
def prompt_filter(script_filters):
    [item] = [item for item in script_filters if not item["config"]["keyword"]]
    return item


@pytest.fixture(scope="module")
def hotkey(objects):
    [item] = [item for item in objects.values() if item["type"] == "alfred.workflow.trigger.hotkey"]
    return item


@pytest.fixture(scope="module")
def conditional(objects):
    [item] = [item for item in objects.values() if item["type"] == "alfred.workflow.utility.conditional"]
    return item


def destinations(workflow, objects, source, modifiers=0, output_uid=None):
    links = workflow["connections"].get(source["uid"], [])
    return [
        objects[link["destinationuid"]]
        for link in links
        if link["modifiers"] == modifiers and link.get("sourceoutputuid") == output_uid
    ]


def test_connections_reference_existing_objects(workflow, objects):
    linked = set(workflow["connections"]) | {
        link["destinationuid"] for links in workflow["connections"].values() for link in links
    }

    assert linked <= objects.keys(), "every connection should join objects that exist in the workflow"


def test_scripts_call_known_commands_fast(objects):
    scripts = [item["config"]["script"] for item in objects.values() if "script" in item["config"]]

    for script in scripts:
        command = re.search(r"run\.py (\S+)", script).group(1)

        assert command in COMMANDS, f"script should call an existing command, got {command!r}"
        assert script.startswith('exec "${python:-/usr/bin/python3}" -S -X utf8 run.py'), (
            "scripts should exec python without site imports to keep keystrokes fast"
        )
        assert '"$1"' in script, "scripts should take the query as a quoted argv argument"


def test_every_search_keyword_runs_the_same_search(search_filters):
    assert {item["config"]["keyword"] for item in search_filters} == {"st", "sta", "stash"}, (
        "st, sta and stash should all open the stash"
    )
    assert {item["config"]["script"] for item in search_filters} == {
        'exec "${python:-/usr/bin/python3}" -S -X utf8 run.py search "$1"'
    }, "every search keyword should run the same search script"


def test_hyper_l_opens_the_stash(workflow, objects, hotkey):
    [target] = destinations(workflow, objects, hotkey)

    assert (hotkey["config"]["hotkey"], hotkey["config"]["hotmod"]) == (KEY_L, CMD | ALT | CTRL | SHIFT), (
        "the hotkey should be hyper (⌘⌥⌃⇧) + l"
    )
    assert hotkey["config"]["argument"] == 0, "the hotkey passes no argument, so Alfred opens the stash empty"
    assert target["config"]["keyword"] == "stash", "the hotkey should open the stash keyword"


def test_search_filters_rank_themselves_and_cancel_stale_runs(script_filters):
    for item in script_filters:
        config = item["config"]

        assert config["alfredfiltersresults"] is False, "the script ranks results itself"
        assert config["queuemode"] == 2, "a stale run should be terminated on each keystroke"
        assert config["argumenttype"] == 1, "the argument is optional so a bare keyword browses the stash"


@pytest.mark.parametrize(
    "modifiers, expected_type, detail",
    [
        (0, "alfred.workflow.utility.conditional", None),
        (SHIFT, "alfred.workflow.utility.conditional", None),
        (CMD, "alfred.workflow.action.script", ("script", "run.py edit")),
        (ALT, "alfred.workflow.action.script", ("script", "run.py delete")),
    ],
)
def test_every_search_keyword_shares_the_actions(workflow, objects, search_filters, modifiers, expected_type, detail):
    for item in search_filters:
        [target] = destinations(workflow, objects, item, modifiers)

        assert target["type"] == expected_type, f"modifier {modifiers} should lead to {expected_type}"
        if detail:
            key, expected = detail
            assert expected == target["config"][key] or expected in target["config"][key], (
                f"modifier {modifiers} should configure {key} as {expected!r}"
            )


@pytest.mark.parametrize(
    "action, command",
    [
        ("add", "run.py add"),
        ("open", "run.py open"),
        ("alfred", "run.py alfred"),
        ("fill", "run.py prompt"),
        ("resolve", "run.py resolve"),
    ],
)
def test_conditional_routes_actions_to_their_scripts(workflow, objects, conditional, action, command):
    [condition] = [c for c in conditional["config"]["conditions"] if c["matchstring"] == action]
    [target] = destinations(workflow, objects, conditional, output_uid=condition["uid"])

    assert condition["inputstring"] == "{var:action}", "the conditional should test the action variable items set"
    assert command in target["config"]["script"], f"the {action} branch should run {command}"


def test_conditional_routes_paste_to_autopaste(workflow, objects, conditional):
    [condition] = [c for c in conditional["config"]["conditions"] if c["matchstring"] == "paste"]
    [target] = destinations(workflow, objects, conditional, output_uid=condition["uid"])

    assert target["type"] == "alfred.workflow.output.clipboard" and target["config"]["autopaste"] is True, (
        "the paste branch should copy and paste"
    )


def test_prompt_filter_feeds_the_router_on_every_step(workflow, objects, prompt_filter, conditional):
    assert 'run.py prompt "$1"' in prompt_filter["config"]["script"], "the prompt is a script filter without keyword"
    assert destinations(workflow, objects, prompt_filter) == [conditional], "enter on a prompt row goes to the router"
    assert destinations(workflow, objects, prompt_filter, SHIFT) == [conditional], "so does shift-enter"


def test_resolve_feeds_its_result_back_into_the_router(workflow, objects, conditional):
    [script] = [item for item in objects.values() if "run.py resolve" in item["config"].get("script", "")]

    assert destinations(workflow, objects, script) == [conditional], (
        "resolve fills the clipboard and lets the router copy, paste, open or hand off the result"
    )


def test_conditional_copies_everything_else(workflow, objects, conditional):
    [else_target] = destinations(workflow, objects, conditional)

    assert else_target["type"] == "alfred.workflow.output.clipboard", "everything else should copy the payload"
    assert else_target["config"]["autopaste"] is False, "plain enter copies without pasting"


@pytest.mark.parametrize("command", ["add", "delete", "edit", "alfred"])
def test_command_output_is_shown_as_notification(workflow, objects, command):
    [script] = [item for item in objects.values() if f"run.py {command}" in item["config"].get("script", "")]
    [target] = destinations(workflow, objects, script)

    assert target["type"] == "alfred.workflow.output.notification", f"{command} output should be posted as notification"


@pytest.fixture(scope="module")
def settings(workflow):
    return {item["variable"]: item for item in workflow["userconfigurationconfig"]}


@pytest.mark.parametrize(
    "variable, default",
    [
        ("db_dir", DEFAULT_DB_DIR),
        ("editor", DEFAULT_EDITOR),
        ("max_results", str(DEFAULT_MAX_RESULTS)),
        ("python", "/usr/bin/python3"),
        ("flows", ""),
        ("show_scopes", False),
    ],
)
def test_settings_match_code_defaults(settings, variable, default):
    assert settings[variable]["config"]["default"] == default, f"setting {variable} should default to {default!r}"


def test_settings_are_editable_fields_with_help(settings):
    for item in settings.values():
        assert item["type"] in ("textfield", "checkbox"), "every setting is a field Configure Workflow… can show"
        assert item["label"] and item["description"], "every setting explains itself in the configuration sheet"
        assert item["config"]["required"] is False, "every setting has a working default"


def test_scope_icon_ships_with_the_workflow():
    assert os.path.isfile(os.path.join(os.path.dirname(PLIST_PATH), "scope.png")), "scope rows need their icon"


def test_no_plain_variables_shadow_the_settings(workflow):
    assert workflow["variables"] == {}, "values live in user configuration only, so there is one place to edit them"
