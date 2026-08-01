"""
Action, objective, and glitch card classes in addition to Hand class.
No methods, just definitions.
"""

from enum import Enum

class CardStatus(Enum):
    IN_ACTIONPILE = "in_actionpile"
    IN_CACHE_PILE = "in_cache_pile"
    IN_OBJECTIVE_PILE = "in_objective_pile"
    IN_HAND = "In_hand"
    IN_PLAY = "in_play"
    IN_DISCARD_PILE = "in_discard_pile"

class CardCategory(str, Enum):
    CYBERSECURITY = "Cybersecurity"
    GOVERNANCE = "Governance"
    TECHNOLOGY = "Technology"
    INTELLIGENCE = "Intelligence"

class ActionCard:
    """
    Creates a new action or glitch card.
    - Eligible piles: Action, Cache
    - There can be a maximum of 4 action cards in a player's hand.
    """

    def __init__(self, name, description, category, responsibility=None, effect=None, glitchType=None):
        self.name = name
        self.description = description
        self.category = category
        self.responsibility = responsibility
        self.effect = effect
        self.glitchType = glitchType
        self.cardStatus:CardStatus

    def __repr__(self):
        return f"NoneObjectiveCard(name={self.name}, description={self.description}, category={self.category}, respScore={self.responsibility}, effectScore={self.effect}, status={self.cardStatus})"


class ObjectiveCard:
    """
    Creates a new objective card.
    - Eligible piles: objective_pile
    - There must be 2 objective cards in a player's hand by the end of each turn.
    """
    def __init__(self, name, description, responsibility, effect):
        self.name = name
        self.description = description
        self.responsibility = responsibility
        self.effect = effect
        self.cardStatus:CardStatus

    def __repr__(self):
        return f"ObjectiveCard(name={self.name}, description={self.description}, respScore={self.responsibility}, effectScore={self.effect}, status={self.cardStatus})"
    

class Hand:
    """
    A collection of action and objective cards that each player has. 
    """
    def __init__(self):
        self.action_cards = []
        self.objective_cards = []

    def __repr__(self):
        return f"Hand(action_cards={self.action_cards}, objective_cards={self.objective_cards})"
