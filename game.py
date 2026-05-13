# game.py

# Library imports
from typing import List, Optional
from pathlib import Path
import json
import random

# Local imports
from board import Board
from cardpile import CardPile, CardPileTypes
from player import Player
from cards import ActionCard, ObjectiveCard
from cards import numOfActionCards, numOfGlitchCards, numOfGlitchCards
from die import Die
# from turn_manager import TurnManager
from enum import Enum


# Game files
ACTION_CARDS_FILE = "data/action_cards.json"
OBJECTIVE_CARDS_FILE = "data/objective_cards.json"

class GameStats(Enum):
    LOBBY = 1
    PlAYING = 2
    FINISHED = 3

class Game:
    def __init__(self, game_id: str)-> None:
        # Identifiers
        self.game_id: str
        # Set game status to lobby
        self.status = GameStats.LOBBY

        # Game objects
        self.game_id = game_id
        self.board = Board()
        self.players: List[Player] = []  # List of Player objects
        self.action_pile = CardPile(CardPileTypes.ACTION)
        self.objective_pile = CardPile(CardPileTypes.OBJECTIVE)
        self.discard_pile = CardPile(CardPileTypes.DISCARD)
        self.die = Die(6)
        self.current_turn = 0
        self.winner = None

        # Initate turn manager
        # self.turn_manager = TurnManager(self)

        # Initialize turn order
        self.turn_order: List[Player] = []
        self.current_turn_index: int = 0
        self.turn_history: List[dict] = []

    # === Manage Players ===
    def add_player(self, player: Player)-> None:
        """Add player to game"""
        if self.status == GameStats.LOBBY:
            self.players.append(player)
        else:
            raise ValueError("Game not in Lobby mode. Cannot add player")
        
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
    def execute_turn(self, player: Player, objective: ObjectiveCard, actions: List[ActionCard]) -> None:
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
        # Check if player has lost rights to this turn
        
        if player.lose_next_turn:
            player.lose_next_turn = False
            self.skip_turn(player, reason = "lost_previous_turn")
            return

        # Check that we have four action cards and an objective card
        if len(actions) != 4:
            raise ValueError(f"Need exactly 4 action cards, got {len(actions)}")
        if not objective:
            raise ValueError("Need one objective card, got none")
    

        # Display cards on board
        self.board.display_cards(objective, actions)

        # Build and evaluate operation
        success, bonus_applied, spaces_to_move  = self._execute_operation(player, objective, actions)

        # Check if current_player won
        if player.boardPosition >= 19:
            self.end_game(player)
            return

        # Discard action cards
        for card in actions:
            self.discard_pile.add(card)
            player.hand.action_cards.remove(card)

        # Return objective card to the bottom of the objective deck
        player.hand.objective_cards.remove(objective)
        self.objective_pile.content.append(objective)
        
        # Draw replacement cards
        # Objective
        new_obj = self.objective_pile.draw()
        if not new_obj:
            raise RuntimeError("Cannot draw objective card")
        player.hand.objective_cards.append(new_obj)

        # Action - TODO: ADD OPTION TO DRAW FROM TOP OF DISCARD PILE
        for _ in range(2):
            self.refill_deck_if_empty(self.action_pile)
            card = self.action_pile.draw()
            if not card:
                raise RuntimeError("Cannot draw action card")
            player.hand.action_cards.append(card)

        # Clear board (UI)
        self.board.clear_card_slots()

        # Log turn
        self.turn_history.append({
            'event': 'turn_executed',
            'player_id': player.id,
            'player_name': player.name,
            'success': success,
            'spaces_moved': spaces_to_move,
            'final_position': player.boardPosition
        })

        # Move to next turn
        self.next_turn()

        # Can return a dict of results here (later for gRPC)

    def get_current_player(self) -> Player:
        """Return current player"""
        return self.turn_order[self.current_turn_index]
    
    def execute_turn(self, player: Player, objective: ObjectiveCard, actions: List[ActionCard]) -> None:
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
        # Check if player has lost rights to this turn
        
        if player.lose_next_turn:
            player.lose_next_turn = False
            self.skip_turn(player, reason = "lost_previous_turn")
            return

        # Check that we have four action cards and an objective card
        if len(actions) != 4:
            raise ValueError(f"Need exactly 4 action cards, got {len(actions)}")
        if not objective:
            raise ValueError("Need one objective card, got none")
    

        # Display cards on board
        self.board.display_cards(objective, actions)

        # Build and evaluate operation
        success, bonus_applied, spaces_to_move  = self._execute_operation(player, objective, actions)

        # Check if current_player won
        if player.boardPosition >= 19:
            self.end_game(player)
            return

        # Discard action cards
        for card in actions:
            self.discard_pile.add(card)
            player.hand.action_cards.remove(card)

        # Return objective card to the bottom of the objective deck
        player.hand.objective_cards.remove(objective)
        self.objective_pile.content.append(objective)
        
        # Draw replacement cards
        # Objective
        new_obj = self.objective_pile.draw()
        if not new_obj:
            raise RuntimeError("Cannot draw objective card")
        player.hand.objective_cards.append(new_obj)

        # Action - TODO: ADD OPTION TO DRAW FROM TOP OF DISCARD PILE
        for _ in range(2):
            self.refill_deck_if_empty(self.action_pile)
            card = self.action_pile.draw()
            if not card:
                raise RuntimeError("Cannot draw action card")
            player.hand.action_cards.append(card)


        # Clear board (UI)
        self.board.clear_card_slots()

        # Log turn
        self.turn_history.append({
            'event': 'turn_executed',
            'player_id': player.id,
            'player_name': player.name,
            'success': success,
            'spaces_moved': spaces_to_move,
            'final_position': player.boardPosition
        })

        # Move to next turn
        self.next_turn()

        # Can return a dict of results here (later for gRPC)

    def next_turn(self) -> Player:
        """Advance to next player"""
        self.current_turn_index = (self.current_turn_index + 1) % len(self.turn_order)
        return self.get_current_player()

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

    def pass_turn(self, player: Player) -> None:
        """Player voluntarily passes their turn."""
        self.skip_turn(player, reason="passed")
        # TODO: UPDATE STATUS OR SOMETHING TO IMPACT TURN EXEC
        def _execute_operation(self, player: Player, objective: ObjectiveCard, actions: List[ActionCard])->tuple:
        """Build an operation and evaluate it. Return (was operation successful, is a bonus applicable)"""

        operation = Operation(objective)
        for action in actions:
            operation.add_action(action)
        
        try:
            # Evaluate operation. Might raise LoseTurnException
            spaces_to_move = operation.evaluate_op()
            success = True

            # Move Player
            old_pos = player.boardPosition
            new_pos = min(old_pos + spaces_to_move , 19) # Cap position at 19
            player.boardPosition = new_pos

            # Bonus (if applicable): extra space + draw two action cards
            bonus_applied = False
            if operation.responsibility >= 4:
                # Move an extra space
                new_pos = min(new_pos + 1, 19)
                player.boardPosition = new_pos
                bonus_applied = True

                # Draw 2 extra cards
                for _ in range(2):
                    self.refill_deck_if_empty(self.action_pile)
                    card = self.action_pile.draw()
                    if card and len(player.hand.action_cards) < 6:  # Respect 6 card limit
                        player.hand.action_cards.append(card)
                    else:
                        raise RuntimeError("Adding bonus card failed")

        except LoseTurnException:
            player.lose_next_turn = True # Set flag for next turn
            success = False
            bonus_applied = False
            spaces_to_move = 0  

        return success, bonus_applied, spaces_to_move

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
        self._load_cards_from_json()
        self.action_pile.shuffle()
        self.objective_pile.shuffle()

        # Deal initial hands to each player
        for player in self.players:
            # Deal 2 objectives
            for _ in range(2):
                card = self.objective_pile.draw()
                if card is None:
                    raise RuntimeError("Ran out of objective cards during initial deal")
                player.hand.objective_cards.append(card)
            
            # Deal 4 actions
            for _ in range(4):
                card = self.action_pile.draw()
                if card is None:
                    raise RuntimeError("Ran out of action cards during initial deal")
                player.hand.action_cards.append(card)

        # Initialize turn order
        self._initialize_turn_order()

        # Set status
        self.status = GameStats.PlAYING

    def end_game(self, winner: Player) -> None:
        """Mark game as finished, set winner"""
        self.status = GameStats.FINISHED
        self.winner = winner
        # TODO: REPAIR - TURN INTO ENUM
        winner.playerStatus = 'finished'
        
    # === State Queries ===
    def is_full(self) -> bool:
        """Check if game has 6 players (max)"""
        return len(self.players) >= 6
    
    def can_start(self) -> bool:
        """Check if game has 3-6 players and status is 'lobby'"""
        return 3 <= len(self.players) <= 6 and self.status == GameStats.LOBBY

    # === Card Management ===
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

    # === Internal Methods ===
    def _initialize_turn_order(self):
        """Randomly assign a turn order for the game """
        # Check that there some players have joined the game
        if not self.players:
            raise ValueError("Cannot initialize turn order: no players in game")

        self.turn_order = self.players 
        random.shuffle(self.turn_order)
        self.current_turn_index = 0

        return self.turn_order

    def _load_cards_from_json(self) -> None:
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