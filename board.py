from typing import List, Optional
from cards import ActionCard, ObjectiveCard

class Board:
    '''
    Represents the 20-space game board for display purposes.
    Tracks what cards are currently being shown and provides visual representations.
    Player position tracking is handled by Game.
    '''
    def __init__(self):
        # 5 card slots for displaying current operation (1 objective + 4 actions)
        self.card_slots: List[Optional[ActionCard | ObjectiveCard]] = [None] * 5

    def display_cards(self, objective: ObjectiveCard, actions: List[ActionCard]) -> None:
        """Puts the 5 cards (1 objective + 4 actions) into the board's display slots."""
        self.card_slots[0] = objective
        for i, action in enumerate(actions[:4]):  # Max 4 actions
            self.card_slots[i + 1] = action


    def clear_card_slots(self) -> None:
        """Remove all cards from display after turn ends."""
        self.card_slots = [None] * 5


    def get_visual_board(self, players: List) -> str:
        """
        Generate visual representation of board with player positions.
        Sample output: 
            Board:
                0: [Alice, Bob]
                1: [ ]
                2: [Charlie]
                ...
                19: [ ]
        """
        board_str = "Board:\n"
        for i in range(20):
            # Find players at this position
            players_here = [p.name for p in players if p.boardPosition == i]
            if players_here:
                board_str += f"  {i:2d}: [{', '.join(players_here)}]\n"
            else:
                board_str += f"  {i:2d}: [ ]\n"
        return board_str
    
    def __repr__(self): # Reports displayed cards on board
        displayed = [c.name for c in self.card_slots if c]
        return f"Board(displayed_cards: {displayed if displayed else 'none'})"

