"""
Player Parameters:
    - id: unique integer corresponding to player
    - name: the name of the player
    - role: 
        - "adversary"
        - "agent"
    - hand: the hand of the player with 4 action cards and 2 objective cards
    - board_position: the position of the player on the board, also their score.
    - playerStatus: the status of the player
        - "waiting"
        - "playing"
        - "finished"
"""

import uuid
import cards

class Player:
    def __init__(self, name, role='ally'):
        self.id = str(uuid.uuid4())

        self.name = name
        self.role = role
        self.hand = cards.Hand()
        self.board_position = 0
        self.lose_next_turn = False  # Flag for skip turn penalty
        self.playerStatus = "waiting"

    def __repr__(self)->str:
            return (
                f"Player(id={self.id}, name={self.name}, role={self.role}, "
                f"board_position={self.board_position}, status={self.playerStatus})"
                )
