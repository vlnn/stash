import time

import pytest

from docs.scenarios import SCENARIOS, clock_at, keystrokes, search_items
from stash import cli


def titles(query, today=None):
    return [item["title"] for item in search_items(query, today)]


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda scenario: scenario.name)
def test_typing_lands_on_expected_entry(scenario):
    assert titles(scenario.typed, scenario.today)[0] == scenario.lands_on, (
        f"typing {scenario.typed!r} should put {scenario.lands_on!r} first"
    )


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda scenario: scenario.name)
def test_every_keystroke_has_something_to_show(scenario):
    for query in keystrokes(scenario.typed):
        assert titles(query, scenario.today), (
            f"typing {query!r} on the way to {scenario.typed!r} should show at least one row"
        )


@pytest.mark.parametrize(
    "typed, expected",
    [
        ("a", ["a"]),
        ("st", ["s", "st"]),
        ("k8 p", ["k", "k8", "k8 ", "k8 p"]),
    ],
)
def test_keystrokes_are_every_prefix_in_order(typed, expected):
    assert keystrokes(typed) == expected, f"keystrokes of {typed!r} should be each prefix, shortest first"


def test_scenario_names_are_unique_file_names():
    names = [scenario.name for scenario in SCENARIOS]

    assert len(names) == len(set(names)), "every scenario should get its own gif"
    assert all(name.replace("-", "").isalnum() for name in names), "scenario names should be safe file names"


def test_clock_at_freezes_the_day_for_the_tool():
    with clock_at("2026-10-26"):
        assert time.strftime("%Y-%m-%d", cli.now()) == "2026-10-26", "inside clock_at the tool should see that day"


def test_clock_at_restores_the_clock_afterwards():
    before = cli.now

    with clock_at("2026-10-26"):
        pass

    assert cli.now is before, "leaving clock_at should hand the real clock back"


def test_clock_at_none_leaves_the_clock_alone():
    before = cli.now

    with clock_at(None):
        assert cli.now is before, "an undated scenario should run on the real clock"


@pytest.mark.parametrize(
    "query, today, expected_first",
    [
        ("today/ visit", "2026-10-26", "zoo visit"),
        ("yesterday/ visit", "2026-10-26", "visit bank"),
        ("tomorrow/", "2026-10-26", "visit vet"),
    ],
)
def test_dated_docs_lines_are_seen_from_the_frozen_day(query, today, expected_first):
    assert titles(query, today)[0] == expected_first, f"{query!r} as of {today} should put {expected_first!r} first"


@pytest.mark.parametrize("view", ["today", "yesterday", "tomorrow", "week", "next-week"])
def test_calendar_scenarios_pin_their_day(view):
    for scenario in SCENARIOS:
        if scenario.typed.startswith(f"{view}/"):
            assert scenario.today, f"{scenario.name} depends on the calendar and should pin its day"
