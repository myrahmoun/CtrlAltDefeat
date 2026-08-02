"""
Objective and non-objective card classes in addition to Hand class.
No methods, just definitions.
"""

from enum import Enum

class CardStatus(Enum):
    IN_NON_OBJECTIVE = "in_non_objective_pile"
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
    GLITCH = "Glitch"

class NonObjectiveCard:
    """
    Creates a new action or glitch card.
    - Eligible piles: Non_objective, Cache
    - There can be a maximum of 4 action cards in a player's hand.
    """

    def __init__(self, name, description, category, responsibility=None, effect=None, glitchType=""):
        self.name = name
        self.description = description
        self.category = category
        self.responsibility = responsibility
        self.effect = effect
        self.glitchType = glitchType
        self.cardStatus=CardStatus['IN_NON_OBJECTIVE']

    def __repr__(self):
        return f"NonObjectiveCard(name={self.name}, description={self.description}, category={self.category}, respScore={self.responsibility}, effectScore={self.effect}, status={self.cardStatus})"


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
        self.cardStatus=CardStatus['IN_OBJECTIVE_PILE']

    def __repr__(self):
        return f"ObjectiveCard(name={self.name}, description={self.description}, respScore={self.responsibility}, effectScore={self.effect}, status={self.cardStatus})"
    

class Hand:
    """
    A collection of non_objective and objective cards that each player has. 
    """
    def __init__(self):
        self.non_objective_cards = []
        self.objective_cards = []

    def __repr__(self):
        return f"Hand(non_objective_cards={self.non_objective_cards}, objective_cards={self.objective_cards})"
