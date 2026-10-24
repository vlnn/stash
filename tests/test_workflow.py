import os
import plistlib
import re

import pytest

from alfred_db.cli import COMMANDS, DEFAULT_DB_FILE, DEFAULT_EDITOR, DEFAULT_MAX_RESULTS

CMD, ALT, SHIFT = 1 << 20, 1 << 19, 1 << 17
PLIST_PATH = os.path.join(os.path.dirname(__file__), os.pardir, "info.plist")


@pytest.fixture(scope="module")
def workflow():
    with open(PLIST_PATH, "rb") as file:
        return plistlib.load(file)


@pytest.fixture(scope="module")
def objects(workflow):
    return {item["uid"]: item for item in workflow["objects"]}


def scripts(objects):
    return [item["config"]["script"] for item in objects.values() if "script" in item["config"]]


def object_with_keyword(objects, keyword):
    return next(item for item in objects.values() if item["config"].get("keyword") == keyword)


def destinations(workflow, objects, source, modifiers=0):
    links = workflow["connections"].get(source["uid"], [])
    return [objects[link["destinationuid"]] for link in links if link["modifiers"] == modifiers]


def test_connections_reference_existing_objects(workflow, objects):
    linked = {uid for uid in workflow["connections"]} | {
        link["destinationuid"] for links in workflow["connections"].values() for link in links
    }

    assert linked <= objects.keys(), "every connection should join objects that exist in the workflow"


def test_every_object_has_editor_position(workflow, objects):
    assert objects.keys() <= workflow["uidata"].keys(), "every object should have a position in Alfred's editor"


def test_scripts_call_known_commands_fast(objects):
    for script in scripts(objects):
        command = re.search(r"run\.py (\S+)", script).group(1)

        assert command in COMMANDS, f"script should call an existing command, got {command!r}"
        assert script.startswith('exec "${python:-/usr/bin/python3}" -S -X utf8 run.py'), (
            "scripts should exec python without site imports to keep keystrokes fast"
        )
        assert '"$1"' in script, "scripts should take the query as a quoted argv argument"


@pytest.mark.parametrize(
    "keyword, argument_type",
    [("db", 1), ("db+", 0), ("dbedit", 2)],
)
def test_keywords_and_argument_rules(objects, keyword, argument_type):
    assert object_with_keyword(objects, keyword)["config"]["argumenttype"] == argument_type, (
        f"{keyword} should have argument type {argument_type} (0 required, 1 optional, 2 none)"
    )


@pytest.mark.parametrize("keyword", ["db", "db+"])
def test_script_filters_own_filtering_and_cancel_stale_runs(objects, keyword):
    config = object_with_keyword(objects, keyword)["config"]

    assert config["alfredfiltersresults"] is False, f"{keyword} should rank results itself"
    assert config["queuemode"] == 2, f"{keyword} should terminate a stale run on each keystroke"
    assert config["queuedelaymode"] == 0, f"{keyword} should run immediately without a delay"
    assert config["scriptargtype"] == 1, f"{keyword} should receive the query via argv"


@pytest.mark.parametrize("modifiers, autopaste", [(0, False), (SHIFT, True)])
def test_search_copies_or_pastes_payload(workflow, objects, modifiers, autopaste):
    [target] = destinations(workflow, objects, object_with_keyword(objects, "db"), modifiers)

    assert target["type"] == "alfred.workflow.output.clipboard", f"modifier {modifiers} should use the clipboard"
    assert target["config"]["autopaste"] is autopaste, f"modifier {modifiers} should set autopaste to {autopaste}"


@pytest.mark.parametrize("modifiers, command", [(CMD, "run.py edit"), (ALT, "run.py delete")])
def test_search_modifiers_run_commands(workflow, objects, modifiers, command):
    [target] = destinations(workflow, objects, object_with_keyword(objects, "db"), modifiers)

    assert command in target["config"]["script"], f"modifier {modifiers} should run {command}"


@pytest.mark.parametrize(
    "keyword, command",
    [("db+", "run.py add"), ("dbedit", "run.py edit")],
)
def test_other_keywords_run_their_command(workflow, objects, keyword, command):
    [target] = destinations(workflow, objects, object_with_keyword(objects, keyword))

    assert command in target["config"]["script"], f"{keyword} should run {command}"


@pytest.mark.parametrize("command", ["add", "delete", "edit"])
def test_command_output_is_shown_as_notification(workflow, objects, command):
    [script] = [item for item in objects.values() if f"run.py {command}" in item["config"].get("script", "")]
    [target] = destinations(workflow, objects, script)

    assert target["type"] == "alfred.workflow.output.notification", f"{command} output should be posted as notification"


@pytest.mark.parametrize(
    "variable, default",
    [
        ("db_file", DEFAULT_DB_FILE),
        ("editor", DEFAULT_EDITOR),
        ("max_results", str(DEFAULT_MAX_RESULTS)),
        ("python", "/usr/bin/python3"),
    ],
)
def test_variables_match_code_defaults(workflow, variable, default):
    assert workflow["variables"][variable] == default, f"workflow variable {variable} should default to {default!r}"
