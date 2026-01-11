# turn_manager.py

from typing import List, Dict, Tuple, Optional
from player import Player
from cards import ObjectiveCard, ActionCard, GlitchCard
from operation import Operation, LoseTurnException, InvalidOperationException


class TurnManager:
    """
    Controls turn sequence and executes turn logic.
    Works with Game's objects but doesn't own them.
    """

    def __init__(self, game) -> None:
        """
        Args:
            game: Reference to parent Game object
        """
        self.game = game
        self.turn_history: List[dict] = []  # Optional: log of past turns

    def execute_turn(self, player: Player, objective: ObjectiveCard, actions: List[ActionCard], die_roll: Optional[int] = None) -> dict:
        """
        Execute a complete turn for a player.
        
        Args:
            player: The player taking their turn
            objective: The objective card being played
            actions: List of 4 action cards (one per category)
            die_roll: Optional die roll value (required if operation needs die roll)
            
        Returns:
            dict with turn results including success, spaces_moved, etc.
        """
        pass

    def skip_turn(self, player: Player, reason: str = "timeout") -> None:
        """
        Skip a player's turn (e.g., due to timeout or glitch effect).
        """
        self.turn_history.append({
            'event': 'turn_skipped',
            'player_id': player.id,
            'player_name': player.name,
            'reason': reason
        })
        
        # Move to next turn
        self.game.next_turn()