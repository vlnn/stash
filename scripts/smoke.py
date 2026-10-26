"""Runs the built bundle the way Alfred would: /usr/bin/python3 scripts/smoke.py dist/Stashes.alfredworkflow [python]"""

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


def fake_pbpaste(directory):
    bin_dir = os.path.join(directory, "bin")
    os.makedirs(bin_dir, exist_ok=True)
    path = os.path.join(bin_dir, "pbpaste")
    with open(path, "w") as file:
        file.write("#!/bin/sh\nprintf pasted\n")
    os.chmod(path, 0o755)
    return f"{bin_dir}:{os.environ.get('PATH', '')}"


def main(bundle_path, python):
    with tempfile.TemporaryDirectory() as directory:
        bundle_dir = os.path.join(directory, "bundle")
        with zipfile.ZipFile(bundle_path) as bundle:
            bundle.extractall(bundle_dir)
        scripts = scripts_of(bundle_dir)
        commands = {"search", "add", "delete", "edit", "open", "alfred", "prompt", "resolve"}
        check(set(scripts) == commands, "the bundle wires every command")
        env = {
            **os.environ,
            "python": python,
            "db_dir": os.path.join(directory, "stash"),
            "editor": "echo opened {file}:{line}",
            "flows": "kobold=kb",
            "show_stashes": "1",
        }
        check(titles(run(bundle_dir, scripts, "search", "", env)) == ["Nothing stashed yet"], "an empty folder says so")
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
        stored = found["mods"]["alt"]["arg"]
        check(stored.startswith("20") and ": logs | " in stored, "lines are stamped")
        check(run(bundle_dir, scripts, "delete", stored, env).startswith("Deleted:"), "delete removes it")
        check(
            titles(run(bundle_dir, scripts, "search", "", env)) == ["ssh prod", "books", "кава coffee"],
            "the rest is intact",
        )
        check(
            run(bundle_dir, scripts, "add", "grocery/ milk eggs | 2L", env) == "Added to grocery/: milk eggs",
            "add into a stash creates it",
        )
        [stash_row, *_] = json.loads(run(bundle_dir, scripts, "search", "", env))["items"]
        check(stash_row["title"] == "grocery/" and stash_row["autocomplete"] == "grocery/ ", "stash rows come first")
        check(
            titles(run(bundle_dir, scripts, "search", "grocery/ mil", env)) == ["milk eggs", "Add: mil"],
            "name/ narrows",
        )
        check(
            run(bundle_dir, scripts, "edit", "grocery/ 1", env).endswith("grocery.txt:1"), "edit opens the stash file"
        )
        run(bundle_dir, scripts, "add", "ssh box | ssh {{user=root}}@{{host}}", env)
        [box, _] = json.loads(run(bundle_dir, scripts, "search", "box", env))["items"]
        check(box["variables"]["action"] == "fill", "an entry with placeholders routes to the prompt")
        step_env = {**env, "template": box["variables"]["template"], "filled": "{}", "finish": ""}
        [default, *_] = json.loads(run(bundle_dir, scripts, "prompt", "", step_env))["items"]
        check(default["variables"]["filled"] == '{"user": "root"}', "the prompt offers the default")
        step_env = {**step_env, "filled": default["variables"]["filled"]}
        [typed, *_] = json.loads(run(bundle_dir, scripts, "prompt", "10.0.0.1", step_env))["items"]
        check(typed["arg"] == "ssh root@10.0.0.1" and typed["variables"] == {"action": "copy"}, "the last step copies")
        run(bundle_dir, scripts, "add", "wrap | echo '{{clipboard}}'", env)
        [wrap, _] = json.loads(run(bundle_dir, scripts, "search", "wrap", env))["items"]
        check(wrap["variables"]["action"] == "resolve" and wrap["arg"] == "", "the clipboard is not read on search")
        resolve_env = {**env, "template": wrap["variables"]["template"], "finish": "", "PATH": fake_pbpaste(directory)}
        resolved = json.loads(run(bundle_dir, scripts, "resolve", "", resolve_env))["alfredworkflow"]
        check(resolved == {"arg": "echo 'pasted'", "variables": {"action": "copy"}}, "resolve fills it on enter")
        unmatched = titles(run(bundle_dir, scripts, "search", "zelazny @kobold", env))
        check(unmatched == ["Add: zelazny @kobold"], "new text is added, not run")
        [found, run_row, _] = json.loads(run(bundle_dir, scripts, "search", "delany @kobold", env))["items"]
        check(found["title"] == "books" and run_row["arg"] == "kb delany", "found through the payload, enter or run")
        check(titles(run(bundle_dir, scripts, "search", "today/", env))[0] == "ssh prod", "today/ holds today's lines")
        check(titles(run(bundle_dir, scripts, "search", "yesterday/ ssh", env)) == ["Add: ssh"], "yesterday/ does not")
        check(run(bundle_dir, scripts, "add", "today/ zoo visit", env) == "Added: zoo visit", "today/ adds to default")
        check(not os.path.exists(os.path.join(env["db_dir"], "today.txt")), "a view never becomes a file")
        [row, *_] = json.loads(run(bundle_dir, scripts, "search", "tod", env))["items"]
        check(row["title"] == "today/" and row["autocomplete"] == "today/ ", "typing a view name lists its row")
        [zoo, *_] = json.loads(run(bundle_dir, scripts, "search", "zoo", env))["items"]
        check(zoo["subtitle"] == "today · Copy", "a dated line says how old it is")
        check(run(bundle_dir, scripts, "add", "tomorrow/ dentist", env) == "Added: dentist", "tomorrow/ adds ahead")
        [planned, *_] = json.loads(run(bundle_dir, scripts, "search", "tomorrow/ dent", env))["items"]
        check(planned["title"] == "dentist" and planned["subtitle"][:2] == "20", "tomorrow/ lists it, dated")
        check(titles(run(bundle_dir, scripts, "search", "today/ dent", env)) == ["Add: dent"], "today/ does not yet")
        check(titles(run(bundle_dir, scripts, "search", "next", env))[0] == "next-week/", "next lists its views")
        check(titles(run(bundle_dir, scripts, "search", "| echo a | wc", env)) == ["Add: echo a | wc"], "| alone adds")
        check(run(bundle_dir, scripts, "add", "| echo a | wc", env) == "Added: echo a | wc", "and stores the pipes")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "/usr/bin/python3")
