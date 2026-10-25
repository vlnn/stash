"""Runs the built bundle the way Alfred would: /usr/bin/python3 scripts/smoke.py dist/Stash.alfredworkflow [python]"""

import json
import os
import plistlib
import subprocess
import sys
import tempfile
import zipfile


def scripts_of(bundle_dir):
    with open(os.path.join(bundle_dir, "info.plist"), "rb") as file:
        workflow = plistlib.load(file)
    scripts = {}
    for item in workflow["objects"]:
        script = item["config"].get("script", "")
        if "run.py " in script:
            command = script.split("run.py ")[1].split()[0]
            scripts[command] = script
    return scripts


def run(bundle_dir, scripts, command, argument, env):
    completed = subprocess.run(
        ["bash", "-c", scripts[command], "--", argument],
        cwd=bundle_dir,
        env=env,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        sys.exit(f"{command} {argument!r} failed:\n{completed.stderr}")
    return completed.stdout.strip()


def titles(output):
    return [item["title"] for item in json.loads(output)["items"]]


def check(condition, message):
    if not condition:
        sys.exit(f"smoke test failed: {message}")
    print(f"ok  {message}")


def main(bundle_path, python):
    with tempfile.TemporaryDirectory() as directory:
        bundle_dir = os.path.join(directory, "bundle")
        with zipfile.ZipFile(bundle_path) as bundle:
            bundle.extractall(bundle_dir)
        scripts = scripts_of(bundle_dir)
        check(set(scripts) == {"search", "add", "delete", "edit", "open", "alfred"}, "the bundle wires every command")
        env = {
            **os.environ,
            "python": python,
            "db_dir": os.path.join(directory, "stash"),
            "editor": "echo opened {file}:{line}",
            "flows": "kobold=kb",
        }
        check(titles(run(bundle_dir, scripts, "search", "", env)) == ["The stash is empty"], "an empty stash says so")
        check(
            run(bundle_dir, scripts, "add", "ssh prod | ssh deploy@10.0.1.5", env) == "Added: ssh prod",
            "add stores a line",
        )
        run(bundle_dir, scripts, "add", "logs | tail -f app.log | grep ERROR", env)
        run(bundle_dir, scripts, "add", "books | delany @kobold", env)
        run(bundle_dir, scripts, "add", "кава coffee", env)
        [found, addition] = json.loads(run(bundle_dir, scripts, "search", "logs", env))["items"]
        check(found["arg"] == "tail -f app.log | grep ERROR", "pipes survive in payloads")
        check(addition["title"] == "Add: logs", "the add row follows the matches")
        [hand_off, _] = json.loads(run(bundle_dir, scripts, "search", "books", env))["items"]
        check(hand_off["variables"] == {"action": "alfred"} and hand_off["arg"] == "kb delany", "@word hands off")
        check(titles(run(bundle_dir, scripts, "search", "кав", env))[0] == "кава coffee", "unicode searches")
        check(run(bundle_dir, scripts, "edit", "2", env).endswith("default.txt:2"), "edit opens the editor at the line")
        check(
            run(bundle_dir, scripts, "delete", "logs | tail -f app.log | grep ERROR", env).startswith("Deleted:"),
            "delete removes a line",
        )
        check(
            titles(run(bundle_dir, scripts, "search", "", env)) == ["ssh prod", "books", "кава coffee"],
            "the rest is intact",
        )
        check(
            run(bundle_dir, scripts, "add", "grocery/ milk eggs | 2L", env) == "Added to grocery/: milk eggs",
            "add into a scope creates it",
        )
        [scope_row, *_] = json.loads(run(bundle_dir, scripts, "search", "", env))["items"]
        check(scope_row["title"] == "grocery/" and scope_row["autocomplete"] == "grocery/ ", "scope rows come first")
        check(
            titles(run(bundle_dir, scripts, "search", "grocery/ mil", env)) == ["milk eggs", "Add: mil"],
            "name/ narrows",
        )
        check(
            run(bundle_dir, scripts, "edit", "grocery/ 1", env).endswith("grocery.txt:1"), "edit opens the scope file"
        )


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "/usr/bin/python3")
