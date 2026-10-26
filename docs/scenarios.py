"""What the documentation GIFs show: a query typed key by key against docs/stashes, and the result it must land on.

tests/test_scenarios.py asserts the landing; scripts/make_gifs.py draws every keystroke of the way there.
"""

import json
import os
from typing import NamedTuple

from stash import cli

STASHES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stashes")
GIFS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gifs")


class Scenario(NamedTuple):
    name: str
    typed: str
    lands_on: str
    shows: str


SCENARIOS = [
    Scenario("fuzzy-label", "stg k8", "k8s ctx staging kube", "letters in order inside words, in any order"),
    Scenario("payload-fallback", "deploy", "ssh prod web", "a word no label has is looked for in the payload"),
    Scenario("add-with-separator", "logs api | tail -f app.log", "Add: logs api", "typing | offers a new entry"),
    Scenario("stash-prefix", "checklists/ rel", "release checklist", "name/ searches one stash only"),
]


def keystrokes(typed):
    return [typed[:count] for count in range(1, len(typed) + 1)]


def search_items(query):
    config = cli.config_from({"db_dir": STASHES_DIR})
    return json.loads(cli.search_command(query, config))["items"]
