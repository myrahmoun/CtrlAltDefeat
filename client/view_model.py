"""
view_model.py

Translates raw protobuf messages (pb.GameState, pb.TurnResult) into plain
Python objects that widgets can read without knowing anything about proto
or the oneof card wrapper. This translation happens once, in
game_state_from_proto(), rather than being repeated inside every widget.
"""

from dataclasses import dataclass, field


@dataclass
class ActionCardView:
    name: str
    description: str
    category: str
    responsibility: int
    effect: int


@dataclass
class GlitchCardView:
    name: str
    description: str
    glitch_type: str
    effect_type: str
    target_category: str
    count: int


@dataclass
class ObjectiveCardView:
    name: str
    description: str
    responsibility: int
    effect: int


@dataclass
class HandView:
    non_objective_cards: list  # list[ActionCardView | GlitchCardView]
    objective_cards: list      # list[ObjectiveCardView]


@dataclass
class PlayerView:
    id: str
    name: str
    board_position: int
    lose_next_turn: bool
    hand: HandView
    pending_discard: "dict | None"  # {"count": int, "target_category": str, "reason": str} or None


@dataclass
class GameStateView:
    game_id: str
    status: str
    current_player_id: str
    winner_id: str
    players: list  # list[PlayerView]

    def player(self, player_id: str):
        """Find a player by id, or None if not present."""
        return next((p for p in self.players if p.id == player_id), None)


def _non_objective_card_from_proto(c) -> "ActionCardView | GlitchCardView":
    """Resolve the oneof once, here, so nothing else in the app has to."""
    which = c.WhichOneof("card")
    if which == "action":
        return ActionCardView(
            name=c.name, description=c.description,
            category=c.action.category,
            responsibility=c.action.responsibility,
            effect=c.action.effect,
        )
    elif which == "glitch":
        return GlitchCardView(
            name=c.name, description=c.description,
            glitch_type=c.glitch.glitch_type,
            effect_type=c.glitch.effect_type,
            target_category=c.glitch.target_category,
            count=c.glitch.count,
        )
    raise ValueError(f"NonObjectiveCard has neither action nor glitch set: {c!r}")


def _hand_from_proto(hand) -> HandView:
    return HandView(
        non_objective_cards=[_non_objective_card_from_proto(c) for c in hand.non_objective_cards],
        objective_cards=[
            ObjectiveCardView(name=c.name, description=c.description,
                               responsibility=c.responsibility, effect=c.effect)
            for c in hand.objective_cards
        ],
    )


def game_state_from_proto(state) -> GameStateView:
    """The one place pb.GameState gets turned into plain Python data."""
    return GameStateView(
        game_id=state.game_id,
        status=state.status,
        current_player_id=state.current_player_id,
        winner_id=state.winner_id,
        players=[
            PlayerView(
                id=p.id, name=p.name, board_position=p.board_position,
                lose_next_turn=p.lose_next_turn, hand=_hand_from_proto(p.hand),
                pending_discard=(
                    {"count": p.pending_discard.count,
                     "target_category": p.pending_discard.target_category,
                     "reason": p.pending_discard.reason}
                    if p.HasField("pending_discard") else None
                ),
            )
            for p in state.players
        ],
    )