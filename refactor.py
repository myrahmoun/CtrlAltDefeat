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
        self.turn_history: List[dict] = []

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







