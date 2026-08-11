"""
Methods to setup and maintain a game
"""

from typing import List
from pathlib import Path
from enum import Enum
import json
import random

from src.board import Board
from src.cardpile import CardPile, CardPileTypes
from src.player import Player
from src.cards import ActionCard, GlitchCard, ObjectiveCard, CardCategory, GlitchEffectType
from src.die import Die
from src.operation import Operation, LoseTurnException


# Game files
DATA_DIR = Path(__file__).parent.parent / "data"
ACTION_CARDS_FILE = DATA_DIR / "full_action_cards.json"
OBJECTIVE_CARDS_FILE = DATA_DIR / "full_objective_cards.json"

class GameStats(Enum):
    LOBBY = 1
    PLAYING = 2
    FINISHED = 3


class Game():
    """
    Owns and drives a single game's state: the board, players, card piles,
    turn order, and the rules for setting up, progressing, and ending a game.
    """
    _MAX_GLITCH_CHAIN = 50  # guards against a pathological all-glitch remaining deck

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
        self.objective_pile.shuffle()

        # Glitch cards are only ever drawn, never dealt — pull them out of
        # the pile before the initial deal so no player can start with one,
        # then merge them back in afterward for normal mid-game draws.
        glitch_cards = [c for c in self.action_pile.content if isinstance(c, GlitchCard)]
        self.action_pile.content = [c for c in self.action_pile.content if not isinstance(c, GlitchCard)]
        self.action_pile.shuffle()

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

        # Merge glitch cards back into the action pile now that dealing is
        # done, and reshuffle so they're mixed in for mid-game draws.
        self.action_pile.content.extend(glitch_cards)
        self.action_pile.shuffle()

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
        Raises ValueError if not given exactly 4 action cards and 1
        objective, or if the player has a pending glitch discard to resolve
        first (see resolve_pending_glitch_discard).
        """
        if player.lose_next_turn:
            player.lose_next_turn = False
            self.next_turn()
            return

        if player.pending_glitch_discard is not None:
            raise ValueError(f"{player.name} must resolve a pending glitch discard first")

        if len(actions) != 4 or not objective:
            raise ValueError("Need exactly 4 action cards and 1 objective card")

        result = self._execute_operation(player, objective, actions)

        # Detect win
        if player.board_position >= 19:
            self.end_game(player)
            return

        # Discard cards
        for card in actions:
            self.discard_card(player, card)

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
        success, spaces_moved, bonus, lose_turn, and glitch_events (any
        Glitch Cards resolved from the bonus draw — see _resolve_glitches).
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
            'glitch_events': [],
        }

        try:
            spaces_to_move = operation.evaluate_op()
            player.board_position = min(player.board_position + spaces_to_move, 19)
            result['success'] = True
            result['spaces_moved'] = spaces_to_move

            if operation.responsibility >= 4:
                player.board_position = min(player.board_position + 1, 19)
                result['bonus'] = True
                result['glitch_events'] = self.draw_and_resolve_glitches(player, 2)

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
        mid-draw. Does not resolve any Glitch Cards drawn — see
        draw_and_resolve_glitches for the version that does.
        """
        for _ in range(count):
            self._refill_if_empty(self.action_pile)
            card = self.action_pile.draw()
            if card:
                player.hand.non_objective_cards.append(card)

    def draw_and_resolve_glitches(self, player: Player, count: int = 2) -> list:
        """
        Draw `count` cards, then immediately resolve any Glitch Cards among
        them: each is discarded after applying its effect, and effects that
        themselves draw cards can chain into further Glitch Cards, which are
        resolved the same way until none remain in hand (instructions.md,
        "Glitch Cards").

        Returns a list of event dicts (see _resolve_glitches) describing
        what happened, for the caller to relay to the player. If a discard
        effect needs the player to choose which card(s) to discard,
        resolution pauses there — player.pending_glitch_discard is set, and
        the last event's effect_type is "discard" with no further events
        following it until resolve_pending_glitch_discard is called.
        Raises ValueError if the player already has a pending glitch discard.
        """
        if player.pending_glitch_discard is not None:
            raise ValueError(f"{player.name} must resolve a pending glitch discard first")
        self.draw_cards(player, count)
        return self._resolve_glitches(player)

    def _resolve_glitches(self, player: Player) -> list:
        """
        Play and discard Glitch Cards from the player's hand until none
        remain, or until a discard effect needs the player's input (see
        draw_and_resolve_glitches).
        """
        events = []
        chain = 0
        while True:
            glitch = next((c for c in player.hand.non_objective_cards if isinstance(c, GlitchCard)), None)
            if glitch is None:
                return events
            chain += 1
            if chain > self._MAX_GLITCH_CHAIN:
                return events

            player.hand.non_objective_cards.remove(glitch)
            self.discard_pile.add(glitch)

            event = {
                'name': glitch.name,
                'description': glitch.description,
                'effect_type': glitch.effect_type.value,
                'count': glitch.count,
                'target_category': glitch.target_category.value if glitch.target_category else "",
                'drawn_card_names': [],
            }

            if glitch.effect_type == GlitchEffectType.DRAW:
                before = len(player.hand.non_objective_cards)
                self.draw_cards(player, glitch.count)
                event['drawn_card_names'] = [c.name for c in player.hand.non_objective_cards[before:]]
                events.append(event)

            elif glitch.effect_type == GlitchEffectType.DISCARD:
                events.append(event)
                available = [c for c in player.hand.non_objective_cards
                             if glitch.target_category is None or c.category == glitch.target_category]
                if not available:
                    continue  # nothing matches — nothing to pause for
                player.pending_glitch_discard = {
                    'count': min(glitch.count, len(available)),
                    'target_category': event['target_category'],
                }
                return events  # caller must resolve this before we continue

            elif glitch.effect_type == GlitchEffectType.SKIP_OPERATION:
                # Reuses lose_next_turn: since this resolves during the
                # current turn's draw phase, execute_turn's existing check
                # at the top skips *this* turn, not a future one.
                player.lose_next_turn = True
                events.append(event)

    def resolve_pending_glitch_discard(self, player: Player, card_indices: list) -> list:
        """
        Apply the player's chosen discards for a pending glitch-triggered
        discard, then resume resolving any further Glitch Cards.
        Returns the list of further glitch events (see _resolve_glitches).
        Raises ValueError if there's no pending discard, the number of
        chosen cards doesn't match what's required, a duplicate index is
        given, or a chosen card doesn't match the required category.
        """
        pending = player.pending_glitch_discard
        if pending is None:
            raise ValueError(f"{player.name} has no pending glitch discard")
        if len(set(card_indices)) != len(card_indices) or len(card_indices) != pending['count']:
            raise ValueError(f"Must choose exactly {pending['count']} distinct card(s) to discard")

        cards_to_discard = []
        for i in card_indices:
            card = player.hand.non_objective_cards[i]
            if pending['target_category'] and card.category != pending['target_category']:
                raise ValueError(f"{card.name} is not a {pending['target_category']} card")
            cards_to_discard.append(card)

        for card in cards_to_discard:
            self.discard_card(player, card)

        player.pending_glitch_discard = None
        return self._resolve_glitches(player)

    def discard_card(self, player: Player, card) -> None:
        """
        Remove `card` from the player's non-objective hand and add it to
        the discard pile. Used both for voluntary end-of-turn discards and
        for glitch-triggered discards.
        Raises ValueError if the player doesn't have that card in hand.
        """
        if card not in player.hand.non_objective_cards:
            raise ValueError(f"{player.name} does not have {card.name} in hand")
        player.hand.non_objective_cards.remove(card)
        self.discard_pile.add(card)

    def end_game(self, winner: Player) -> None:
        """Mark the game as FINISHED and record the winning player."""
        self.status = GameStats.FINISHED
        self.winner = winner