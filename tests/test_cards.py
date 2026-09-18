"""Card parsing and deck composition, checked against the source data in data/."""

import json

import pytest

from src.cards import (
    ActionCard, GlitchCard, ObjectiveCard, NonObjectiveCard,
    CardCategory, GlitchEffectType,
)
from src.cardpile import CardPileTypes
from src.game import ACTION_CARDS_FILE, OBJECTIVE_CARDS_FILE, Game

# Per-category totals from CardData/actionCards.csv; see instructions.md.
EXPECTED_CATEGORY_TOTALS = {
    CardCategory.INTELLIGENCE: 20,
    CardCategory.TECHNOLOGY: 18,
    CardCategory.GOVERNANCE: 20,
    CardCategory.CYBERSECURITY: 19,
    CardCategory.GLITCH: 12,
}
EXPECTED_ACTION_DECK = 89


def test_action_deck_composition(game):
    """Every action card is dealt or in a pile, split by category as the CSV says."""
    everything = list(game.action_pile.content) + list(game.discard_pile.content)
    for player in game.players:
        everything.extend(player.hand.non_objective_cards)

    assert len(everything) == EXPECTED_ACTION_DECK

    counts = {}
    for card in everything:
        key = CardCategory(card.category)
        counts[key] = counts.get(key, 0) + 1
    assert counts == EXPECTED_CATEGORY_TOTALS


def test_objective_deck_matches_its_json():
    """
    Structural invariant: one loaded card per JSON entry, since the data has
    no usable `count` column. Holds whether or not that bug is fixed.
    """
    entries = json.load(open(OBJECTIVE_CARDS_FILE))
    game = Game("g")
    game._load_cards(OBJECTIVE_CARDS_FILE, CardPileTypes.OBJECTIVE)
    assert game.objective_pile.size() == sum(Game._copy_count(e) for e in entries)


@pytest.mark.xfail(
    reason="objective 'count' column lost in the CSV->JSON conversion; "
           "see instructions.md, divergence 3",
    strict=False,
)
def test_objective_deck_should_hold_24_cards():
    game = Game("g")
    game._load_cards(OBJECTIVE_CARDS_FILE, CardPileTypes.OBJECTIVE)
    assert game.objective_pile.size() == 24


def test_glitch_cards_are_never_action_cards(game):
    """The two subclasses stay disjoint, since the server branches on type."""
    for player in game.players:
        for card in player.hand.non_objective_cards:
            assert isinstance(card, NonObjectiveCard)
            assert isinstance(card, ActionCard) != isinstance(card, GlitchCard)


def test_action_card_rejects_glitch_category():
    with pytest.raises(ValueError):
        ActionCard("x", "d", CardCategory.GLITCH)


@pytest.mark.parametrize("text, effect, category, count", [
    ("Draw 2 Action Cards", GlitchEffectType.DRAW, None, 2),
    ("Discard 1 Action Card", GlitchEffectType.DISCARD, None, 1),
    ("Discard 1 Technology card", GlitchEffectType.DISCARD, CardCategory.TECHNOLOGY, 1),
    ("Discard 1 Governance Card", GlitchEffectType.DISCARD, CardCategory.GOVERNANCE, 1),
    ("You cannot complete an operation this turn",
     GlitchEffectType.SKIP_OPERATION, None, 1),
])
def test_glitch_type_parsing(text, effect, category, count):
    assert GlitchCard._parse_glitch_type(text) == (effect, category, count)


def test_glitch_type_parsing_is_case_insensitive():
    """The source CSV mixes 'Technology card' and 'Technology Card'."""
    lower = GlitchCard._parse_glitch_type("Discard 1 Technology card")
    upper = GlitchCard._parse_glitch_type("Discard 1 Technology Card")
    assert lower == upper


def test_unparseable_glitch_type_raises():
    with pytest.raises(ValueError):
        GlitchCard._parse_glitch_type("Do something inscrutable")


def test_every_glitch_in_the_data_parses():
    """A new glitch card with unrecognised wording should fail loudly here."""
    for entry in json.load(open(ACTION_CARDS_FILE)):
        if entry["category"].strip() == CardCategory.GLITCH.value:
            card = GlitchCard.from_json(entry)
            assert card.effect_type in tuple(GlitchEffectType)
            assert card.count >= 1


def test_blank_card_values_default_to_zero():
    card = ActionCard.from_json({
        "name": "n", "description": "d", "category": "Technology",
        "responsibility": "", "effect": "",
    })
    assert (card.responsibility, card.effect) == (0, 0)


def test_copy_count_defaults_to_one():
    assert Game._copy_count({}) == 1
    assert Game._copy_count({"count": ""}) == 1
    assert Game._copy_count({"count": 3}) == 3


def test_objective_card_from_json():
    card = ObjectiveCard.from_json({
        "name": "Disrupt State Threats", "description": "d",
        "responsibility": 0, "effect": 5,
    })
    assert (card.name, card.responsibility, card.effect) == ("Disrupt State Threats", 0, 5)
