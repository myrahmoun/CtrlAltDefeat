# game.py

from typing import List, Optional
from board import Board
from cardpile import CardPile
from player import Player
from cards import Hand
from Operation import Operation
from Die import Die
from turn_manager import TurnManager


class Game:
    def __init__(self, game_id: str)-> None:
        # Identifiers
        self.game_id: str
        self.status: str  # 'lobby', 'playing', 'finished'

        # Game objects
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

        # Initate turn manager
        self.turn_manager = TurnManager(self)
    
    def add_player(self, player_id)-> None:
        """Add player to game"""
        self.players.append(player_id)
        
    def remove_player(self, player_id) -> None:
        """Remove player (disconnect handling)"""
        self.players.remove(player_id)

    def get_player(self, player_id) -> Optional[Player]:
        """Lookup player by ID"""
        if player_id in self.players:
            return player_id # MUST RETURN PLAYER OBJECT? OR JUST ID? LATTER IS CIRCULAR

    # === Game Lifecycle ===
    def start_game(self):
        """
        Initialize game:
        - Load cards from JSON into piles
        - Deal initial hands (2 obj + 4 actions)
        - Roll die for turn order
        - Set status to 'playing'
        - Tell turn_manager to start
        """

    def end_game(self, winner: Player) -> None:
        """Mark game as finished, set winner"""
        
    # === State Queries ===
    def is_full(self) -> bool:
        """Check if game has 6 players (max)"""
    
    def can_start(self) -> bool:
        """Check if game has 3-6 players and status is 'lobby'"""

    def get_game_state(self) -> dict:
        """
        Serialize current state for gRPC responses:
        - game_id, status, winner
        - board positions
        - all player info (but only visible hand for requesting player)
        - current turn info
        """

    # === Card Management (called by TurnManager) ===
    def refill_deck_if_empty(self, pile: CardPile) -> None:
        """If pile empty, shuffle discard back in"""
    
    def load_cards_from_json(self) -> None:
        """Read card definitions and populate piles"""