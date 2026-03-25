from typing import List, Optional
from cards import ActionCard, ObjectiveCard, GlitchCard, CardStatus
from enum import Enum
import random

class CardPileTypes(Enum):
    ACTION = 1
    OBJECTIVE = 2
    DISCARD = 3

class CardPile():
    '''
    Manages a pile of cards (action deck, objective deck, or discard pile).
    Can draw, add, shuffle, and check if empty.
    '''

    def __init__(self, pile_type):
        """
        pile_type: CardPileTypes.ACTION, CardPileTypes.OBJECTIVE, or CardPileTypes.DISCARD (or their string equivalents)
        """
        if isinstance(pile_type, str):
            self.type = CardPileTypes[pile_type.upper()]
        else:
            self.type = pile_type
        self.content: List = []


    def is_empty(self)->bool:
        return len(self.content) == 0
    

    def add(self, card)-> None:
        """
        Add a card to the pile
        """
        self.content.append(card)
        if self.type == CardPileTypes.ACTION:
            card.cardStatus = CardStatus.IN_ACTIONPILE
        elif self.type == CardPileTypes.OBJECTIVE:
            card.cardStatus = CardStatus.IN_OBJECTIVE_PILE
        elif self.type == CardPileTypes.DISCARD:
            card.cardStatus = CardStatus.IN_DISCARD_PILE


    def draw(self):
        """
        Remove and return the top card.
        Returns None if pile is empty.
        """
        if self.is_empty():
            return None
        
        card = self.content.pop(0)  # Take from top
        return card
    

    def size(self) -> int:
        """Return number of cards in pile."""
        return len(self.content)
    

    def load_cards(self, cards: List) -> None:
        """
        Load a list of cards into the pile (used during initialization).
        """
        self.content = cards
        for card in cards:
            if self.type == CardPileTypes.ACTION:
                card.cardStatus = CardStatus.IN_ACTIONPILE
            elif self.type == CardPileTypes.OBJECTIVE:
                card.cardStatus = CardStatus.IN_OBJECTIVE_PILE
            elif self.type == CardPileTypes.DISCARD:
                card.cardStatus = CardStatus.IN_DISCARD_PILE


    def shuffle(self) -> None:
        """Shuffle the cards in the pile."""
        random.shuffle(self.content)

    def __repr__(self):
        return f"CardPile(type={self.type}, size={self.size()})"
