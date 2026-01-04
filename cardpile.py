from typing import List, Optional
from cards import ActionCard, ObjectiveCard, GlitchCard
import random

class CardPile():
    '''
    Manages a pile of cards (action deck, objective deck, or discard pile).
    Can draw, add, shuffle, and check if empty.
    '''


    def __init__(self, pile_type: str):
        """
        pile_type: 'action', 'objective', or 'discard'
        """
        self.type = pile_type
        self.content: List = []


    def is_empty(self)->bool:
        return len(self.content) == 0
    

    def add(self, card)-> None:
        """
        Add a card to the pile
        """
        self.content.append(card)
        card.cardStatus = f"in_{self.type}_pile"


    def draw(self) -> Optional[ActionCard | ObjectiveCard | GlitchCard]:
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
            card.cardStatus = f"in_{self.type}_pile"


    def shuffle(self) -> None:
        """Shuffle the cards in the pile."""
        random.shuffle(self.content)

    def __repr__(self):
        return f"CardPile(type={self.type}, size={self.size()})"
