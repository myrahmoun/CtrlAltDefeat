"""
Game setup, turns, the hand limit, glitch resolution, and the finish rule.
"""

import pytest

from src.cards import (
    ActionCard, GlitchCard, ObjectiveCard,
    CardCategory as Category, GlitchEffectType,
)
from src.game import Game, GameStats
from src.player import Player

REQUIRED = (Category.INTELLIGENCE, Category.TECHNOLOGY,
            Category.GOVERNANCE, Category.CYBERSECURITY)


def operation_cards(responsibility=0, effect=0):
    return [ActionCard(f"{c} card", "d", c, responsibility=responsibility, effect=effect)
            for c in REQUIRED]


def arm(player, objective, actions):
    """Put exactly these cards in a player's hand."""
    player.hand.objective_cards = [objective, ObjectiveCard("spare", "d", 0, 1)]
    player.hand.non_objective_cards = list(actions)


def stack_deck(game, *cards, filler=12):
    """Put `cards` on top of the action pile, backed by harmless filler."""
    game.action_pile.content = list(cards) + [
        ActionCard(f"filler{i}", "d", Category.GOVERNANCE) for i in range(filler)
    ]


# ── Setup ─────────────────────────────────────────────────────────────────

def test_setup_deals_the_right_hands(game):
    assert game.status is GameStats.PLAYING
    for player in game.players:
        assert len(player.hand.objective_cards) == 2
        assert len(player.hand.non_objective_cards) == 4
        assert player.board_position == 0


def test_no_player_starts_with_a_glitch_card(make_game):
    """instructions.md divergence 5 — a deliberate rule, so it needs a guard."""
    for _ in range(25):
        for player in make_game().players:
            assert not any(isinstance(c, GlitchCard)
                           for c in player.hand.non_objective_cards)


def test_glitch_cards_are_returned_to_the_deck_after_dealing(game):
    assert any(isinstance(c, GlitchCard) for c in game.action_pile.content)


def test_turn_order_covers_every_player(game):
    assert sorted(p.name for p in game.turn_order) == sorted(p.name for p in game.players)


@pytest.mark.parametrize("count", [0, 1, 2, 7])
def test_wrong_player_count_cannot_start(count):
    game = Game("g")
    for i in range(count):
        game.players.append(Player(f"p{i}"))
    with pytest.raises(ValueError):
        game.setup_game()


def test_a_started_game_cannot_start_again(game):
    with pytest.raises(ValueError):
        game.setup_game()


# ── Turns ─────────────────────────────────────────────────────────────────

def test_a_successful_turn_advances_play_and_refills_the_objective(game, roll):
    roll(6)
    player = game.get_current_player()
    objective = ObjectiveCard("o", "d", responsibility=1, effect=2)
    actions = operation_cards(responsibility=1, effect=1)
    arm(player, objective, actions)

    result = game.execute_turn(player, objective, actions)

    assert result["success"]
    assert len(player.hand.objective_cards) == 2
    assert objective not in player.hand.objective_cards
    assert game.get_current_player() is not player
    assert all(card in game.discard_pile.content for card in actions)


def test_a_failed_operation_leaves_the_counter_alone(game, roll):
    roll(1)
    player = game.get_current_player()
    player.board_position = 5
    objective = ObjectiveCard("o", "d", responsibility=1, effect=4)
    actions = operation_cards()
    arm(player, objective, actions)

    result = game.execute_turn(player, objective, actions)

    assert not result["success"]
    assert result["spaces_moved"] == 0
    assert player.board_position == 5


def test_going_offline_costs_the_next_turn(game, roll):
    roll(1)
    player = game.get_current_player()
    objective = ObjectiveCard("o", "d", responsibility=0, effect=2)
    actions = operation_cards()
    arm(player, objective, actions)

    result = game.execute_turn(player, objective, actions)
    assert result["lose_turn"]
    assert player.lose_next_turn

    # the skipped turn is consumed without any cards being played
    while game.get_current_player() is not player:
        game.pass_turn()
    assert game.execute_turn(player, None, []) is None
    assert not player.lose_next_turn


def test_a_turn_needs_four_actions_and_an_objective(game):
    player = game.get_current_player()
    with pytest.raises(ValueError):
        game.execute_turn(player, ObjectiveCard("o", "d", 1, 1), operation_cards()[:3])
    with pytest.raises(ValueError):
        game.execute_turn(player, None, operation_cards())


def test_a_pending_discard_blocks_a_turn(game):
    player = game.get_current_player()
    player.pending_discard = {"count": 1, "target_category": "", "reason": "hand_limit"}
    with pytest.raises(ValueError):
        game.execute_turn(player, ObjectiveCard("o", "d", 1, 1), operation_cards())


def test_the_responsibility_bonus_adds_a_space_and_two_cards(game, roll):
    roll(6)
    player = game.get_current_player()
    objective = ObjectiveCard("o", "d", responsibility=0, effect=1)
    actions = operation_cards(responsibility=1, effect=1)
    arm(player, objective, actions)

    result = game._execute_operation(player, objective, actions)

    assert result["bonus"]
    assert player.board_position == 5 + 1  # effect of 5, plus the bonus space


# ── The finish rule (instructions.md, "Playing an operation" step 3) ──────

def test_an_irresponsible_operation_is_held_short_of_the_centre(game, roll):
    roll(6)
    player = game.get_current_player()
    player.board_position = 15
    objective = ObjectiveCard("o", "d", responsibility=0, effect=2)
    actions = operation_cards(effect=2)
    arm(player, objective, actions)

    result = game._execute_operation(player, objective, actions)

    assert result["success"]
    assert result["blocked_from_finish"]
    assert player.board_position == game.FINISH_POSITION - 1
    assert result["spaces_moved"] == 3  # 15 -> 18, not the full effect of 10
    assert game.winner is None


def test_exactly_three_responsibility_may_finish(game, roll):
    roll(6)
    player = game.get_current_player()
    player.board_position = 17
    objective = ObjectiveCard("o", "d", responsibility=3, effect=2)
    actions = operation_cards(effect=1)
    arm(player, objective, actions)

    result = game._execute_operation(player, objective, actions)

    assert result["responsibility"] == 3
    assert not result["blocked_from_finish"]
    assert player.board_position == game.FINISH_POSITION


def test_reaching_the_centre_ends_the_game(game, roll):
    roll(6)
    player = game.get_current_player()
    player.board_position = 15
    objective = ObjectiveCard("o", "d", responsibility=1, effect=2)
    actions = operation_cards(responsibility=1, effect=2)
    arm(player, objective, actions)

    game.execute_turn(player, objective, actions)

    assert player.board_position == game.FINISH_POSITION
    assert game.winner is player
    assert game.status is GameStats.FINISHED


def test_an_operation_far_from_the_line_is_unaffected_by_the_floor(game, roll):
    roll(6)
    player = game.get_current_player()
    player.board_position = 2
    objective = ObjectiveCard("o", "d", responsibility=0, effect=1)
    actions = operation_cards(effect=1)
    arm(player, objective, actions)

    result = game._execute_operation(player, objective, actions)

    assert not result["blocked_from_finish"]
    assert player.board_position == 2 + result["spaces_moved"]


# ── Drawing, glitches, discards ───────────────────────────────────────────

def test_the_deck_refills_from_the_discard_pile(game):
    player = game.get_current_player()
    game.discard_pile.content = list(game.action_pile.content)
    game.action_pile.content = []

    game.draw_cards(player, 1)

    assert len(player.hand.non_objective_cards) == 5


def test_refilling_with_nothing_left_raises(game):
    player = game.get_current_player()
    game.action_pile.content = []
    game.discard_pile.content = []
    with pytest.raises(RuntimeError):
        game.draw_cards(player, 1)


def test_a_draw_glitch_resolves_and_chains(game):
    player = game.get_current_player()
    player.hand.non_objective_cards = []
    glitch = GlitchCard("Budget Increase", "d", "Draw 2 Action Cards",
                        GlitchEffectType.DRAW, None, 2)
    stack_deck(game, glitch)

    events = game.draw_and_resolve_glitches(player, 1)

    assert [e["effect_type"] for e in events] == ["draw"]
    assert not any(isinstance(c, GlitchCard) for c in player.hand.non_objective_cards)
    assert glitch in game.discard_pile.content


def test_a_skip_glitch_costs_the_current_turn(game):
    player = game.get_current_player()
    player.hand.non_objective_cards = []
    glitch = GlitchCard("Approval Delay", "d", "You cannot complete an operation this turn",
                        GlitchEffectType.SKIP_OPERATION, None, 1)
    stack_deck(game, glitch)

    events = game.draw_and_resolve_glitches(player, 1)

    assert [e["effect_type"] for e in events] == ["skip_operation"]
    assert player.lose_next_turn


def test_a_discard_glitch_queues_a_pending_choice(game):
    player = game.get_current_player()
    player.hand.non_objective_cards = [
        ActionCard("tech", "d", Category.TECHNOLOGY),
        ActionCard("gov", "d", Category.GOVERNANCE),
    ]
    glitch = GlitchCard("Technology Fails", "d", "Discard 1 Technology card",
                        GlitchEffectType.DISCARD, Category.TECHNOLOGY, 1)
    stack_deck(game, glitch)

    game.draw_and_resolve_glitches(player, 1)

    assert player.pending_discard is not None
    assert player.pending_discard["target_category"] == Category.TECHNOLOGY.value
    assert player.pending_discard["reason"] == "glitch"


def test_a_discard_glitch_with_no_legal_target_is_skipped(game):
    player = game.get_current_player()
    player.hand.non_objective_cards = [ActionCard("gov", "d", Category.GOVERNANCE)]
    glitch = GlitchCard("Technology Fails", "d", "Discard 1 Technology card",
                        GlitchEffectType.DISCARD, Category.TECHNOLOGY, 1)
    stack_deck(game, glitch)

    game.draw_and_resolve_glitches(player, 1)

    assert player.pending_discard is None


def test_exceeding_the_hand_limit_queues_a_discard(game):
    player = game.get_current_player()
    player.hand.non_objective_cards = [
        ActionCard(f"a{i}", "d", Category.TECHNOLOGY) for i in range(6)
    ]
    stack_deck(game)

    game.draw_and_resolve_glitches(player, 2)

    assert player.pending_discard == {
        "count": 2, "target_category": "", "reason": "hand_limit",
    }


def test_resolving_a_pending_discard_clears_it(game):
    player = game.get_current_player()
    player.hand.non_objective_cards = [
        ActionCard(f"a{i}", "d", Category.TECHNOLOGY) for i in range(7)
    ]
    player.pending_discard = {"count": 1, "target_category": "", "reason": "hand_limit"}

    game.resolve_pending_discard(player, [0])

    assert player.pending_discard is None
    assert len(player.hand.non_objective_cards) == 6


@pytest.mark.parametrize("indices", [[], [0, 1], [0, 0]])
def test_resolving_with_the_wrong_number_of_cards_raises(game, indices):
    player = game.get_current_player()
    player.pending_discard = {"count": 1, "target_category": "", "reason": "hand_limit"}
    with pytest.raises(ValueError):
        game.resolve_pending_discard(player, indices)


def test_resolving_the_wrong_category_raises(game):
    player = game.get_current_player()
    player.hand.non_objective_cards = [
        ActionCard("gov", "d", Category.GOVERNANCE),
        ActionCard("tech", "d", Category.TECHNOLOGY),
    ]
    player.pending_discard = {
        "count": 1, "target_category": Category.TECHNOLOGY.value, "reason": "glitch",
    }
    with pytest.raises(ValueError):
        game.resolve_pending_discard(player, [0])  # the Governance card


def test_resolving_without_a_pending_discard_raises(game):
    with pytest.raises(ValueError):
        game.resolve_pending_discard(game.get_current_player(), [0])


def test_discarding_a_card_the_player_lacks_raises(game):
    player = game.get_current_player()
    with pytest.raises(ValueError):
        game.discard_card(player, ActionCard("elsewhere", "d", Category.TECHNOLOGY))


def test_drawing_with_a_pending_discard_raises(game):
    player = game.get_current_player()
    player.pending_discard = {"count": 1, "target_category": "", "reason": "hand_limit"}
    with pytest.raises(ValueError):
        game.draw_and_resolve_glitches(player, 2)


def test_glitch_chaining_is_bounded(game):
    """An all-glitch deck must terminate rather than spin forever."""
    player = game.get_current_player()
    player.hand.non_objective_cards = []
    game.action_pile.content = [
        GlitchCard(f"g{i}", "d", "Draw 2 Action Cards", GlitchEffectType.DRAW, None, 2)
        for i in range(500)
    ]

    events = game.draw_and_resolve_glitches(player, 1)

    assert len(events) <= Game._MAX_GLITCH_CHAIN
