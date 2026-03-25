'''
Player Parameters:
    - id: unique integer corresponding to player
    - name: the name of the player
    - role: 
        - "adversary"
        - "agent"
    - hand: the hand of the player with 4 action cards and 2 objective cards
    - boardPosition: the position of the player on the board, also their score. 
    - playerStatus: the status of the player
        - "waiting"
        - "playing"
        - "finished"
'''

import cards

class Player:
    _next_id = 1  # class-level counter

    def __init__(self, name, role='ally'):
        self.id = Player._next_id
        Player._next_id += 1

        self.name = name
        self.role = role
        self.hand = cards.Hand()
        self.boardPosition = 0 # number between 0 and 19
        self.lose_next_turn = False  # Flag for skip turn penalty
        self.playerStatus = "waiting"

    def __repr__(self)->str:
            return (
                f"Player(id={self.id}, name={self.name}, role={self.role}, "
                f"boardPosition={self.boardPosition}, status={self.playerStatus})"
                )
