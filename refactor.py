# refactor_game.py

# Library imports
from typing import List, Dict, Tuple, Optional
from pathlib import Path
import json
import random

# Local imports
from board import Board
from cardpile import CardPile, CardPileTypes
from player import Player
from cards import ActionCard, ObjectiveCard, GlitchCard,  numOfActionCards, numOfGlitchCards, numOfGlitchCards
from die import Die
from enum import Enum
from operation import Operation, LoseTurnException, InvalidOperationException


# Game files
ACTION_CARDS_FILE = Path("data/action_cards.json")
OBJECTIVE_CARDS_FILE = Path("data/objective_cards.json")

class GameStats(Enum):
    LOBBY = 1
    PLAYING = 2
    FINISHED = 3


class Game():
    def __init__(self, game_id: str) -> None:
        self.id = game_id
        self.status = GameStats.LOBBY

        self.board = Board()
        self.players: List[Player] = []
        self.action_pile = CardPile(CardPileTypes.ACTION)
        self.objective_pile = CardPile(CardPileTypes.OBJECTIVE)
        self.discard_pile = CardPile(CardPileTypes.DISCARD)
        self.die = Die(6)
        self.winner = None

        self.turn_order: List[Player] = []
        self.current_turn_index: int = 0

    def setup_game(self) -> None:
        if not self._can_start():
            raise ValueError(f"Cannot start game: need 3-6 players, have {len(self.players)}. Game status: {self.status}")

        # Load cards into piles
        self._load_cards(ACTION_CARDS_FILE, CardPileTypes.ACTION)
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
                player.hand.action_cards.append(card)

        # Initialize and shuffle turn order
        self.turn_order = self.players[:]
        random.shuffle(self.turn_order)
        self.current_turn_index = 0

        # Set game status to playing
        self.status = GameStats.PLAYING

        
    def _can_start(self) -> bool:
        """Check if game has 3-6 players and status is 'lobby'"""
        return 3 <= len(self.players) <= 6 and self.status == GameStats.LOBBY
    

    def _load_cards(self, path: Path, pile_type: CardPileTypes) -> None:
        if not path.exists():
            raise FileNotFoundError(f"Cards file not found: {path}")

        with open(path, 'r') as f:
            data = json.load(f)
        if 'cards' not in data:
            raise ValueError(f"Invalid format in {path}: missing 'cards' key")

        if pile_type == CardPileTypes.ACTION:
            cards = [
                ActionCard(
                    name=c['name'], description=c['description'],
                    category=c['category'], responsibility=c['responsibility'],
                    effect=c['effect']
                )
                for c in data['cards']
            ]
            self.action_pile.load_cards(cards)
        elif pile_type == CardPileTypes.OBJECTIVE:
            cards = [
                ObjectiveCard(
                    name=c['name'], description=c['description'],
                    responsibility=c['responsibility'], effect=c['effect']
                )
                for c in data['cards']
            ]
            self.objective_pile.load_cards(cards)

    def get_current_player(self) -> Player:
        return self.turn_order[self.current_turn_index]

    def next_turn(self) -> Player:
        self.current_turn_index = (self.current_turn_index + 1) % len(self.turn_order)
        return self.get_current_player()

    def execute_turn(self, player: Player, objective: ObjectiveCard, actions: List[ActionCard]) -> None:
        if player.lose_next_turn:
            player.lose_next_turn = False
            self.next_turn()
            return

        if len(actions) != 4 or not objective:
            raise ValueError("Need exactly 4 action cards and 1 objective card")

        self.board.display_cards(objective, actions)
        self._execute_operation(player, objective, actions)

        if player.boardPosition >= 19:
            self.end_game(player)
            return

        for card in actions:
            self.discard_pile.add(card)
            player.hand.action_cards.remove(card)

        player.hand.objective_cards.remove(objective)
        self.objective_pile.content.append(objective)

        new_obj = self.objective_pile.draw()
        if not new_obj:
            raise RuntimeError("Cannot draw objective card")
        player.hand.objective_cards.append(new_obj)

        for _ in range(2):
            self._refill_if_empty(self.action_pile)
            card = self.action_pile.draw()
            if not card:
                raise RuntimeError("Cannot draw action card")
            player.hand.action_cards.append(card)

        self.board.clear_card_slots()
        self.next_turn()

    def _execute_operation(self, player: Player, objective: ObjectiveCard, actions: List[ActionCard]) -> None:
        operation = Operation(objective)
        for action in actions:
            operation.add_action(action)

        try:
            spaces_to_move = operation.evaluate_op()
            player.boardPosition = min(player.boardPosition + spaces_to_move, 19)

            if operation.responsibility >= 4:
                player.boardPosition = min(player.boardPosition + 1, 19)
                for _ in range(2):
                    self._refill_if_empty(self.action_pile)
                    card = self.action_pile.draw()
                    if card and len(player.hand.action_cards) < 6:
                        player.hand.action_cards.append(card)

        except LoseTurnException:
            player.lose_next_turn = True

    def _refill_if_empty(self, pile: CardPile) -> None:
        if pile.is_empty():
            if self.discard_pile.is_empty():
                raise RuntimeError("Cannot refill: both deck and discard pile are empty")
            pile.content = self.discard_pile.content
            self.discard_pile.content = []
            pile.shuffle()

    def end_game(self, winner: Player) -> None:
        self.status = GameStats.FINISHED
        self.winner = winner




