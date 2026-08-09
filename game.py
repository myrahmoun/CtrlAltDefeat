"""
Methods to setup and maintain a game
"""

from typing import List
from pathlib import Path
from enum import Enum
import json
import random

from board import Board
from cardpile import CardPile, CardPileTypes
from player import Player
from cards import ActionCard, GlitchCard, ObjectiveCard, CardCategory
from die import Die
from operation import Operation, LoseTurnException


# Game files
ACTION_CARDS_FILE = Path(__file__).parent / "data" / "full_action_cards.json"
OBJECTIVE_CARDS_FILE = Path(__file__).parent / "data" / "full_objective_cards.json"

class GameStats(Enum):
    LOBBY = 1
    PLAYING = 2
    FINISHED = 3


class Game():
    """
    Owns and drives a single game's state: the board, players, card piles,
    turn order, and the rules for setting up, progressing, and ending a game.
    """

    def __init__(self, game_id: str) -> None:
        """Create a new game in LOBBY status with empty piles and no players yet."""
        self.id = game_id
        self.status = GameStats.LOBBY

        self.board = Board()
        self.players: List[Player] = []
        self.action_pile = CardPile(CardPileTypes.NON_OBJECTIVE)
        self.objective_pile = CardPile(CardPileTypes.OBJECTIVE)
        self.discard_pile = CardPile(CardPileTypes.DISCARD)
        self.die = Die(6)
        self.winner = None

        self.turn_order: List[Player] = []
        self.current_turn_index: int = 0

    def setup_game(self) -> None:
        """
        Transition the game from LOBBY to PLAYING: load and shuffle both
        decks, deal each player 2 objective cards and 4 action cards,
        randomize turn order, and mark the game as in progress.
        Raises ValueError if the player count or game status don't allow a start.
        """
        if not self._can_start():
            raise ValueError(f"Cannot start game: need 3-6 players, have {len(self.players)}. Game status: {self.status}")

        # Load cards into piles
        self._load_cards(ACTION_CARDS_FILE, CardPileTypes.NON_OBJECTIVE)
        self._load_cards(OBJECTIVE_CARDS_FILE, CardPileTypes.OBJECTIVE)
        self.action_pile.shuffle()
        self.objective_pile.shuffle()

        # Populate cards in each player's hand
        for player in self.players:
            for _ in range(2):
                card = self.objective_pile.draw()
                if not card:
                    raise RuntimeError("Ran out of objective cards during deal")
                player.hand.objective_cards.append(card)
            for _ in range(4):
                card = self.action_pile.draw()
                if not card:
                    raise RuntimeError("Ran out of action cards during deal")
                player.hand.non_objective_cards.append(card)

        # Initialize and shuffle turn order
        self.turn_order = self.players[:]
        random.shuffle(self.turn_order)
        self.current_turn_index = 0

        # Set game status to playing
        self.status = GameStats.PLAYING


    def _can_start(self) -> bool:
        """Check if game has 3-6 players and status is 'lobby'"""
        return 3 <= len(self.players) <= 6 and self.status == GameStats.LOBBY


    @staticmethod
    def _copy_count(entry: dict) -> int:
        """
        Return how many copies of a card to load, per the JSON entry's
        'count' field. An empty string or missing field defaults to 1 copy.
        """
        raw = entry.get('count', "")
        return int(raw) if raw != "" else 1

    def _load_cards(self, path: Path, pile_type: CardPileTypes) -> None:
        """
        Read a card JSON file and load it into the given pile, expanding
        each entry into `count` copies. Non-objective entries become either
        an ActionCard or a GlitchCard depending on their category; objective
        entries become ObjectiveCards.
        Raises FileNotFoundError if the given path doesn't exist.
        """
        if not path.exists():
            raise FileNotFoundError(f"Cards file not found: {path}")

        with open(path, 'r') as f:
            data = json.load(f)

        if pile_type == CardPileTypes.NON_OBJECTIVE:
            cards = []
            for c in data:
                copies = self._copy_count(c)
                if c['category'] == CardCategory.GLITCH.value:
                    cards.extend(GlitchCard.from_json(c) for _ in range(copies))
                else:
                    cards.extend(ActionCard.from_json(c) for _ in range(copies))
            self.action_pile.load_cards(cards)
        elif pile_type == CardPileTypes.OBJECTIVE:
            cards = []
            for c in data:
                copies = self._copy_count(c)
                cards.extend(ObjectiveCard.from_json(c) for _ in range(copies))
            self.objective_pile.load_cards(cards)

    def get_current_player(self) -> Player:
        """Return the player whose turn it currently is."""
        return self.turn_order[self.current_turn_index]

    def next_turn(self) -> Player:
        """Advance current_turn_index to the next player and return them."""
        self.current_turn_index = (self.current_turn_index + 1) % len(self.turn_order)
        return self.get_current_player()

    def pass_turn(self) -> None:
        """Skip the current player's turn without executing an operation."""
        self.next_turn()

    def execute_turn(self, player: Player, objective: ObjectiveCard, actions: List[ActionCard]):
        """
        Run a player's turn: if they're serving a skipped turn, just advance
        play. Otherwise build and evaluate an operation from the given
        objective and 4 action cards, apply its outcome to the player's
        board position, discard the used cards, deal a replacement
        objective card, and advance to the next player.

        Returns the operation result dict (see _execute_operation), or None
        if the turn was skipped or the game just ended.
        Raises ValueError if not given exactly 4 action cards and 1 objective.
        """
        if player.lose_next_turn:
            player.lose_next_turn = False
            self.next_turn()
            return

        if len(actions) != 4 or not objective:
            raise ValueError("Need exactly 4 action cards and 1 objective card")

        result = self._execute_operation(player, objective, actions)

        # Detect win
        if player.board_position >= 19:
            self.end_game(player)
            return

        # Discard cards
        for card in actions:
            self.discard_pile.add(card)
            player.hand.non_objective_cards.remove(card)

        player.hand.objective_cards.remove(objective)
        self.objective_pile.content.append(objective)

        # Draw new objective card
        new_obj = self.objective_pile.draw()
        if not new_obj:
            raise RuntimeError("Cannot draw objective card")
        player.hand.objective_cards.append(new_obj)

        self.next_turn()
        return result

    def _execute_operation(self, player: Player, objective: ObjectiveCard, actions: List[ActionCard]) -> dict:
        """
        Build an Operation from the objective and action cards, evaluate it,
        and apply the outcome to the player: move them forward on success
        (with a bonus space and 2 extra cards if responsibility >= 4), or
        flag them to lose their next turn if the operation triggers a
        LoseTurnException.

        Returns a dict describing the outcome: responsibility, effect,
        success, spaces_moved, bonus, and lose_turn.
        """
        operation = Operation(objective)
        for action in actions:
            operation.add_action(action)

        result = {
            'responsibility': operation.responsibility,
            'effect': operation.effect,
            'success': False,
            'spaces_moved': 0,
            'bonus': False,
            'lose_turn': False,
        }

        try:
            spaces_to_move = operation.evaluate_op()
            player.board_position = min(player.board_position + spaces_to_move, 19)
            result['success'] = True
            result['spaces_moved'] = spaces_to_move

            if operation.responsibility >= 4:
                player.board_position = min(player.board_position + 1, 19)
                result['bonus'] = True
                self.draw_cards(player, 2)

        except LoseTurnException:
            player.lose_next_turn = True
            result['lose_turn'] = True

        return result

    def _refill_if_empty(self, pile: CardPile) -> None:
        """
        If the given pile is empty, refill it by shuffling the discard pile
        back in. Raises RuntimeError if both the pile and the discard pile
        are empty, since there's nothing left to refill from.
        """
        if pile.is_empty():
            if self.discard_pile.is_empty():
                raise RuntimeError("Cannot refill: both deck and discard pile are empty")
            pile.content = self.discard_pile.content
            self.discard_pile.content = []
            pile.shuffle()

    def draw_cards(self, player: Player, count: int = 2) -> None:
        """
        Draw `count` cards from the action pile into the player's hand,
        refilling the action pile from the discard pile if it runs out
        mid-draw.
        """
        for _ in range(count):
            self._refill_if_empty(self.action_pile)
            card = self.action_pile.draw()
            if card:
                player.hand.non_objective_cards.append(card)

    def end_game(self, winner: Player) -> None:
        """Mark the game as FINISHED and record the winning player."""
        self.status = GameStats.FINISHED
        self.winner = winner