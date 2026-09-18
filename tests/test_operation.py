"""
Operation scoring and the die tables.

These mirror instructions.md, "Scoring" step by step: both totals include the
Objective Card, and each responsibility band has its own outcome table.
"""

import pytest

from src.cards import ActionCard, ObjectiveCard, CardCategory as Category
from src.operation import (
    Operation, LoseTurnException, OperationFailedException, InvalidOperationException,
)

REQUIRED = (Category.INTELLIGENCE, Category.TECHNOLOGY,
            Category.GOVERNANCE, Category.CYBERSECURITY)


def build(objective_responsibility=0, objective_effect=0,
          action_responsibility=0, action_effect=0, categories=REQUIRED):
    operation = Operation(ObjectiveCard(
        "Objective", "d",
        responsibility=objective_responsibility, effect=objective_effect,
    ))
    for category in categories:
        operation.add_action(ActionCard(
            f"{category} card", "d", category,
            responsibility=action_responsibility, effect=action_effect,
        ))
    return operation


# ── Totals include the Objective Card (instructions.md, Scoring 1 and 6) ──

def test_totals_include_the_objective_card():
    operation = build(objective_responsibility=2, objective_effect=6,
                      action_responsibility=1, action_effect=1)
    assert operation.responsibility == 2 + 4
    assert operation.effect == 6 + 4


def test_objective_alone_sets_the_totals():
    operation = Operation(ObjectiveCard("o", "d", responsibility=2, effect=5))
    assert (operation.responsibility, operation.effect) == (2, 5)


def test_replacing_a_card_of_the_same_category_nets_out():
    """add_action displaces same-category cards; totals must follow."""
    operation = build(objective_responsibility=1, objective_effect=3,
                      action_responsibility=1, action_effect=1)
    displaced = operation.add_action(
        ActionCard("swap", "d", Category.TECHNOLOGY, responsibility=5, effect=5)
    )
    assert displaced is not None
    assert operation.responsibility == 1 + 1 + 1 + 1 + 5
    assert operation.effect == 3 + 1 + 1 + 1 + 5


# ── Die tables ────────────────────────────────────────────────────────────

def test_responsibility_4_or_more_succeeds_without_a_roll(roll):
    roll(1)  # would fail in any other band
    operation = build(objective_responsibility=0, objective_effect=2,
                      action_responsibility=1, action_effect=1)
    assert operation.responsibility == 4
    assert operation.evaluate_op() == operation.effect


@pytest.mark.parametrize("die, succeeds", [(1, False), (2, False),
                                           (3, True), (4, True), (5, True), (6, True)])
def test_mid_responsibility_band(roll, die, succeeds):
    """Responsibility 1-3: 1-2 fail, 3-6 succeed."""
    roll(die)
    operation = build(objective_responsibility=2, objective_effect=4)
    assert operation.responsibility == 2
    if succeeds:
        assert operation.evaluate_op() == 4
    else:
        with pytest.raises(OperationFailedException):
            operation.evaluate_op()


@pytest.mark.parametrize("die, outcome", [
    (1, "offline"), (2, "offline"),
    (3, "fail"), (4, "fail"), (5, "fail"),
    (6, "success"),
])
def test_low_responsibility_band(roll, die, outcome):
    """Responsibility 0 or less: 1-2 go offline, 3-5 fail, 6 succeeds."""
    roll(die)
    operation = build(objective_responsibility=0, objective_effect=3)
    assert operation.responsibility == 0

    if outcome == "success":
        assert operation.evaluate_op() == 3
    elif outcome == "fail":
        with pytest.raises(OperationFailedException):
            operation.evaluate_op()
    else:
        with pytest.raises(LoseTurnException):
            operation.evaluate_op()


def test_negative_responsibility_uses_the_low_band(roll):
    roll(6)
    operation = build(objective_responsibility=0, objective_effect=2,
                      action_responsibility=-1, action_effect=1)
    assert operation.responsibility == -4
    assert operation.evaluate_op() == 6


def test_a_die_failure_is_distinct_from_a_zero_effect_success(roll):
    """
    Both score no movement, but only one is a failure — the client reports
    them differently, so evaluate_op must not conflate them.
    """
    roll(6)
    zero_effect = build(objective_responsibility=1, objective_effect=0)
    assert zero_effect.evaluate_op() == 0  # succeeded, just went nowhere

    roll(1)
    failed = build(objective_responsibility=1, objective_effect=5)
    with pytest.raises(OperationFailedException):
        failed.evaluate_op()


# ── Completeness ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("missing", REQUIRED)
def test_an_operation_missing_any_category_is_invalid(missing):
    categories = [c for c in REQUIRED if c is not missing]
    operation = build(categories=categories)
    with pytest.raises(InvalidOperationException):
        operation.evaluate_op()


def test_four_cards_of_one_category_is_still_invalid():
    operation = build(categories=(Category.TECHNOLOGY,) * 4)
    with pytest.raises(InvalidOperationException):
        operation.evaluate_op()


def test_an_operation_without_an_objective_is_invalid():
    operation = Operation(None)
    for category in REQUIRED:
        operation.add_action(ActionCard("a", "d", category))
    with pytest.raises(InvalidOperationException):
        operation.evaluate_op()
