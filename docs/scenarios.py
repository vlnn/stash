"""What the documentation GIFs show: a query typed key by key against docs/stashes, and the result it must land on.

tests/test_scenarios.py asserts the landing; scripts/make_gifs.py draws every keystroke of the way there.
A scenario that depends on the calendar pins its day, so the dated lines in docs/stashes stay where the GIF expects.
"""

import json
import os
import time
from contextlib import contextmanager
from typing import NamedTuple, Optional

from stash import cli

STASHES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stashes")
GIFS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gifs")
DOCS_DAY = "2026-10-26"


class Scenario(NamedTuple):
    name: str
    typed: str
    lands_on: str
    shows: str
    today: Optional[str] = None


SCENARIOS = [
    Scenario("fuzzy-label", "stg k8", "k8s ctx staging kube", "letters in order inside words, in any order"),
    Scenario("dropped-letters", "stgng", "ssh staging web", "dropped letters match; swapped ones would not"),
    Scenario("payload-fallback", "deploy", "ssh prod web", "a word no label has is looked for in the payload"),
    Scenario("add-miss", "uuid gen", "Add: uuid gen", "nothing found: ↩ stores what you typed"),
    Scenario("add-with-separator", "logs api | tail -f app.log", "Add: logs api", "typing | offers a new entry"),
    Scenario("stash-row", "ck", "checklists/", "part of a stash name shows its row; ⇥ enters it"),
    Scenario("stash-prefix", "checklists/ rel", "release checklist", "name/ searches one stash only"),
    Scenario("template", "box", "ssh box", "a payload with {{blanks}} asks for them on ↩"),
    Scenario("hand-off", "algo", "algorithms book", "↩ hands 'algorithms' to the @books workflow"),
    Scenario("run-row", "algorithms @books", "algorithms book", "a typed hand-off gets a Run row, stored nowhere"),
    Scenario("view-today", "today/ visit", "zoo visit", "today/ holds today's lines and the undated ones", DOCS_DAY),
    Scenario("view-tomorrow", "tomorrow/", "visit vet", "tomorrow/ is the plan for tomorrow", DOCS_DAY),
    Scenario("view-week", "week/ visit", "zoo visit", "week/: today, the days ahead, the days gone", DOCS_DAY),
    Scenario("view-row", "nex", "next-week/", "the start of a view name shows its row", DOCS_DAY),
    Scenario("freshness", "visit", "zoo visit", "equal matches: today, the near future, then the rest", DOCS_DAY),
]


def keystrokes(typed):
    return [typed[:count] for count in range(1, len(typed) + 1)]


@contextmanager
def clock_at(day):
    if day is None:
        yield
        return
    frozen = time.strptime(day, "%Y-%m-%d")
    real_now, cli.now = cli.now, lambda: frozen
    try:
        yield
    finally:
        cli.now = real_now


def search_items(query, today=None):
    config = cli.config_from({"db_dir": STASHES_DIR})
    with clock_at(today):
        return json.loads(cli.search_command(query, config))["items"]
