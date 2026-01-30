# turn_manager.py

from typing import List, Dict, Tuple, Optional
from player import Player
from cards import ObjectiveCard, ActionCard, GlitchCard
from Operation import Operation, LoseTurnException, InvalidOperationException


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
        self.turn_order: List[int] = []  # Ordered list of player_ids
        self.current_turn_index: int = 0
        self.turn_history: List[dict] = []  # Optional: log of past turns
    
    # === Turn Sequences ==

    def initialize_turn_order(self) -> None:
        """
        Initlize order of player turns
        """
        if not self.game.players:
            raise ValueError("Cannot initialize turn order: no players in game")
    

    def get_current_player(self) -> Player:
        """Return player whose turn it is"""
        pass

    def next_turn(self):
        """
        Advance to next player in turn_order.
        Wraps around (after last player → first player).
        Returns new current player.
        """
        pass

    # === Turn Execution ===
    
    def execute_turn(self, player: Player, objective: ObjectiveCard, actions: List[ActionCard], die_roll: Optional[int] = None) -> dict:
        """
        Execute a complete turn for a player.
        
        Args:
            player: The player taking their turn
            objective: The objective card being played
            actions: List of 4 action cards (one per category)
            die_roll: Optional die roll value (required if Operation needs die roll)
            
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
        self.next_turn()