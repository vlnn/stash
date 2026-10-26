import pytest

from docs.scenarios import SCENARIOS, keystrokes, search_items


def titles(query):
    return [item["title"] for item in search_items(query)]


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda scenario: scenario.name)
def test_typing_lands_on_expected_entry(scenario):
    assert titles(scenario.typed)[0] == scenario.lands_on, (
        f"typing {scenario.typed!r} should put {scenario.lands_on!r} first"
    )


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda scenario: scenario.name)
def test_every_keystroke_has_something_to_show(scenario):
    for query in keystrokes(scenario.typed):
        assert titles(query), f"typing {query!r} on the way to {scenario.typed!r} should show at least one row"


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
