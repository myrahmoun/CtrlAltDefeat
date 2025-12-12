'''
This file contains the classes for the player.
Parameters:
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
    def __init__(self, name, role):
        self.name = name
        self.role = role
        self.hand = cards.Hand()
        self.boardPosition = 0
        self.playerStatus = "waiting"

        def __repr__(self):
            return f"Player(name={self.name}, role={self.role}, hand={self.hand}, boardPosition={self.boardPosition}, status={self.status})"

