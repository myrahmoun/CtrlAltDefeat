from typing import List, Dict, Optional
from cards import ActionCard, ObjectiveCard

class Board:
    '''
    Represents the 20-space game board.
    Tracks player positions and displays the current operation's cards.
    '''


    def __init__(self):
        # 20 positions, each holds list of player_ids at that spot
        self.positions: List[List[str]] = [[] for _ in range(20)]

        # 5 card slots for displaying current operation (1 objective + 4 actions)
        self.card_slots: List[Optional[ActionCard | ObjectiveCard]] = [None] * 5


    def add_player(self, player_id: str, position: int = 0) -> None:
        """Place a player at a specific position (default: start at 0)."""
        if 0 <= position < 20:
            self.positions[position].append(player_id)


    def move_player(self, player_id: str, from_pos: int, to_pos: int) -> None:
        """Move player from one position to another."""
        # Remove from old position
        if player_id in self.positions[from_pos]:
            self.positions[from_pos].remove(player_id)
        
        # Add to new position (cap at 19, the winning position)
        final_pos = min(to_pos, 19)
        self.positions[final_pos].append(player_id)


    def get_player_position(self, player_id: str) -> Optional[int]:
        """Find which position a player is currently at."""
        for pos, players in enumerate(self.positions):
            if player_id in players:
                return pos
        return None
    

    def display_cards(self, objective: ObjectiveCard, actions: List[ActionCard]) -> None:
        """Puts the 5 cards (1 objective + 4 actions) into the board's display slots."""
        self.card_slots[0] = objective
        for i, action in enumerate(actions[:4]):  # Max 4 actions
            self.card_slots[i + 1] = action


    def clear_card_slots(self) -> None:
        """Remove all cards from display after turn ends."""
        self.card_slots = [None] * 5


    def get_position_display(self, position: int) -> str:
        """Get readable string of players at a position."""
        if not self.positions[position]:
            return "[ ]"
        return f"[{', '.join(self.positions[position])}]"
    
    def __repr__(self):
        # Show board as a simple visual
        board_str = "Board:\n"
        for i in range(20):
            players = self.get_position_display(i)
            board_str += f"  {i:2d}: {players}\n"
        return board_str

