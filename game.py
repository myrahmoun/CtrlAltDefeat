# game.py

from typing import List, Optional
from board import Board
from cardpile import CardPile
from player import Player
from cards import Hand
from Operation import Operation
from Die import Die


class Game:
    def __init__(self, game_id)-> None:
        self.game_id = game_id
        self.board = Board()
        self.players = []  # List of Player objects
        self.action_pile = CardPile('action')
        self.objective_pile = CardPile('objective')
        self.discard_pile = CardPile('discard')
        self.die = Die(6)
        self.current_turn = 0
        self.status = 'waiting'  # waiting, playing, finished
        self.winner = None
    
    def add_player(self, player, name):
        """Add player to game"""
        self.players.append(player)
        
    def start_game(self):
        """Initialize: load cards, deal hands, set turn order"""
     
    def process_turn(self, player, selected_cards):
        """Execute full turn: validate → create operation → evaluate → move player"""
        
    def next_turn(self):
        """Advance to next player"""
        
    def check_victory(self):
        """Check if anyone reached position 19"""
        
    def get_current_player(self):
        """Return player whose turn it is"""