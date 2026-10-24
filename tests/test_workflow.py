import os
import plistlib
import re

import pytest

from alfred_db.cli import COMMANDS, DEFAULT_DB_FILE, DEFAULT_EDITOR, DEFAULT_MAX_RESULTS

PLIST_PATH = os.path.join(os.path.dirname(__file__), os.pardir, "info.plist")


@pytest.fixture(scope="module")
def workflow():
    with open(PLIST_PATH, "rb") as file:
        return plistlib.load(file)


def test_connections_reference_existing_objects(workflow):
    objects = {item["uid"] for item in workflow["objects"]}
    linked = set(workflow["connections"]) | {
        link["destinationuid"] for links in workflow["connections"].values() for link in links
    }

    assert linked <= objects, "every connection should join objects that exist in the workflow"


def test_scripts_call_known_commands_fast(workflow):
    scripts = [item["config"]["script"] for item in workflow["objects"] if "script" in item["config"]]

    for script in scripts:
        command = re.search(r"run\.py (\S+)", script).group(1)

        assert command in COMMANDS, f"script should call an existing command, got {command!r}"
        assert script.startswith('exec "${python:-/usr/bin/python3}" -S -X utf8 run.py'), (
            "scripts should exec python without site imports to keep keystrokes fast"
        )
        assert '"$1"' in script, "scripts should take the query as a quoted argv argument"


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
