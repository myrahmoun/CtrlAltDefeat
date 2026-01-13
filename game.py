# game.py

# Library imports
from typing import List, Optional
from pathlib import Path
import json

# Local imports
from board import Board
from cardpile import CardPile
from player import Player
from cards import ActionCard, ObjectiveCard
from die import Die
from turn_manager import TurnManager


# Game files
ACTION_CARDS_FILE = "action_cards.json"
OBJECTIVE_CARDS_FILE = "objective_cards.json"

class Game:
    def __init__(self, game_id: str)-> None:
        # Identifiers
        self.game_id: str
        self.status: str  # 'lobby', 'playing', 'finished'

        # Game objects
        self.game_id = game_id
        self.board = Board()
        self.players: List[Player] = []  # List of Player objects
        self.action_pile = CardPile('action')
        self.objective_pile = CardPile('objective')
        self.discard_pile = CardPile('discard')
        self.die = Die(6)
        self.current_turn = 0
        self.status = 'waiting'  # waiting, playing, finished
        self.winner = None

        # Initate turn manager
        self.turn_manager = TurnManager(self)

        # Initialize turn order
        self.turn_order: List[Player] = []
        self.current_turn_index: int = 0


    # === Manage Players ===
    def add_player(self, player_id)-> None:
        """Add player to game"""
        self.players.append(player_id)
        
    def remove_player(self, player_id) -> None:
        """Remove player (disconnect handling)"""
        self.players.remove(player_id)

    def get_player_by_id(self, player_id: int) -> Optional[Player]:
        """Lookup player by ID and return player object. Might be useful later for gRPC?"""
        for player in self.players:
            if player.id == player_id:
                return player
        return None
        
    # === Manage Turn Sequence ===
    def initialize_turn_order(self):
        """Roll die for each player, sort by roll, populate turn_order"""
        # Check that there some players have joined the game
        if not self.players:
            raise ValueError("Cannot initialize turn order: no players in game")
        
        # Keep rolling until all players have unique rolls
        rolls = {}

        # Keep rolling for each player until they get a unique value
        for player in self.players:
            while True:
                roll = self.die.roll()
                if roll not in rolls.values():
                    rolls[player] = roll
                    print(f"{player.name} rolled {roll}")
                    break
                else:
                    print(f"{player.name} rolled {roll} (tie, re-rolling)")
            
        # Sort players by roll (highest first)
        self.turn_order = sorted(rolls.keys(), key=lambda player: rolls[player], reverse=True)
        self.current_turn_index = 0
    
    def get_current_player(self) -> Player:
        """Return current player"""
        return self.turn_order[self.current_turn_index]
    
    def next_turn(self) -> Player:
        """Advance to next player"""
        self.current_turn_index = (self.current_turn_index + 1) % len(self.turn_order)
        return self.get_current_player()

    # === Game Lifecycle ===
    def start_game(self):
        """
        Initialize game:
        - Load cards from JSON into piles
        - Shuffle piles
        - Deal initial hands (2 obj + 4 actions)
        - Initialize turn order (delegate to turn_manager)
        - Set status to 'playing'
        """
        if not self.can_start():
            raise ValueError(f"Cannot start game: need 3-6 players, have {len(self.players)}")
        
        # Load and shuffle cards
        self.load_cards_from_json()
        self.action_pile.shuffle()
        self.objective_pile.shuffle()

        # Deal initial hands to each player
        for player in self.players:
            # Deal 2 objectives
            for i in range(2):
                card = self.objective_pile.draw()
                if card is None:
                    raise RuntimeError("Ran out of objective cards during initial deal")
                player.hand.objective_cards.append(card)
            
            # Deal 4 actions
            for j in range(4):
                card = self.action_pile.draw()
                if card is None:
                    raise RuntimeError("Ran out of action cards during initial deal")
                player.hand.action_cards.append(card)

        # Initialize turn order
        self.initialize_turn_order()

        # Set status
        self.status = 'playing'


    def end_game(self, winner: Player) -> None:
        """Mark game as finished, set winner"""
        self.status = 'finished'
        self.winner = winner
        winner.playerStatus = 'finished'
        
    # === State Queries ===
    def is_full(self) -> bool:
        """Check if game has 6 players (max)"""
        return len(self.players) >= 6
    
    def can_start(self) -> bool:
        """Check if game has 3-6 players and status is 'lobby'"""
        return 3 <= len(self.players) <= 6 and self.status == 'waiting'

    # === Card Management ===
    def load_cards_from_json(self) -> None:
        """Read card definitions and populate piles"""
        
        # Load action cards
        action_path = Path(ACTION_CARDS_FILE)
        if not action_path.exists():
            raise FileNotFoundError(f"Action cards file not found: {ACTION_CARDS_FILE}")
        
        with open(action_path, 'r') as f:
            action_data = json.load(f)
            if 'cards' not in action_data:
                raise ValueError(f"Invalid format in {ACTION_CARDS_FILE}: missing 'cards' key")
            
            action_cards = []
            for card_dict in action_data['cards']:
                card = ActionCard(
                    name=card_dict['name'],
                    description=card_dict['description'],
                    category=card_dict['category'],
                    responsibility=card_dict['responsibility'],
                    effect=card_dict['effect']
                )
                action_cards.append(card)
            self.action_pile.load_cards(action_cards)
        
        # Load objective cards  
        objective_path = Path(OBJECTIVE_CARDS_FILE)
        if not objective_path.exists():
            raise FileNotFoundError(f"Objective cards file not found: {OBJECTIVE_CARDS_FILE}")
        
        with open(objective_path, 'r') as f:
            objective_data = json.load(f)
            if 'cards' not in objective_data:
                raise ValueError(f"Invalid format in {OBJECTIVE_CARDS_FILE}: missing 'cards' key")
            
            objective_cards = []
            for card_dict in objective_data['cards']:
                card = ObjectiveCard(
                    name=card_dict['name'],
                    description=card_dict['description'],
                    responsibility=card_dict['responsibility'],
                    effect=card_dict['effect']
                )
                objective_cards.append(card)
            self.objective_pile.load_cards(objective_cards)


    def refill_deck_if_empty(self, pile: CardPile) -> None:
        """If pile empty, shuffle discard back in"""
        if pile.is_empty():
            if self.discard_pile.is_empty():
                raise RuntimeError("Cannot refill deck: both deck and discard pile are empty")
        
            # Swap the discard pile's content into the empty pile
            pile.content = self.discard_pile.content
            self.discard_pile.content = []
            # Shuffle the refilled pile
            pile.shuffle()